# Signaling session — 2026-09-11

Client: `eagle_eye/signaling_client.py`
Target: `ws://192.168.1.2:12121/ws`
Camera announced: `back`

## Client → Server

```json
{"type": "camera_ready", "camera": "back", "cam": "back"}
```

## Server → Client

### 1. Immediate ack

```json
{"type": "camera_ready", "camera": "back", "cam": "back"}
```

### 2. Compact status heartbeat (repeated)

```json
{"type": "status", "battery": 20, "charging": true, "is_pro": false}
```

### 3. Full status payload (appeared a few seconds after camera_ready)

```json
{
  "type": "status",
  "usb_connected": true,
  "ip_address": "192.168.1.2",
  "is_pro": false,
  "res_index": 0,
  "fps_index": 0,
  "bitrate_mode_index": 1,
  "bitrate_target_index": 2,
  "zoom": 1.0252,
  "lock_landscape": false,
  "motion_enabled": false,
  "motion_sensitivity_index": 2,
  "idle_timeout_index": 1,
  "idle_quality_index": 0,
  "background_timeout_enabled": false,
  "background_timeout_index": 1,
  "audio_enabled": false,
  "anti_feedback_enabled": false,
  "dual_mode": false,
  "port": "12121",
  "separate_ports": false,
  "ssl_enabled": false,
  "battery": 20,
  "charging": true,
  "current_camera": "back",
  "measured_fps": 29,
  "measured_bitrate": 2500000,
  "current_width": 1280,
  "current_height": 720,
  "clients_connected": 1,
  "power_saver_enabled": false,
  "thermal_throttled": false,
  "in_pocket": true,
  "prefer_h265": false,
  "volume": 1,
  "power_saver_delay_index": 0,
  "thermal_throttle_enabled": true,
  "pocket_detection_enabled": true,
  "accent_color": "#6B35E6",
  "accent_hover_color": "#501BCD",
  "whip_enabled": false,
  "debug_osd_enabled": false,
  "orientation": {
    "pitch": -18.42642593383789,
    "roll": -177.89950561523438,
    "yaw": -148.1046140625,
    "compass": 205.7744140625,
    "mag_strength": 34.559608459472656
  },
  "system_temp": 41,
  "thermal_status": -2147483648,
  "telemetry_interval": 1000,
  "codec": "H264",
  "cpu_usage": 15
}
```

### Notes

- After sending `camera_ready`, the server echoed it back, then streamed status messages.
- The **full status payload** contains sensor orientation (pitch/roll/yaw/compass), stream
  metadata (resolution 1280x720, measured_fps 29, codec H264, bitrate 2.5 Mbps), and
  connection info (`clients_connected: 1`, `port: 12121`).
- No `offer`/`answer`/`candidate` messages were observed in this run. The server likely
  waits for an incoming WebRTC offer from the client, or the browser's offer happened
  after the `camera_ready` step and is triggered by a separate flow.
- The `current_camera` field switched from `front` (earlier heartbeat) to `back` after
  the client announced `back`, which suggests the phone can acknowledge camera selection.

## Next step

Figure out how the server expects the **client to initiate the WebRTC offer**, or whether
the server pushes an offer to the client. Implement that exchange in `aiortc` next.
