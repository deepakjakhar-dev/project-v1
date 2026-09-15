# Eagle Eye — Session Summary & Roadmap

*Written: 2026-09-11. This is the single document to read after a break: everything
discussed, everything proven, and exactly what comes next.*

---

## 1. What Eagle Eye is

Three friends wear three Android phones (chest/hand mounts). Each phone streams
its **camera view** and its **ARCore 3D position** to a central PC (moving to an
M4 MacBook Air). When one friend sees a person ("enemy"), every *other* friend's
screen shows a **red X at that person's true 3D location** — and if a wall
blocks the view, the X lands **on the wall** in the person's direction, like a
shadow cast by a flashlight.

Key constraint chosen by the team: **zero configuration** — no markers, no tape
measures, must work in any room instantly.

---

## 2. Everything proven so far (with dates)

### Milestone 1 — WebRTC video pipeline (proven)
- Phone streaming app → `ws://192.168.1.2:12121/ws` signaling → `aiortc` on PC
- Phone sends WebRTC offer (usually); PC answers and receives H264 (payload 101)
- Sustained **25.6 FPS** decode to numpy on the Dell (CPU-only), zero drops
- `eagle_eye/webrtc_client.py`, notes in `notes/MILESTONE_1_COMPLETE.md`

### YOLO person detection (proven)
- YOLOv8n, `conf≥0.35`, persons only, **latest-wins detector thread**
  (`LatestFrame` slot) so a slow detector never builds lag
- Live log every 0.5 s: `persons=N best conf=0.xx bbox=(...) infer 15 fps`
- ~15 infer-FPS on the Dell CPU; window overlay with boxes (press q to quit)

### WebXR pose streaming (proven — the localization breakthrough)
- `webxr/index.html` served by `eagle_eye/pose_receiver.py` over HTTPS+WSS (port 8443)
- Chrome on Android streams **ARCore x/y/z + quaternion** as JSON at ~30 FPS
- Camera frames also stream (~10 FPS, 320px JPEG) in "camera+pose" mode
- **Two phones simultaneously** (cam1 192.168.1.2, cam2 192.168.1.10) verified
- `y` values ≈ +1.2–1.6 m — phone height above floor, physically correct
- Height reading = the floor where each AR session *started* (per-phone origin)

### Instrumentation (live)
- Heartbeats, per-node pose FPS (5 s window), clock-sync one-way latency
  (NTP-style: best/lowest-RTT sync sample wins, median latency, ± uncertainty)
- `/time` endpoint on the server for clock sync
- `fake_phone.py` sends a synthetic walk for testing without a phone

### Hardware facts that shaped decisions
- Dell: Intel UHD 620, torch CPU-only → YOLO ~15 FPS, depth models not viable
- **MacBook Air M4 2025** available → MPS/Metal torch will be several × faster,
  makes depth-anything keyframe experiments viable later

---

## 3. Debug battles won (so we don't re-fight them)

| Symptom | Root cause | Fix |
|---|---|---|
| Phone showed raw HTML code | receiver sent `Content-Type: text/plain` | proper `text/html` Response object |
| Port 8443 busy at startup | stale server holding the port | kill by PID; receiver now prints a clear message |
| `pose: NO` forever, camera granted | missing `updateRenderState({baseLayer})` | set XRWebGLLayer after makeXRCompatible |
| Poses null in some configs | reference space quirks | fallback chain local-floor → local → viewer |
| `±44400` uncertainty nonsense | sync sent ms, server read seconds | everything in seconds on the wire |
| Latency line never printed | skewed sync samples filtered to death | clamp ≥0, median of last 50, best-RTT offset |
| cam1 fps dipped to 0.8 | Chrome throttles backgrounded AR page | keep page foreground during demos |

WebXR requirements: HTTPS (self-signed cert, one trust tap per phone), Chrome
on Android, one tap "Enter AR", move phone gently at start for ARCore lock.

---

## 4. Architecture decisions (and why)

- **WebXR page instead of custom ARCore app**: no install, no SDK, works today.
  Custom app remains the accuracy upgrade path (~weeks of work) — not needed yet.
- **Pose and video are separate channels** (WebXR JSON + phone app WebRTC):
  they will merge in fusion; both are independently proven.
- **Latest-wins detection**: newest frame always wins; stale frames skipped.
  Scales to 3 cameras on weak hardware.
- **Monocular depth first** (`Z = fy × 1.7 m / bbox_height_px`): ±20%, enough
  for "roughly this position". Triangulation adds precision when 2 cams see
  the same person; people-as-rulers anchors scale without any calibration.
