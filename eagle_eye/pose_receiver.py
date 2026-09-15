"""Eagle Eye — WebXR pose + frame receiver, with live fusion.

Serves webxr/index.html over HTTPS, receives ARCore pose (+ optional JPEG
frames) from phone browsers running Chrome on Android, runs YOLOv8n person
detection on the latest frame per camera, converts detections into 3D world
points using monocular person-height depth, and broadcasts the resulting
shared world state to any world-state listener (e.g. the viewer page).

Run (Mac or Windows, same steps):

    python eagle_eye/pose_receiver.py            # server mode
    python eagle_eye/pose_receiver.py selftest   # offline sanity check

Then open  https://<this-machine-ip>:8443/?name=cam1  on each phone, tap
through the certificate warning (one tap to trust) and press Enter AR.

World state is served at  https://<ip>:8443/world  (JSON, polled by viewers).
"""

from __future__ import annotations

import asyncio
import datetime
import http
import json
import os
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import websockets
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response

# Allow running both as a module (python -m eagle_eye.pose_receiver) and as a
# script (python eagle_eye/pose_receiver.py) by making the project root
# importable before the package imports below.
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from eagle_eye.fusion import (  # noqa: E402
    WorldState,
    _mat_vec_mul,
    _quat_to_matrix,
    focal_px_for,
)

HERE = _HERE
PORT = int(os.environ.get("EE_PORT", "8443"))

SHOW_WINDOW = os.environ.get("EE_SHOW", "1") == "1"
SAVE_FRAMES_ENV = os.environ.get("SAVE_FRAMES", "0") == "1"

# Detector execution.
DETECT = os.environ.get("DETECT", "1") == "1"
YOLO_CONF = float(os.environ.get("YOLO_CONF", "0.35"))
YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")

# Shared (lock-protected) world state.
WORLD = WorldState()
WORLD_LOCK = threading.Lock()
WORLD.mutex = WORLD_LOCK

# Frame slots: name -> latest decoded BGR numpy image. The detector pops the
# newest frame (latest-wins) and marks the slot None until the next one lands.
latest_frames: dict[str, np.ndarray | None] = {}
FRAME_LOCK = threading.Lock()

# Telemetry.
frame_counts: dict[str, int] = {}
frame_stats: dict[str, dict] = {}
clock_offsets: dict[str, dict] = {}  # name -> {"off": seconds, "rtt": seconds}
pose_stats: dict[str, dict] = {}

# Offline testing: when INJECT_DETECTION=1, a synthetic person detection is
# injected when YOLO finds nothing, so the full track -> world -> overlay
# chain can be demonstrated without a real person on camera.
INJECT_DETECTION = os.environ.get("INJECT_DETECTION", "0") == "1"

# Detector state.
_detect_model = None
_detect_model_lock = threading.Lock()


def _load_detector():
    """Load (or reuse) the YOLOv8n person detector. Heavy import happens here."""
    global _detect_model
    with _detect_model_lock:
        if _detect_model is None:
            from ultralytics import YOLO
            _detect_model = YOLO(YOLO_MODEL)
        return _detect_model


def _process_one(name: str) -> None:
    """Detect persons on the newest frame for `name` and update WORLD."""
    # Pop the newest frame (latest-wins) in one locked step.
    FRAME_LOCK.acquire()
    try:
        img = latest_frames.get(name)
        if img is None:
            return
        latest_frames[name] = None
    finally:
        FRAME_LOCK.release()

    img_h, img_w = img.shape[0], img.shape[1]

    try:
        model = _load_detector()
        now_s = time.time()
        results = model.predict(img, classes=[0], conf=YOLO_CONF, verbose=False)
    except Exception as exc:  # never let detector trouble kill the server
        print(f"\n[!] detector error ({name}): {exc}", flush=True)
        return

    dets = []
    for b in results[0].boxes:
        dets.append({
            "x": int(b.xyxy[0][0]),
            "y": int(b.xyxy[0][1]),
            "w": int(b.xyxy[0][2] - b.xyxy[0][0]),
            "h": int(b.xyxy[0][3] - b.xyxy[0][1]),
            "conf": float(b.conf[0]),
        })
    if not dets and INJECT_DETECTION:
        # Simulated detection: a person-shaped box center-frame, sized so the
        # person-height depth math places them ~2.5 m away.
        box_h = int(img_h * 0.42)
        dets.append({
            "x": img_w // 2 - 20,
            "y": img_h // 2 - box_h // 2,
            "w": 40,
            "h": box_h,
            "conf": 0.90,
        })

    WORLD_LOCK.acquire()
    try:
        # Record frame size so cross-camera projection uses real dims.
        WORLD.update_frame(name, img, img_w, img_h)
        pose = WORLD.cam_pose(name)
        if pose is not None:
            for d in dets:
                WORLD.update_track_from_detection(name, d, pose, img_w, img_h, now_s)
            WORLD.prune(now_s)
    finally:
        WORLD_LOCK.release()


