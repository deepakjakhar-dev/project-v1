# Eagle Eye — fusion build note (2026-09-11)

Purpose: turn the proven pieces (pose stream, WebXR camera frames, YOLOv8n
person detection) into a single 3D world point per detected person, then
project that point into the other cameras' views. Marker is drawn only when
the projected point actually lands in a camera's image. No scanning, no
walk-around alignment, no 2-camera triangulation — one detecting camera is
the source of truth for that person.

Depth model decision:
- Working depth now = monocular person-height depth from the detected bbox.
  A standing person is roughly 1.7 m tall; how tall they appear in the image
  gives distance in meters. Free, live, and "roughly this position".
- Heavy Apple Depth-Pro-style models are NOT used live here. They need
  datacenter GPU and are the wrong tool for "where is this one person".
  Kept as a later optional scene-mapping layer (walls) on the M4, not a
  person-distance source.
- Lightweight monocular depth model (e.g. Depth Anything small) is NOT wired
  now. The plan is to keep one clean depth interface in fusion.py so a model
  can be plugged in later without touching the rest. Not shipped today.

Shared coordinate decision (no alignment walk):
- Each phone keeps its own AR origin. No cooperation step.
- For cross-camera projection, each phone's reported floor height + yaw
  (from the pose quaternion) is the only shared signal. Approximate between
  phones by construction. That is the stated goal: approximate position,
  marker on the wall they're looking at.
- Projection is "in view or not" only today. If the point is off-screen for
  another camera, no marker. No off-screen arrow until asked for.

Detection source for this build:
- YOLO runs on the WebXR frames arriving in pose_receiver.py (320px JPEG,
  ~10 FPS). That is the frame source this build uses. webrtc_client.py is
  untouched and continues to own the higher-quality WebRTC video path.
- The fusion module is written so the frame source is swappable later (WebXR
  frames now, WebRTC frames via an adapter later) without rewriting the math.

Files changed in this build:
- eagle_eye/fusion.py         (new)  depth + ray + world point + projection
- eagle_eye/pose_receiver.py  (edit) subscribe to frames, run detector, build
                                     world state, broadcast JSON
- eagle_eye/viewer/index.html (edit) consume the broadcast as real data with
                                     the simulation as fallback
