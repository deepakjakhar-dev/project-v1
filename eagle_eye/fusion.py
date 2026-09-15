"""Eagle Eye — fusion math and shared world state.

Turns a detection (bbox) on a camera frame, combined with that camera's AR
pose, into a single 3D point in meters (in that camera's local coordinate
system). Then projects that point into every other camera's image so a marker
can be drawn where the person appears in their view.

Design notes:
- One detecting camera is the source of truth for that person. No triangulation.
- Monocular depth from person height (1.7 m) is the working depth today.
- No shared alignment walk. Cross-camera projection uses each phone's own
  pose; the shared-room coherence comes from the floor/horizon cue that ARCore
  already gives each phone (local-floor reference space).
- Marker is drawn only when the projected point is inside the other camera's
  image. Wall behavior falls out of ordinary projection: if a wall is in that
  direction, the marker visually lands on it.
- This module does NOT import OpenCV, ultralytics, or any heavy runtime dep
  at module level; it only uses stdlib math so it can be imported freely.

Kept deliberately separable so the frame source can later switch from WebXR
frames to WebRTC frames without touching this math.

Convention (matches what the receiver viewer path uses):
  camera-local: +X right, +Y down, +Z forward out of the camera.
  floor is the ARCore local-floor plane (Y is up in the world pose reported
  by the phone).
"""

from __future__ import annotations

import math
import time as _time_mod
from dataclasses import dataclass, field
from typing import Any

# ----------------------------------------------------------------------
# Camera intrinsics (estimate)
# ----------------------------------------------------------------------
# We do not have a calibrated focal length per phone. Start with a reasonable
# horizontal FOV (~65 deg) and derive an equivalent focal length in pixels.
# Refine later if phones report intrinsics or we calibrate.
#
# We treat the image as square-ish for the depth math: use the smaller
# dimension to be conservative (we estimate distance, and over-confidence is
# worse than a slightly conservative number).
#
# f = (h/2) / tan(fov/2)  ->  focal length in pixels for that dimension

ESTIMATED_H_FOV_DEG = 65.0  # conservative default
_PERSON_HEIGHT_M = 1.7


def focal_px_for(img_h: int, img_w: int, fov_deg: float = ESTIMATED_H_FOV_DEG) -> tuple[float, float]:
    """Focal lengths (px) along X and Y from an assumed horizontal FOV.

    The receiver viewer path and the fusion projection both use the same
    formula here so the two projections agree. The height-axis focal length
    is derived from the FOV; the width-axis focal length scales with the
    image aspect ratio.
    """
    h_fov = math.radians(fov_deg)
    f_from_h = (img_h / 2.0) / math.tan(h_fov / 2.0)
    f_from_w = f_from_h * (img_w / img_h)
    return f_from_w, f_from_h


# ----------------------------------------------------------------------
# Camera pose helpers (quaternion -> matrix)
# ----------------------------------------------------------------------


def _quat_to_matrix(qx: float, qy: float, qz: float, qw: float) -> list[list[float]]:
    """Rotation matrix from a unit quaternion (x,y,z,w)."""
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if n < 1e-9:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]


def _mat_vec_mul(m: list[list[float]], v: list[float]) -> list[float]:
    return [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]


def _mat_transpose(m: list[list[float]]) -> list[list[float]]:
    return [[m[r][c] for r in range(len(m))] for c in range(len(m[0]))]


def _inverse_pose(
    pos: list[float], rot: list[list[float]],
) -> tuple[list[float], list[list[float]]]:
    """Camera-frame -> world is (pos, rot). World -> camera is (-R^T*pos, R^T)."""
    rot_t = _mat_transpose(rot)
    cam_pos = _vec_neg(_mat_vec_mul(rot_t, pos))
    return cam_pos, rot_t


def _vec_neg(v: list[float]) -> list[float]:
    return [-x for x in v]


# ----------------------------------------------------------------------
# Depth
# ----------------------------------------------------------------------


def person_depth_from_bbox_height(
    bbox_h_px: int, img_h: int, img_w: int, fov_deg: float = ESTIMATED_H_FOV_DEG
) -> float:
    """Estimate distance to a person from their bounding-box height.

    Assumes the detected person is roughly _PERSON_HEIGHT_M tall, standing,
    and roughly upright in the image. Returns meters from the camera.

    This is the working depth for today. It is approximate (±20% is typical)
    and gets worse for very small or very tilted boxes; callers should clamp
    and sanity-check.
    """
    if img_h <= 0 or img_w <= 0 or bbox_h_px <= 0:
        return 0.0
    h_fov = math.radians(fov_deg)
    # focal length in pixels along the height axis
    f = (img_h / 2.0) / math.tan(h_fov / 2.0)
    # distance = (real_height * f) / projected_height
    return (_PERSON_HEIGHT_M * f) / float(bbox_h_px)


# ----------------------------------------------------------------------
# Ray from camera center through a pixel
# ----------------------------------------------------------------------


