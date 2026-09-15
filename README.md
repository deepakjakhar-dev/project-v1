# Eagle Eye

Live multi-camera person detection with shared 3D positioning. Android phones
become sensor nodes: each streams **ARCore position (WebXR)** + camera frames
to a central Python server, which detects people (YOLOv8n), places them in the
room's 3D space, and will project markers onto every other camera's view —
including onto walls that occlude the person.

## Status

- [x] Phone → PC live video (WebRTC, ~25 FPS)
- [x] YOLOv8n person detection on the stream (latest-wins detector thread)
- [x] **WebXR pose streaming**: phone ARCore position → PC, no app install
- [x] Pose FPS + clock-synced latency measurement
- [x] **Fusion**: detections × pose → 3D world tracks (monocular depth from
  person bounding-box height, one camera per person — no triangulation)
- [x] Cross-camera red-X overlay on incoming frames (in-view projection)
- [x] `/world` JSON endpoint + browser viewer that consumes it

Current mode: **in-view projection only** — a red X appears on another
camera's frame when the tracked person is inside that camera's field of
view. Shared world alignment (so markers work across rooms) is a later
stage.

## Quick start (Windows PC or Mac — same steps)

```bash
pip install -r requirements.txt

# WebXR pose receiver (phones connect here)
python eagle_eye/pose_receiver.py
#   → open https://<machine-ip>:8443/?name=cam1 on each phone in Chrome
#   → accept the self-signed cert warning (one tap), then Enter AR
#   → console shows live x/y/z, pose FPS and latency every 5 s
#   → tracks appear at https://<machine-ip>:8443/world (JSON)
#   → open viewer/index.html on any laptop to watch the shared world

# WebRTC video + YOLO detection from the phone app stream
python eagle_eye/webrtc_client.py
```

## The phone side (WebXR node)

`webxr/index.html` is served by the receiver itself over HTTPS (WebXR
requires it). Two buttons: **pose only** and **camera + pose**. The page
clock-syncs to the server (`/time`) so the PC can compute true one-way
latency, stamps every pose/frame with a capture timestamp, and streams:

```json
{"type": "pose", "name": "cam1", "c": 123456.7,
 "x": 0.42, "y": -0.01, "z": -1.13, "qx": 0, "qy": 0, "qz": 0, "qw": 1}
```

## Environment flags (pose_receiver.py)

| Flag | Default | Meaning |
|---|---|---|
| `EE_PORT` | 8443 | HTTPS+WSS port |
| `EE_SHOW` | 1 | OpenCV windows for incoming camera frames (red X overlay included) |
| `SAVE_FRAMES` | 0 | Save incoming JPEGs to `frames/` |
| `DETECT` | 1 | Run YOLOv8n on incoming frames |
| `YOLO_CONF` | 0.35 | Detector confidence threshold |
| `YOLO_MODEL` | yolov8n.pt | Detector weights |
| `INJECT_DETECTION` | 0 | Inject a synthetic track each second (offline demo of the full chain, no phone needed) |

## The shared world state

Every detected person becomes a track at `https://<machine-ip>:8443/world`:

```json
{"t": 1760000000.1, "tracks": [
  {"id": "p1", "x": 0.62, "y": 1.25, "z": 5.31,
   "conf": 0.71, "seen_by": ["cam1"], "age": 0.4}
], "cams": {"cam1": {"x": 0.0, "y": 1.3, "z": 0.0, "fps": 29.9}}}
```

`viewer/index.html` polls this endpoint (defaults to the same host serving
it; override with `?server=wss://host:8443`) and draws live tracks on top
of its simulation — with the simulation as fallback when nothing is
connected.

## Test utilities

```bash
python eagle_eye/pose_receiver.py selftest    # cert + fusion-math check, no phone needed
python eagle_eye/fake_phone.py wss://127.0.0.1:8443/ws fake            # pose burst
WITH_FRAMES=1 python eagle_eye/fake_phone.py wss://127.0.0.1:8443/ws fake  # + synthetic frames
INJECT_DETECTION=1 python eagle_eye/pose_receiver.py                    # full chain demo, no phone
```

## Layout

```
eagle_eye/
  webrtc_client.py     phone app → aiortc → YOLO detection
  signaling_client.py  phone app signaling protocol probe
  pose_receiver.py     WebXR pose+frame receiver, fusion + /world (HTTPS + WSS, one port)
  fusion.py            depth / ray / projection math + in-memory world state
  fake_phone.py        synthetic pose+frame stream for testing
webxr/index.html       the phone-side AR node page
viewer/index.html      world-state viewer (polls /world, sim fallback)
notes/                 session notes, milestones, plans
```