def _detector_worker() -> None:
    """Background loop: detect on the newest frame of every camera that has one.

    Iterates the actual frame-slot keys, so any camera name works (cam1…,
    fake, smoke — not just the hardcoded first three).
    """
    while True:
        with FRAME_LOCK:
            names = [n for n, img in latest_frames.items() if img is not None]
        for name in names:
            try:
                _process_one(name)
            except Exception as exc:
                print(f"\n[!] detector worker error ({name}): {exc}", flush=True)
        time.sleep(0.06)


def _draw_markers_for_viewer(img: np.ndarray, viewer_name: str) -> np.ndarray:
    """Return a copy of img with red X markers for tracks visible to this camera.

    In-view only (per project decision): a track is drawn only when its world
    point projects inside this camera's image and in front of it. Projection
    goes through WORLD.projection_for so the math matches fusion exactly.
    """
    import cv2

    out = img.copy()
    img_h, img_w = img.shape[:2]

    WORLD_LOCK.acquire()
    try:
        tracks = list(WORLD.tracks.values())
    finally:
        WORLD_LOCK.release()

    # Prefer the actual image dims we are drawing on.
    WORLD_LOCK.acquire()
    try:
        st = WORLD.cams.get(viewer_name)
        if st is not None:
            st.img_w, st.img_h = img_w, img_h
    finally:
        WORLD_LOCK.release()

    for trk in tracks:
        WORLD_LOCK.acquire()
        try:
            proj = WORLD.projection_for(trk, viewer_name)
        finally:
            WORLD_LOCK.release()
        if proj is None:
            continue
        u, v = int(round(proj["u"])), int(round(proj["v"]))
        # Distance for marker size + label.
        pose = WORLD.cam_pose(viewer_name)
        if not pose:
            continue
        dist = (
            (trk.x - pose["x"]) ** 2
            + (trk.y - pose["y"]) ** 2
            + (trk.z - pose["z"]) ** 2
        ) ** 0.5
        s = max(6, min(16, int(1200.0 / max(dist, 0.3))))
        cv2.drawMarker(out, (u, v), (0, 0, 255), cv2.MARKER_CROSS,
                       markerSize=s, thickness=2)
        cv2.putText(out, f"{trk.id} ~{dist:.1f}m",
                    (max(4, u - 30), max(14, v - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    return out


def local_ip() -> str:
    """Best-effort LAN IP so the printed URL is directly usable."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def make_cert(certfile: Path, keyfile: Path) -> None:
    """Generate a self-signed cert (phones need HTTPS for WebXR)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "eagle-eye")])
    sans: list[x509.GeneralName] = [
        x509.DNSName("localhost"), x509.DNSName("eagle-eye")
    ]
    for ip in {local_ip(), "127.0.0.1"}:
        sans.append(x509.IPAddress(ipaddress.ip_address(ip)))
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        )
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(key, hashes.SHA256())
    )
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def ssl_context() -> ssl.SSLContext:
    certfile, keyfile = HERE / "cert.pem", HERE / "key.pem"
    if not certfile.exists():
        print("generating self-signed certificate (cert.pem / key.pem)…")
        make_cert(certfile, keyfile)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    return ctx


