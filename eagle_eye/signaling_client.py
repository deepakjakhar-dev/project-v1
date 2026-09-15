"""Tiny WebSocket signaling client that mirrors Chrome's dialogue with the phone app.

Goal (Stage 0 from the handoff):
1. Connect to ws://192.168.1.2:12121/ws
2. Send the camera_ready message the app expects.
3. Print every incoming message so we can reproduce the SDP/ICE exchange.
4. Once we understand the protocol, fold this into an aiortc-based receiver.

Usage:
    python eagle_eye/signaling_client.py

Config is read from environment so we can point it at a different phone/server
without editing code:

    WS_URL        - signaling WebSocket URL (default: ws://192.168.1.2:12121/ws)
    CAMERA_NAME   - which camera to announce (default: back)
    WEBCAM_DEVICE - optional; not used by this client but reserved for the aiortc stage
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("signaling")


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


WS_URL = _env_str("WS_URL", "ws://192.168.1.2:12121/ws")
CAMERA_NAME = _env_str("CAMERA_NAME", "back")


async def run() -> None:
    import websockets

    log.info("connecting to %s", WS_URL)
    async with websockets.connect(WS_URL) as ws:
        log.info("connected")

        # Step 1: announce the camera the same way the browser did.
        camera_ready: dict[str, Any] = {
            "type": "camera_ready",
            "camera": CAMERA_NAME,
            "cam": CAMERA_NAME,
        }
        await ws.send(json.dumps(camera_ready))
        log.info("sent camera_ready: %s", camera_ready)

        # Step 2: mirror everything the server sends back.
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = raw
                log.info("<<< %s", msg)
                _maybe_capture_state(msg)
        except websockets.ConnectionClosed as exc:
            log.info("connection closed: %s", exc)


_STATE: dict[str, Any] | None = None


def _maybe_capture_state(msg: Any) -> None:
    """Keep the latest full status payload for the next aiortc stage."""
    global _STATE
    if isinstance(msg, dict) and msg.get("type") == "status":
        _STATE = msg


def current_state() -> dict[str, Any] | None:
    return _STATE


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
