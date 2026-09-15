# Eagle Eye — Mac test guide

The PC build is done and self-tested (fusion math + full offline pipeline
pass). This is the exact sequence to run it on the Mac, start to finish.

## 1. One-time setup on the Mac

```bash
cd eagle-eye
python3 -m pip install -r requirements.txt
python eagle_eye/pose_receiver.py selftest
```

Expect: `selftest OK: fusion math (round-trip, cross-camera, behind-camera)
+ cert generation`.

If `cert.pem`/`key.pem` came along in the copy, keep them — the phone trust
step only needs doing once per cert. If they're missing, selftest regenerates
them (then phones must re-trust the new cert).

## 2. Find the Mac's IP

```bash
ipconfig getifaddr en0
```

Say it prints `192.168.1.20`. Everything below uses that.

## 3. Start the server

```bash
python eagle_eye/pose_receiver.py
```

Leave it running. Note macOS may show a firewall prompt on first run —
click **Allow** so phones can reach it.

## 4. Connect phones (no install, just Chrome)

On each Android phone on the **same Wi-Fi**, open in Chrome:

```
https://192.168.1.20:8443/?name=cam1
```

Second phone uses `?name=cam2`, third `?name=cam3`.

- Chrome shows a privacy warning (self-signed cert) → **Advanced** →
  **Proceed**. This is the "one tap to trust" — it is per phone, per cert,
  and only because we don't have a paid HTTPS certificate.
- Tap **camera + pose** (both features stream; the other button is pose-only).
- The Mac console should print `x=... y=... z=...` lines and pose FPS.

If nothing connects: **System Settings → Wi-Fi → Details** and check both
devices are on the same network; iOS devices must stay off that Wi-Fi
(they'd grab the `cam` names otherwise — actually they can't run the page,
but keep the network clean anyway).

## 5. Watch the world state

Two ways, both from any browser (laptop or the Mac itself):

- Raw JSON: `https://192.168.1.20:8443/world` (proceed past the same cert
  warning once).
- Visual: `viewer/index.html` isn't served by the receiver (it only serves
  the phone page), so open the file directly in a browser on the Mac
  (double-click it). It polls `https://<mac-ip>:8443/world` — accept the
  cert warning if asked — and falls back to its simulation when nothing is
  live.

## 6. The actual test (the milestone moment)

1. One person holds a phone in AR (**camera + pose**) and points it at a
   second person standing 2–4 m away.
2. Watch the Mac console: a track should appear on `/world` with sane
   x/y/z that moves as the tracked person walks.
3. A second phone in AR pointed the same direction shows the **red X** on
   its OpenCV window on the Mac (EE_SHOW=1) — the in-view cross-camera
   marker.
4. Walk the tracked person behind you / off-frame; the track should hold
   briefly (age) then drop.

## 7. Latency + FPS numbers to collect

The receiver prints pose FPS and clock-synced latency per camera. Write
down, per phone:

- pose FPS (want ≥ 25)
- rtt (want < 150 ms on decent Wi-Fi)
- rough end-to-end feel: walk and see the track follow.

## 8. If something's off

| Symptom | Likely cause | Fix |
|---|---|---|
| Port already in use | old receiver still running | kill it, restart |
| Phone can't reach page | different Wi-Fi / firewall | same network, Allow on prompt |
| Track coordinates nonsense | camera pose not yet AR-locked | wave phone slowly, re-enter AR |
| No detections | person too far / small in frame | get within 2–4 m, `YOLO_CONF=0.25` |
| Red X in wrong place | FOV guess is off | noted limitation; fix later with real intrinsics |

## 9. GitHub

The folder is not a git repo yet. After testing works:

```bash
cd eagle-eye
git init && git add -A && git commit -m "Eagle Eye working prototype"
```

`.gitignore` already excludes certs, `__pycache__`, frames, and logs — check
`git status` before pushing and keep `cert.pem`/`key.pem` out of the repo if
you want the phone trust step to survive clones (generate fresh ones per
machine instead).