async def handle(ws) -> None:
    """Handle one WebSocket node connection (pose/frame/sync/hb messages)."""
    peer = getattr(ws, "remote_address", ("?", 0))[0]
    print(f"[+] node connected from {peer}")
    hb_count = 0
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            name = msg.get("name", "?")
            mtype = msg.get("type")

            if mtype == "pose":
                now_s = time.time()
                st = pose_stats.setdefault(
                    name,
                    {"n": 0, "t0": now_s, "last": now_s, "lat": None},
                )
                st["n"] += 1
                st["last"] = now_s
                off_entry = clock_offsets.get(name)
                if msg.get("c") is not None and off_entry:
                    lat_ms = max(
                        0.0,
                        (now_s - (msg["c"] / 1000.0 + off_entry["off"])) * 1000.0,
                    )
                    if lat_ms < 2000:
                        st.setdefault("lats", []).append(lat_ms)
                        if len(st["lats"]) > 50:
                            st["lats"] = st["lats"][-50:]
                        st["lat"] = sorted(st["lats"])[len(st["lats"]) // 2]
                if now_s - st["t0"] >= 5.0:
                    fps = st["n"] / (now_s - st["t0"])
                    lat = (f"  latency {st['lat']:.0f} ms"
                           if st["lat"] is not None else "")
                    unc = (f" ±{clock_offsets[name]['rtt']*500:.0f}"
                           if name in clock_offsets else "")
                    print(f"\n[{name}] pose fps {fps:.1f}{lat}{unc}   ",
                          flush=True)
                    st["n"], st["t0"] = 0, now_s
                # Record for fusion even before any frame arrives.
                WORLD_LOCK.acquire()
                try:
                    WORLD.update_cam(name, msg)
                finally:
                    WORLD_LOCK.release()
                print(
                    f"\r{name}: x={msg['x']:+.2f}  y={msg['y']:+.2f}  "
                    f"z={msg['z']:+.2f}   ",
                    end="", flush=True,
                )
            elif mtype == "sync":
                rtt = float(msg.get("rtt", 1e9))
                off = float(msg.get("off") or 0)
                cur = clock_offsets.get(name)
                if cur is None or rtt < cur["rtt"] * 0.9:
                    clock_offsets[name] = {"off": off, "rtt": rtt}
                    print(f"\n[~] {name}: clock synced — rtt={rtt:.0f}ms (best)")
            elif mtype == "hb":
                hb_count += 1
                if hb_count == 1:
                    print(f"\n[~] {name}: websocket link confirmed (heartbeat)")
            elif mtype == "frame":
                frame_counts[name] = int(msg.get("n", 0))
                import base64 as b64mod
                import cv2

                buf = np.frombuffer(
                    b64mod.b64decode(msg["jpeg"].split(",", 1)[1]), np.uint8
                )
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                FRAME_LOCK.acquire()
                try:
                    latest_frames[name] = img
                finally:
                    FRAME_LOCK.release()
                now_s = time.time()
                fs = frame_stats.setdefault(
                    name, {"n": 0, "t0": now_s, "last": now_s}
                )
                fs["n"] += 1
                fs["last"] = now_s
                if SAVE_FRAMES_ENV:
                    out = HERE / "frames"
                    out.mkdir(exist_ok=True)
                    (out / f"{name}_{msg['n']:06d}.jpg").write_bytes(
                        b64mod.b64decode(msg["jpeg"].split(",", 1)[1])
                    )
                # The polling detector workers pick this up within ~60 ms.
    finally:
        print(f"\n[-] node {peer} disconnected")


def process_request(connection, request) -> Any:
    """Serve the phone page + /time + /world for plain HTTPS GETs."""
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None  # let the websocket handshake proceed

    page = HERE / "webxr" / "index.html"
    if request.path == "/time" or request.path.startswith("/time?"):
        return Response(
            http.HTTPStatus.OK,
            "OK",
            Headers([("Content-Type", "application/json"),
                     ("Cache-Control", "no-store")]),
            json.dumps({"t": time.time(), "server_t": time.time()}).encode(),
        )
    if request.path == "/world" or request.path.startswith("/world?"):
        body = WORLD.snapshot()
        j = json.dumps(body, separators=(",", ":")).encode()
        return Response(
            http.HTTPStatus.OK,
            "OK",
            Headers([("Content-Type", "application/json"),
                     ("Cache-Control", "no-store"),
                     ("Content-Length", str(len(j)))]),
            j,
        )
    if page.exists():
        body = page.read_bytes()
        status = http.HTTPStatus.OK
    else:
        body = b"missing webxr/index.html"
        status = http.HTTPStatus.NOT_FOUND
    return Response(
        status,
        status.phrase,
        Headers(
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ]
        ),
        body,
    )


def viewer_thread() -> None:
    """Show the latest camera image from every node in OpenCV windows."""
    import cv2

    while True:
        with FRAME_LOCK:
            items = [(n, i) for n, i in latest_frames.items() if i is not None]
        if not items:
            time.sleep(0.2)
            continue
        try:
            for name, img in items:
                merged = _draw_markers_for_viewer(img, name)
                cv2.imshow(f"eagle-eye {name}", merged)
            if cv2.waitKey(40) & 0xFF == ord("q"):
                cv2.destroyAllWindows()
                return
        except cv2.error:
            return


