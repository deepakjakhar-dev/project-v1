"""WebRTC receiver: phone -> aiortc -> Python frames -> YOLO person detection.

Signaling model (mirrors the browser session observed in the handoff):
  1. Connect to the phone's WebSocket (ws://<phone-ip>:12121/ws).
  2. Send camera_ready to announce ourselves.
  3. The PHONE sends an "offer"; we create an aiortc answer and send it back.
     (If no offer arrives within a few seconds, we send our own offer instead.)
  4. Feed any ICE candidates either side produces through the WebSocket.
  5. On connection, consume the remote video track, convert frames to numpy,
     and run YOLOv8n person detection on the latest frame (latest-wins, so a
     slow detector never builds up lag).

Usage:
    python eagle_eye/webrtc_client.py

Environment:
    WS_URL      signaling WebSocket URL (default ws://192.168.1.2:12121/ws)
    CAMERA_NAME camera to announce (default back)
    SHOW_WINDOW 1 = OpenCV preview with detection boxes (default 1)
    DETECT      0 = disable detection (default 1)
    YOLO_CONF   detection confidence threshold (default 0.35)
    YOLO_MODEL  model file (default yolov8n.pt)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp
from websockets.asyncio.client import connect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("webrtc")

WS_URL = os.environ.get("WS_URL", "ws://192.168.1.2:12121/ws")
CAMERA_NAME = os.environ.get("CAMERA_NAME", "back")
SHOW_WINDOW = os.environ.get("SHOW_WINDOW", "1") == "1"
DETECT = os.environ.get("DETECT", "1") == "1"
YOLO_CONF = float(os.environ.get("YOLO_CONF", "0.35"))
YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")
OFFER_TIMEOUT_S = 5.0


@dataclass
class Detection:
    conf: float
    x: int
    y: int
    w: int
    h: int


class FrameStats:
    """Rolling FPS counter for the incoming track."""

    def __init__(self) -> None:
        self.count = 0
        self.t0 = time.monotonic()

    def tick(self) -> None:
        self.count += 1
        now = time.monotonic()
        if self.count == 1:
            self.t0 = now
            log.info("FIRST FRAME received")
        elif self.count % 150 == 0:
            dt = now - self.t0
            log.info("recv frames=%d  fps=%.1f", self.count, self.count / dt)


class LatestFrame:
    """Slot that always holds the newest frame; the detector skips stale ones."""

    def __init__(self) -> None:
        self._img: np.ndarray | None = None
        self._cond = threading.Condition()
        self.fresh = False

    def put(self, img: np.ndarray) -> None:
        with self._cond:
            self._img = img
            self.fresh = True
            self._cond.notify()

    def get(self, timeout: float) -> np.ndarray | None:
        with self._cond:
            if not self._cond.wait_for(lambda: self._img is not None, timeout):
                return None
            img, was_fresh = self._img, self.fresh
            self.fresh = False
        if not was_fresh:
            return None  # already processed; wait for a new one
        return img


class Detector:
    """YOLOv8n person detector running on the newest frame in its own thread."""

    def __init__(self, slot: LatestFrame) -> None:
        from ultralytics import YOLO  # heavy import, only when detection is on

        self.model = YOLO(YOLO_MODEL)
        self.slot = slot
        self.lock = threading.Lock()
        self.latest: list[Detection] = []
        self.infer_fps = 0.0
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            img = self.slot.get(timeout=0.5)
            if img is None:
                continue
            t0 = time.monotonic()
            results = self.model.predict(img, classes=[0], conf=YOLO_CONF, verbose=False)
            dt = time.monotonic() - t0
            dets = [
                Detection(
                    conf=float(b.conf[0]),
                    x=int(b.xyxy[0][0]),
                    y=int(b.xyxy[0][1]),
                    w=int(b.xyxy[0][2] - b.xyxy[0][0]),
                    h=int(b.xyxy[0][3] - b.xyxy[0][1]),
                )
                for b in results[0].boxes
            ]
            with self.lock:
                self.latest = dets
                # smooth the inference-rate readout
                self.infer_fps = 0.8 * self.infer_fps + 0.2 * (1.0 / max(dt, 1e-6))

    def snapshot(self) -> tuple[list[Detection], float]:
        with self.lock:
            return self.latest, self.infer_fps

    def stop(self) -> None:
        self._stop.set()


def parse_candidate(data: dict[str, Any]) -> RTCIceCandidate | None:
    """Build an aiortc candidate from the phone's JSON candidate message."""
    cand = data.get("candidate") or {}
    sdp = cand.get("candidate", "") if isinstance(cand, dict) else str(cand)
    if not sdp:
        return None
    try:
        base = candidate_from_sdp(sdp.split(" ", 1)[1] if sdp.startswith("candidate:") else sdp)
    except (ValueError, IndexError):
        return None
    base.sdpMid = cand.get("sdpMid")
    base.sdpMLineIndex = cand.get("sdpMLineIndex")
    return base