- **Cameras need not be stationary**: pose recomputed every frame from ARCore.
- **Depth Pro / heavy AI depth**: shelved — needs datacenter GPU. Depth-anything
  small on M4 Mac is the later scene-mapping option (walls, doorways).

---

## 5. What is NOT built yet (honest list)

1. **Fusion engine** — YOLO on WebXR frames × pose → per-person 3D world tracks.
   All inputs are proven; the engine itself is not written.
2. **Cross-camera red-X overlay** — project a person's 3D point into every other
   camera's view; draw X; wall behavior falls out of projection; off-screen arrow.
3. **Shared world-state broadcast** — JSON out to `viewer/index.html` (mock exists).
4. **Person identity across cameras** — v1 nearest-ray matching; ReID model later.
5. **Friend vs enemy distinction** — v1 marks all people.
6. **Mac migration** — folder is portable now; git push/pull or copy.
7. **GitHub repo** — ready to init; `.gitignore` covers certs/frames/weights.

---

## 6. Next steps, in order

### Step A — Fusion engine (next work session)
- Subscribe to `pose` + `frame` streams in `pose_receiver.py`
- Run YOLOv8n on incoming WebXR frames (reuse the proven latest-wins Detector)
- Convert bbox → direction ray using the pose quaternion (camera intrinsics:
  start with estimated FOV ~65°, refine later)
- Depth from bbox height (1.7 m humans), 3D point = pose position + ray × depth
- Maintain tracks: nearest-neighbor matching with distance gate + simple Kalman
- Output: `WorldTrack {id, x, y, z, conf, seen_by[], last_seen}` in memory
- **Test**: one person walks; their 3D dot stays stable from two phones

### Step B — Minimap (quick, high value)
- Top-down 2D OpenCV/matplotlib window: phone dots (from pose) + person dots
  (from fusion). The fastest way to *see* the world state is correct.

### Step C — Red-X overlay (the headline feature)
- For each camera: project each track's 3D point into that camera's image
- Person visible → X on them; wall in between → X lands on wall automatically
  (ray camera→person hits wall plane first; wall geometry optional at first —
  the X at the person's projected position reads correctly through the wall)
- X size ∝ 1/distance; label `PERSON ~3.2 m`; off-screen edge arrow
- Draw on the WebXR video windows (OpenCV) and broadcast for the viewer page

### Step D — Polish & share
- Shared world state broadcast → `viewer/index.html` live data
- README updates, latency/fps table from a clean 3-phone run
- Multi-room note: AR origins are per-session; rooms fuse via co-visible people

### Later / optional
- Custom ARCore Android app (video+pose in one, higher accuracy)
- ReID for friend-vs-enemy and robust cross-camera identity
- Depth-anything scene mapping on the M4 for wall planes
- Recording & replay for offline debugging

---

## 7. How to run everything (cheat sheet)

```bash
# PC/Mac — the two servers
python eagle_eye/pose_receiver.py          # WebXR pose+frames, port 8443
python eagle_eye/webrtc_client.py          # phone-app video + YOLO detection

# Phone (Chrome on Android, same Wi-Fi)
#   https://<pc-ip>:8443/?name=cam1   (cam2, cam3 …)
#   → trust tap → Enter AR → keep page foreground

# Tests without a phone
python eagle_eye/pose_receiver.py selftest
python eagle_eye/fake_phone.py wss://127.0.0.1:8443/ws fake

# Flags
EE_PORT=8443  EE_SHOW=1  SAVE_FRAMES=1  SHOW_WINDOW=1  YOLO_CONF=0.35
```

## 8. GitHub — what to upload

Upload the whole `eagle-eye/` folder. `.gitignore` already excludes:
`cert.pem`, `key.pem`, `frames/`, `*.pt`, `__pycache__/`, `.selftest_*`.

After cloning (Mac):

```bash
cd eagle-eye
pip install -r requirements.txt
python eagle_eye/pose_receiver.py
```

## 9. Known success criteria met so far

- ✅ One phone → WebRTC → Python → live frames, very low latency (M1 goal)
- ✅ Person detection with confidence, live on PC
- ✅ Phone 3D self-localization streamed continuously to PC (WebXR)
- ✅ Two phones at once, ~30 FPS pose, working telemetry
- ⬜ Person located in shared 3D room space (Step A)
- ⬜ Red X visible on every other camera (Step C — the Eagle Eye moment)