async def main() -> None:
    ctx = ssl_context()
    ip = local_ip()
    print("Eagle Eye receiver running.")
    print(f"  phones : https://{ip}:{PORT}/?name=cam1   (cam2, cam3 …)")
    print(f"  stream : wss://{ip}:{PORT}/ws")
    print(f"  world  : https://{ip}:{PORT}/world   (JSON, polled by viewers)")
    if SHOW_WINDOW:
        print("  video  : OpenCV window opens when a phone streams frames (q quits)")
    if DETECT:
        print("  detect : YOLO person detection on latest frame per camera")
        print(f"           model={YOLO_MODEL} conf={YOLO_CONF:.2f} (webxr frames)")
    if SHOW_WINDOW:
        threading.Thread(target=viewer_thread, daemon=True).start()
    if DETECT:
        for idx in range(2):
            threading.Thread(
                target=_detector_worker,
                name=f"detect-worker-{idx}",
                daemon=True,
            ).start()
    try:
        server = serve(handle, "0.0.0.0", PORT, ssl=ctx,
                       process_request=process_request)
        async with server:
            await asyncio.Future()
    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            print(f"\nPORT {PORT} IS BUSY — a receiver is probably already running.",
                  flush=True)
            print("Fix: close the other one (or on Windows:  netstat -ano | findstr 8443",
                  flush=True)
            print("     then  taskkill /F /PID <that number>),  then start this again.",
                  flush=True)
            sys.exit(1)
        raise


def _blank(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def selftest() -> None:
    """Offline sanity check: fusion math + cert generation, no server needed."""
    # camA at the origin looking +Z (identity). A detection box centered at
    # (160, 128) with 96px height in a 320x240 frame puts the person at
    # ~(0, 0.14, 3.33) m in camA's frame (1.7 m person height assumption).
    pose_a = {"x": 0.0, "y": 0.0, "z": 0.0, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0}
    WORLD.update_cam("camA", pose_a)
    WORLD.update_frame("camA", _blank(320, 240), 320, 240)

    det = {"x": 144, "y": 80, "w": 32, "h": 96, "conf": 0.91}
    trk = WORLD.update_track_from_detection(
        "camA", det, pose_a, 320, 240, time.time()
    )
    assert 0.5 < trk.z < 6.0, f"depth sanity failed: {trk.z}"

    # Round-trip: projecting the world point back into camA must land on the
    # detection's box center (160, 128).
    back = WORLD.projection_for(trk, "camA")
    assert back is not None, f"camA round-trip failed: {back}"
    assert abs(back["u"] - 160) < 2 and abs(back["v"] - 128) < 2, back

    # camB stands 1.5 m to the right and 0.5 m back, yawed to look straight at
    # the person (exercises the world->local transpose with a real rotation).
    yaw = -27.9  # degrees, tuned for this geometry
    qy = math_sin_half(yaw)
    qw = math_cos_half(yaw)
    pose_b = {"x": 1.5, "y": 0.0, "z": 0.5, "qx": 0.0, "qy": qy, "qz": 0.0, "qw": qw}
    WORLD.update_cam("camB", pose_b)
    WORLD.update_frame("camB", _blank(320, 240), 320, 240)
    proj_b = WORLD.projection_for(trk, "camB")
    assert proj_b is not None, f"camB should see the person: {proj_b}"
    assert 0 <= proj_b["u"] <= 320 and 0 <= proj_b["v"] <= 240, proj_b

    # camC looks 90 degrees away — the person must be behind/off-screen.
    pose_c = {"x": 0.0, "y": 0.0, "z": 0.0, "qx": 0.0, "qy": 0.70710677,
              "qz": 0.0, "qw": 0.70710677}
    WORLD.update_cam("camC", pose_c)
    WORLD.update_frame("camC", _blank(320, 240), 320, 240)
    proj_c = WORLD.projection_for(trk, "camC")
    assert proj_c is None, f"camC should NOT see the person: {proj_c}"

    assert cert_and_key_roundtrip()
    print("selftest OK: fusion math (round-trip, cross-camera, behind-camera)"
          " + cert generation")


def math_sin_half(deg: float) -> float:
    import math
    return math.sin(math.radians(deg) / 2.0)


def math_cos_half(deg: float) -> float:
    import math
    return math.cos(math.radians(deg) / 2.0)


def cert_and_key_roundtrip() -> bool:
    certfile, keyfile = HERE / ".selftest_cert.pem", HERE / ".selftest_key.pem"
    try:
        make_cert(certfile, keyfile)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        return True
    finally:
        certfile.unlink(missing_ok=True)
        keyfile.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        asyncio.run(main())