def draw_detections(img: np.ndarray, dets: list[Detection], infer_fps: float) -> None:
    for d in dets:
        cv2.rectangle(img, (d.x, d.y), (d.x + d.w, d.y + d.h), (32, 176, 255), 2)
        cv2.putText(
            img,
            f"PERSON {d.conf:.2f}",
            (d.x, max(d.y - 6, 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (32, 176, 255),
            2,
        )
    cv2.putText(
        img,
        f"infer {infer_fps:.1f} fps  persons {len(dets)}",
        (10, img.shape[0] - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (200, 200, 200),
        1,
    )


async def run() -> None:
    pc = RTCPeerConnection()
    stats = FrameStats()
    done = asyncio.Event()

    slot = LatestFrame()
    detector: Detector | None = None
    detector_thread: threading.Thread | None = None
    if DETECT:
        loop = asyncio.get_running_loop()
        detector = await loop.run_in_executor(None, Detector, slot)
        detector_thread = threading.Thread(target=detector.run, name="yolo", daemon=True)
        detector_thread.start()
        log.info("YOLO model ready (%s, conf=%.2f)", YOLO_MODEL, YOLO_CONF)

    last_log = 0.0

    @pc.on("track")
    def on_track(track):  # noqa: ANN001
        log.info("track received: %s (ready=%s)", track.kind, track.readyState)
        nonlocal last_log

        async def consume():
            nonlocal last_log
            try:
                while True:
                    frame = await track.recv()
                    stats.tick()
                    img = frame.to_ndarray(format="bgr24")
                    if detector is not None:
                        slot.put(img)
                        now = time.monotonic()
                        if now - last_log >= 0.5:
                            dets, infer_fps = detector.snapshot()
                            last_log = now
                            if dets:
                                best = max(dets, key=lambda d: d.conf)
                                log.info(
                                    "persons=%d  best conf=%.2f bbox=(%d,%d %dx%d)  infer %.1f fps",
                                    len(dets), best.conf, best.x, best.y, best.w, best.h, infer_fps,
                                )
                            else:
                                log.info("persons=0  infer %.1f fps", infer_fps)
                    if SHOW_WINDOW:
                        if detector is not None:
                            dets, infer_fps = detector.snapshot()
                            draw_detections(img, dets, infer_fps)
                        cv2.imshow("eagle-eye", img)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            done.set()
                            break
            except Exception as exc:  # noqa: BLE001
                log.exception("frame consumer died: %r", exc)
                done.set()

        asyncio.ensure_future(consume())

    @pc.on("connectionstatechange")
    def on_state():  # noqa: ANN001
        log.info("pc state: %s", pc.connectionState)
        if pc.connectionState in ("failed", "closed"):
            done.set()

    async with connect(WS_URL) as ws:
        log.info("connected to %s", WS_URL)

        async def sender():
            """Consumes outbound messages from a queue -> WebSocket."""
            while True:
                msg = await out_queue.get()
                await ws.send(json.dumps(msg))

        out_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        sender_task = asyncio.create_task(sender())

        def send(msg: dict[str, Any]) -> None:
            out_queue.put_nowait(msg)

        async def receiver():
            """Handles every signaling message the phone sends."""
            while True:
                raw = await ws.recv()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.info("<<< %s", raw)
                    continue

                mtype = msg.get("type")
                cam = msg.get("cam", "")
                if mtype == "offer":
                    log.info("<<< offer from phone (cam=%s)", cam)
                    await pc.setRemoteDescription(
                        RTCSessionDescription(sdp=msg["offer"]["sdp"], type="offer")
                    )
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    send(
                        {
                            "type": "answer",
                            "answer": {
                                "type": "answer",
                                "sdp": pc.localDescription.sdp,
                            },
                            "cam": cam or CAMERA_NAME,
                        }
                    )
                    log.info(">>> answer sent")
                elif mtype == "answer":
                    log.info("<<< answer received")
                    await pc.setRemoteDescription(
                        RTCSessionDescription(sdp=msg["answer"]["sdp"], type="answer")
                    )
                elif mtype == "candidate":
                    cand = parse_candidate(msg)
                    if cand is not None:
                        await pc.addIceCandidate(cand)
                        log.info("<<< candidate added")
                elif mtype in ("camera_ready", "status"):
                    pass  # heartbeats, already characterized in signaling_client.py
                else:
                    log.info("<<< %s", mtype)

        recv_task = asyncio.create_task(receiver())

        send({"type": "camera_ready", "camera": CAMERA_NAME, "cam": CAMERA_NAME})
        log.info(">>> camera_ready sent, waiting for phone offer (%.0fs timeout)", OFFER_TIMEOUT_S)

        # Fallback: if the phone never offered, we offer ourselves.
        try:
            await asyncio.wait_for(done.wait(), timeout=OFFER_TIMEOUT_S)
        except asyncio.TimeoutError:
            pass
        if pc.remoteDescription is None and pc.connectionState not in ("connected", "failed"):
            log.info("no phone offer — sending our own")
            pc.addTransceiver("video", direction="recvonly")
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            send(
                {
                    "type": "offer",
                    "offer": {"type": "offer", "sdp": pc.localDescription.sdp},
                    "cam": CAMERA_NAME,
                }
            )
            log.info(">>> offer sent")
            await done.wait()

        sender_task.cancel()
        recv_task.cancel()
        if detector is not None:
            detector.stop()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