def pixel_to_ray(
    px: int,
    py: int,
    img_w: int,
    img_h: int,
    fov_deg: float = ESTIMATED_H_FOV_DEG,
) -> list[float]:
    """Unit ray (camera-local) from the camera center through image pixel (px,py).

    Camera convention here: +X right, +Y down, +Z forward (out of the camera).
    """
    if img_w <= 0 or img_h <= 0:
        return [0.0, 0.0, 1.0]
    fx, fy = focal_px_for(img_h, img_w, fov_deg)
    cx, cy = img_w / 2.0, img_h / 2.0
    x = (px - cx) / fx
    y = (py - cy) / fy
    n = math.sqrt(x * x + y * y + 1.0)
    return [x / n, y / n, 1.0 / n]


# ----------------------------------------------------------------------
# World point from detection + pose
# ----------------------------------------------------------------------

# bbox in image pixels; center of the box is used as the sighting direction.


def detection_to_world_point(
    bbox_x: int,
    bbox_y: int,
    bbox_w: int,
    bbox_h: int,
    img_w: int,
    img_h: int,
    pose: dict[str, Any],
    fov_deg: float = ESTIMATED_H_FOV_DEG,
) -> dict[str, Any]:
    """Return a 3D point (meters) for a detection in the detecting camera's
    local coordinate system.

    pose must carry: x,y,z (meters) and qx,qy,qz,qw (unit quaternion).
    The returned point is in the same local frame as the pose (camera at
    origin, +Z forward by construction here), so it is effectively
    `pose.position + forward * depth`.
    """
    cx = bbox_x + bbox_w / 2.0
    cy = bbox_y + bbox_h / 2.0
    depth = person_depth_from_bbox_height(int(bbox_h), img_h, img_w, fov_deg)
    depth = max(0.3, min(depth, 30.0))  # sanity clamp
    ray = pixel_to_ray(int(cx), int(cy), img_w, img_h, fov_deg)
    # Camera-local convention: +Z forward out of the camera. So a point at
    # depth D in direction `ray` is  camera_pose + ray * D in world coords.
    wx = pose["x"] + ray[0] * depth
    wy = pose["y"] + ray[1] * depth
    wz = pose["z"] + ray[2] * depth
    return {
        "x": wx,
        "y": wy,
        "z": wz,
        "depth_m": depth,
        "from_bbox_center": [cx, cy],
        "fov_deg": fov_deg,
    }


# ----------------------------------------------------------------------
# Projection into another camera's image
# ----------------------------------------------------------------------


def world_to_pixel(
    wx: float,
    wy: float,
    wz: float,
    cam_pose: dict[str, Any],
    img_w: int,
    img_h: int,
    fov_deg: float = ESTIMATED_H_FOV_DEG,
) -> dict[str, Any] | None:
    """Project a world point (meters) into a camera's image.

    World frame is defined as the detecting camera's local frame (see
    detection_to_world_point). Each other camera has its own pose; to project
    consistently without a shared alignment walk, we treat each camera as if
    its local frame is 'the world' for its own view — i.e. we project relative
    to that camera using the vector from its pose to the point, expressed in
    the camera's +Z-forward frame.

    Returns None when the point is behind the camera or off-screen.
    """
    # vector from this camera to the point, in world (detecting cam) frame
    dx = wx - cam_pose["x"]
    dy = wy - cam_pose["y"]
    dz = wz - cam_pose["z"]
    rot = _quat_to_matrix(cam_pose["qx"], cam_pose["qy"], cam_pose["qz"], cam_pose["qw"])
    # rot is local->world (camera orientation). World->local is rot^T.
    # Transpose to get the vector into this camera's local frame (+Z forward).
    rot_t = [[rot[r][c] for r in range(3)] for c in range(3)]
    local = _mat_vec_mul(rot_t, [dx, dy, dz])
    if local[2] <= 0.05:  # behind or too close to the camera plane
        return None
    fx, fy = focal_px_for(img_h, img_w, fov_deg)
    cx, cy = img_w / 2.0, img_h / 2.0
    x = local[0] / local[2] * fx + cx
    y = local[1] / local[2] * fy + cy
    if x < -50 or x > img_w + 50 or y < -50 or y > img_h + 50:
        return None
    return {
        "u": x,
        "v": y,
        "img_w": img_w,
        "img_h": img_h,
        "behind": local[2] <= 0.05,
    }


# ----------------------------------------------------------------------
# Shared world state
# ----------------------------------------------------------------------


@dataclass
class WorldTrack:
    """One person currently tracked in the shared 3D view."""

    id: str
    # current best estimate (meters, in the detecting camera's local frame)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # last reporting camera + its pose at that moment
    cam: str = ""
    pose: dict[str, Any] = field(default_factory=dict)
    # detection confidence of the detection that produced this point
    conf: float = 0.0
    # how recently this track was updated (seconds)
    last_seen_s: float = 0.0
    # which cameras have reported a projection of this track (for display)
    seen_by: list[str] = field(default_factory=list)


