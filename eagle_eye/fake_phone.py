"""Fake phone: connects to pose_receiver over WSS and streams a walk loop.

Two modes:
- Default (no WITH_FRAMES): pose stream only, like the earlier test.
- WITH_FRAMES=1: also streams synthetic 320x240 JPEG frames so the
  receiver's detection + projection path can be exercised without a real
  phone.

The synthetic frames contain a person silhouette for the receiver's frame
path. YOLO will not fire on drawn shapes; with INJECT_DETECTION=1 on the
receiver, a simulated detection keeps the track -> world -> overlay chain
live for offline testing.

Usage:
    python eagle_eye/fake_phone.py [wss://127.0.0.1:8443/ws] [name]
    WITH_FRAMES=1 python eagle_eye/fake_phone.py wss://127.0.0.1:8443/ws fake

Offline full-pipeline test (receiver side):
    INJECT_DETECTION=1 WITH_FRAMES=1 python eagle_eye/fake_phone.py ...
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import ssl
import sys
import time

import cv2
import numpy as np
from websockets.asyncio.client import connect as ws_connect


async def main(url: str, name: str) -> None:
    with_frames = os.environ.get("WITH_FRAMES", "0") == "1"

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed lab cert
    async with ws_connect(url, ssl=ctx) as ws:
        # give the server a moment to start up before we flood it
        await asyncio.sleep(0.2)
        t0 = time.time()
        count = 320 if with_frames else 40
        for i in range(count):
            if ws.state == 3:  # CLOSED
                break
            # pose a camera slowly circling the room so projection sees varied angles
            ang = i * 0.015
            px = math.sin(ang) * 2.2
            pz = math.cos(ang) * 2.2
            py = 1.25
            qz = math.sin(ang * 0.5) * 0.4
            qw = math.cos(ang * 0.5)
            qx = 0.0
            qy = 0.0

            pose_msg = {
                "type": "pose",
                "name": name,
                "t": i,
                "c": time.time() * 1000,
                "x": round(px, 3),
                "y": round(py, 3),
                "z": round(pz, 3),
                "qx": round(qx, 6),
                "qy": round(qy, 6),
                "qz": round(qz, 6),
                "qw": round(qw, 6),
            }
            await ws.send(json.dumps(pose_msg))

            if with_frames:
                img = _make_frame(i, px, py, pz)
                buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
                b64 = base64.b64encode(buf).decode()
                frame_msg = {
                    "type": "frame",
                    "name": name,
                    "n": i,
                    "c": time.time() * 1000,
                    "jpeg": "data:image/jpeg;base64," + b64,
                }
                if ws.state == 3:  # CLOSED
                    break
                await ws.send(json.dumps(frame_msg))
            await asyncio.sleep(0.05)

        print(
            f"fake_phone: sent {count} messages as {name} "
            f"(frames={'yes' if with_frames else 'no'})"
        )
    print("fake_phone: done")


def _make_frame(i: int, cam_x: float, cam_y: float, cam_z: float) -> np.ndarray:
    """A synthetic 320x240 BGR frame with a dark room and a static person blob
    near frame center so the receiver's detector + projection path can be
    exercised offline."""
    h, w = 240, 320
    img = np.full((h, w, 3), (10, 14, 12), dtype=np.uint8)

    # floor/sight line for orientation cues
    floor_y = int(h * 0.8)
    img[floor_y, :] = (30, 34, 30)

    # synthetic person silhouette (head + body + arms + legs) for the
    # receiver's detector + projection path to exercise. YOLO itself will
    # not fire on pure synthetic shapes, so the receiver also supports an
    # INJECT_DETECTION=1 mode that synthesizes a person detection at a
    # known location for offline pipeline testing.
    cx = int(w * 0.55)
    base_y = int(h * 0.85)  # feet position
    head_r = 12
    body_top = base_y - int(h * 0.72)
    head_cy = body_top - 6
    body_w = 26
    body_left = cx - body_w // 2
    body_right = cx + body_w // 2
    # torso
    cv2.rectangle(img, (body_left, body_top), (body_right, base_y), (70, 75, 80), cv2.FILLED)
    # head
    cv2.circle(img, (cx, head_cy), head_r, (65, 70, 75), cv2.FILLED)
    # arms
    cv2.line(img, (body_left, body_top + 18), (body_left - 14, body_top + 50), (70, 75, 80), 6)
    cv2.line(img, (body_right, body_top + 18), (body_right + 14, body_top + 50), (70, 75, 80), 6)
    # legs
    cv2.line(img, (cx - 6, base_y), (cx - 12, base_y + 18), (55, 60, 65), 8)
    cv2.line(img, (cx + 6, base_y), (cx + 12, base_y + 18), (55, 60, 65), 8)

    return img


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "wss://127.0.0.1:8443/ws"
    name = sys.argv[2] if len(sys.argv) > 2 else "fake"
    try:
        asyncio.run(main(url, name))
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)
