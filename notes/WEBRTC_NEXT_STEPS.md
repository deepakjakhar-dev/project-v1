# WebRTC next steps — decision log

## What worked in this session

- Python `websockets` client connected to `ws://192.168.1.2:12121/ws`.
- Sent `camera_ready`; server echoed it and began streaming status.
- Full status payload captured: resolution 1280x720, fps 29, codec H264, orientation present.

## What we still don't know

1. **Who initiates the WebRTC offer?**
   - Browser logs showed `offer` from the *client side* and `answer` from the server side.
   - In this Python run, nothing SDP-related arrived after `camera_ready`.
   - Either the browser sent an offer immediately after `camera_ready` (and our replay
     needs to do the same), or the server expects a slightly different trigger.
2. **Are SDP/ICE exchanged inside the same WebSocket, or on a separate channel?**
   - Browser DevTools showed the WebSocket carrying `offer`, `answer`, `candidate`.
   - So our Python client should be able to send an offer here too — we just need to
     build one with `aiortc` and forward it as JSON.

## Recommended next action

Build a second script: `eagle_eye/webrtc_client.py` that:

1. Connects to the same WebSocket.
2. Sends `camera_ready` (reuse `signaling_client.py` logic).
3. Creates an `aiortc` `RTCPeerConnection`, adds a dummy/placeholder video track
   (or none yet), and generates an offer.
4. Sends that offer through the WebSocket in the same shape the browser used:

```json
{
  "type": "offer",
  "offer": { "type": "offer", "sdp": "..." },
  "cam": "back"
}
```

5. Listens for `answer` and `candidate` messages from the server and feeds them into
   the `RTCPeerConnection`.
6. Once the connection is `connected`, attach a `MediaStreamTrack` that consumes the
   remote video and hands frames to OpenCV.

## Open questions for the user

- Should the offer be generated with **no local track** (audio/video) and only the remote
  track added later, or do you want a preview window from the Python side too?
- Do you want the `aiortc` stage to also replay the same `camera_ready` format exactly,
  or widen it (e.g., add a device ID)? The server accepted the current minimal format.
- Once the single-phone loop works, do you want the server to support multiple clients
  on the same WebSocket, or should each phone get its own connection/camera name?

## Best-latency choices to keep

- `aiortc` over custom UDP — it's the lowest-latency Python WebRTC option available here.
- 1280x720 @ 29 fps is already labeled as acceptable for the prototype; no need to push
  for 1080p yet.
- Keep OpenCV processing minimal at first (frame show + FPS overlay), then add detection.