@dataclass
class CameraState:
    """Latest known info for one camera node."""

    name: str
    # AR pose (latest)
    pose: dict[str, Any] = field(default_factory=dict)
    # latest camera frame (BGR numpy) if available
    frame: Any = None
    img_w: int = 0
    img_h: int = 0


class WorldState:
    """In-memory shared world state. Thread-safe for the receiver's writer
    thread and the reader/broadcast path."""

    def __init__(self) -> None:
        self.cams: dict[str, CameraState] = {}
        self.tracks: dict[str, WorldTrack] = {}
        self._next_id = 0
        self.mutex = None  # set by the receiver (threading.Lock)

    # -- camera state --------------------------------------------------

    def update_cam(self, name: str, pose: dict[str, Any]) -> None:
        st = self.cams.setdefault(name, CameraState(name=name))
        st.pose = pose

    def update_frame(self, name: str, frame: Any, img_w: int, img_h: int) -> None:
        st = self.cams.setdefault(name, CameraState(name=name))
        st.frame = frame
        st.img_w = img_w
        st.img_h = img_h

    def cam_pose(self, name: str) -> dict[str, Any] | None:
        st = self.cams.get(name)
        return st.pose if st else None

    def cam_frame(self, name: str) -> tuple[Any, int, int]:
        st = self.cams.get(name)
        if st is None or st.frame is None:
            return None, 0, 0
        return st.frame, st.img_w, st.img_h

    # -- tracks ---------------------------------------------------------

    def update_track_from_detection(
        self,
        name: str,
        detection: dict[str, Any],
        pose: dict[str, Any],
        img_w: int,
        img_h: int,
        now_s: float,
    ) -> WorldTrack:
        """Create or update the track for a detection reported by camera `name`."""
        wp = detection_to_world_point(
            int(detection["x"]),
            int(detection["y"]),
            int(detection["w"]),
            int(detection["h"]),
            img_w,
            img_h,
            pose,
        )
        # find an existing track close to this point (nearest neighbor)
        best = None
        best_d = 1e9
        for t in self.tracks.values():
            d = math.sqrt((t.x - wp["x"]) ** 2 + (t.y - wp["y"]) ** 2 + (t.z - wp["z"]) ** 2)
            if d < best_d:
                best_d = d
                best = t
        if best is not None and best_d < 1.5:  # meters; simple gate
            best.x = wp["x"]
            best.y = wp["y"]
            best.z = wp["z"]
            best.pose = pose
            best.cam = name
            best.conf = detection.get("conf", 0.0)
            best.last_seen_s = now_s
            if name not in best.seen_by:
                best.seen_by.append(name)
            return best
        tid = f"p{self._next_id}"
        self._next_id += 1
        trk = WorldTrack(
            id=tid,
            x=wp["x"],
            y=wp["y"],
            z=wp["z"],
            cam=name,
            pose=pose,
            conf=detection.get("conf", 0.0),
            last_seen_s=now_s,
            seen_by=[name],
        )
        self.tracks[tid] = trk
        return trk

    def prune(self, now_s: float, max_age_s: float = 4.0) -> None:
        dead = [tid for tid, t in self.tracks.items() if now_s - t.last_seen_s > max_age_s]
        for tid in dead:
            del self.tracks[tid]

    def projection_for(
        self, track: WorldTrack, viewer_name: str
    ) -> dict[str, Any] | None:
        """Where does `track` appear in `viewer_name`'s camera image?

        Uses the viewer's latest pose. Returns None when the point is off-screen
        or behind that camera.
        """
        pose = self.cam_pose(viewer_name)
        if not pose:
            return None
        _, img_w, img_h = self.cam_frame(viewer_name)
        if img_w <= 0 or img_h <= 0:
            # no frame yet for this camera; can still project geometry, but prefer
            # a known image size for the on-screen test. Use a default if absent.
            img_w, img_h = max(img_w, 640), max(img_h, 480)
        return world_to_pixel(track.x, track.y, track.z, pose, img_w, img_h)

    def snapshot(self) -> dict[str, Any]:
        """Thread-safe snapshot of tracks + cameras for broadcast."""
        if self.mutex:
            self.mutex.acquire()
        try:
            cams = {
                name: {
                    "pose": dict(st.pose),
                    "frame": None,
                }
                for name, st in self.cams.items()
            }
            tracks = [
                {
                    "id": t.id,
                    "x": t.x,
                    "y": t.y,
                    "z": t.z,
                    "conf": t.conf,
                    "cam": t.cam,
                    "last_seen_s": t.last_seen_s,
                    "seen_by": list(t.seen_by),
                }
                for t in self.tracks.values()
            ]
            return {"cams": cams, "tracks": tracks, "t": _time_mod.time(), "n_cams": len(cams)}
        finally:
            if self.mutex:
                self.mutex.release()

    def count(self) -> int:
        return len(self.tracks)


# threading is required by the receiver for the snapshot mutex.
import threading
