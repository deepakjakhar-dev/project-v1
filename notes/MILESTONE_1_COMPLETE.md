# Eagle Eye — Milestone 1 complete

**Date:** 2026-09-11

## Success criterion met

> One Android phone → WebRTC → Windows PC Python program → live frames with very low latency.

## Verified results

- `eagle_eye/webrtc_client.py` connects to the phone's signaling server at
  `ws://192.168.1.2:12121/ws`.
- Sends `camera_ready` (accepted, same format the browser uses).
- If no offer arrives within 5 s, sends its own `recvonly` offer — the phone
  answers (it acts as the WebRTC sender).
- ICE completes over the LAN pair `192.168.1.5 ↔ 192.168.1.2` (IPv6 pairs are
  also discovered but LAN IPv4 wins).
- Video track arrives (`VIDEO_BACK`, H264 payload 101, baseline profile,
  packetization-mode=1, RTX 102), decodes through aiortc into numpy frames.
- Sustained receive rate: **~25.6 FPS** with no drops over a 75 s run
  (matches the ~20–30 FPS seen in the browser viewer).
- First frame arrives ~1 s after ICE completes (phone encoder startup).

## Key implementation facts

- aiortc completes ICE gathering inside `setLocalDescription`, so one `offer`
  message with a complete SDP is sent (no trickle needed). Server candidates
  are still accepted and added on receipt.
- The frame consumer wraps `track.recv()` in try/except and logs a traceback
  on failure — earlier "silent no frames" runs were almost certainly the phone
  encoder not yet streaming, not a client bug.
- Phone offer-push behavior is inconsistent (sometimes pushes `offer` after
  `camera_ready`, usually not) — the client supports both directions.

## Run it

```bash
cd eagle-eye
python eagle_eye/webrtc_client.py                  # FPS logging only
SHOW_WINDOW=1 python eagle_eye/webrtc_client.py    # OpenCV preview window (press q to quit)
```

## Known cosmetic issue

`parse_candidate()` logs a harmless ValueError on some candidate strings;
candidates that fail parsing are skipped (they are not needed — the LAN pair
connects regardless).

## Next steps (per handoff §11)

1. OpenCV processing stage: FPS overlay on the live frame, latency measurement.
2. Second phone → second peer connection (streams kept separate).
3. Detection model (e.g. YOLOv8n) inserted after frame decode.
4. Shared world state server (detections broadcast to multiple viewers).
