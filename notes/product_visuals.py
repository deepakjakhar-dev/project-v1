"""
product_visuals.py
Zero-UI vector drawing tool for the Eagle Eye pitch deck.

Every visual is produced from pure geometry in PIL — no screenshots, no
external assets except the one embedded 3x5 camera-grid png.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Palette — all colors in one place so the deck reads as one cohesive system
# ---------------------------------------------------------------------------
PALETTE = {
    "bg_dark":      (12, 18, 20),
    "bg_slate":     (22, 30, 34),
    "panel":        (28, 37, 41),
    "panel_soft":   (34, 45, 50),
    "line":         (64, 78, 84),
    "line_soft":    (48, 60, 66),
    "text":         (201, 214, 217),
    "text_dim":     (143, 160, 166),
    "gold":         (255, 176, 32),
    "gold_dim":     (190, 132, 24),
    "crimson":      (255, 69, 58),
    "crimson_dim":  (178, 48, 40),
    "signal_blue":  (66, 206, 240),
    "signal_blue2": (42, 142, 172),
    "teal":         (45, 199, 185),
    "green":        (52, 207, 148),
    "amber":        (255, 176, 32),
    "warm_bg":      (232, 214, 186),
    "paper":        (248, 242, 229),
    "ink":          (32, 30, 28),
    "ink_soft":     (80, 72, 62),
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Prefer a system sans; fall back to the default at the given size."""
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "segoeui.ttf" if bold else "seguilight.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ff(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Fallback font (default) with weight indication."""
    return _font(size, bold)


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def rounded_rect(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
                 radius: int, fill: Optional[Tuple[int, int, int]],
                 outline: Optional[Tuple[int, int, int]] = None,
                 width: int = 1) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(
        [x0, y0, x1, y1], radius=radius, fill=fill,
        outline=outline, width=width,
    )
    return (x0, y0, x1, y1)


def line(draw: ImageDraw.ImageDraw, p0: Tuple[int, int], p1: Tuple[int, int],
         color: Tuple[int, int, int], width: int = 1) -> None:
    draw.line([p0, p1], fill=color, width=width)


def dash(draw: ImageDraw.ImageDraw, p0: Tuple[int, int], p1: Tuple[int, int],
         color: Tuple[int, int, int], dash_len: int = 10, gap: int = 7,
         width: int = 1) -> None:
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist <= 0.5:
        return
    ux, uy = dx / dist, dy / dist
    pos = 0
    draw_first = True
    while pos < dist:
        x = p0[0] + ux * pos
        y = p0[1] + uy * pos
        nx = p0[0] + ux * min(pos + dash_len, dist)
        ny = p0[1] + uy * min(pos + dash_len, dist)
        if draw_first:
            line(draw, (x, y), (nx, ny), color, width)
            draw_first = False
        else:
            line(draw, (x, y), (nx, ny), color, width)
        pos += (dash_len + gap)


def arc(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
        start: float, end: float, color: Tuple[int, int, int],
        width: int = 1, ellipse: bool = True) -> None:
    if ellipse:
        draw.arc(box, start=start, end=end, fill=color, width=width)
    else:
        draw.pieslice(box, start=start, end=end, fill=None, outline=color,
                      width=width)


def ellipse(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
            fill: Optional[Tuple[int, int, int]] = None,
            outline: Optional[Tuple[int, int, int]] = None, width: int = 1) -> None:
    draw.ellipse(box, fill=fill, outline=outline, width=width)


def polygon(draw: ImageDraw.ImageDraw, pts: List[Tuple[float, float]],
            fill: Optional[Tuple[int, int, int]],
            outline: Optional[Tuple[int, int, int]] = None, width: int = 1) -> None:
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def text_centered(draw: ImageDraw.ImageDraw, center: Tuple[float, float],
                  s: str, color: Tuple[int, int, int], font: ImageFont.FreeTypeFont,
                  anchor: str = "mm") -> None:
    draw.text(center, s, font=font, fill=color, anchor=anchor)


def text_box(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
             s: str, color: Tuple[int, int, int], font: ImageFont.FreeTypeFont,
             align: str = "left", max_lines: int = 0, line_gap: int = 4) -> None:
    x0, y0, x1, y1 = box
    w = x1 - x0
    avail = y1 - y0
    words = s.split(" ")
    lines: List[str] = []
    cur: List[str] = []
    for w_ in words:
        trial = " ".join(cur + [w_])
        bw, bh = draw.textbbox((0, 0), trial, font=font)[2:]
        if bw > w and cur:
            lines.append(" ".join(cur))
            cur = [w_]
        else:
            cur.append(w_)
    if cur:
        lines.append(" ".join(cur))
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    lh = draw.textbbox((0, 0), "Ay", font=font)[3] + line_gap
    y = y0
    for ln in lines:
        if align == "center":
            draw.text((x0 + w / 2, y + lh / 2), ln, font=font, fill=color, anchor="mm")
        elif align == "right":
            draw.text((x1, y + lh / 2), ln, font=font, fill=color, anchor="rm")
        else:
            draw.text((x0, y + lh / 2), ln, font=font, fill=color, anchor="lm")
        y += lh


def text_block(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
               s: str, color: Tuple[int, int, int],
               font: ImageFont.FreeTypeFont, align: str = "left",
               line_gap: int = 4) -> None:
    """Same as text_box but draws exactly the wrapped lines (no line cap)."""
    text_box(draw, box, s, color, font, align=align, line_gap=line_gap)


def drop_shadow(draw: ImageDraw.ImageDraw, rect: Tuple[int, int, int, int],
                color: Tuple[int, int, int], blur: int = 14,
                offset: int = 0, opacity: float = 0.5) -> None:
    """Simple blurred shadow under a rounded rect — drawn on a temp image."""
    x0, y0, x1, y1 = rect
    pad = blur
    sh = Image.new("L", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), 0)
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle(
        [pad, pad + offset, pad + (x1 - x0), pad + (y1 - y0) + offset],
        radius=18, fill=int(255 * opacity),
    )
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    for y in range(sh.size[1]):
        rb = sh.getpixel((0, y))
        if rb == 0:
            continue
        row = [sh.getpixel((x, y)) for x in range(sh.size[0])]
        for x, a in enumerate(row):
            if a:
                draw.point((x0 - pad + x, y0 - pad + y),
                          fill=(*color, a))
    # PIL doesn't do RGBA drop-in easily for ImageDraw; keep shadow subtle
    # by compositing via Image.alpha_composite later if needed.
    return


# ---------------------------------------------------------------------------
# Drawing recipes — each returns (Image, 16:9)
# ---------------------------------------------------------------------------
W, H = 1600, 900


def _canvas(bg: Tuple[int, int, int] = PALETTE["bg_dark"]) -> Image.Image:
    return Image.new("RGB", (W, H), bg)


def vignette(img: Image.Image, top: Tuple[int, int, int],
             bot: Tuple[int, int, int]) -> Image.Image:
    """Vertical gradient top→bottom burn."""
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((W, H))
    out = Image.new("RGB", (W, H))
    out.paste(grad, (0, 0))
    out = Image.blend(out, img, 0.85)
    return out


def make_cover() -> Image.Image:
    """Title slide: dark with a focused camera-subject composition."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # top band with gold accent
    rounded_rect(d, (0, 0, W, 130), 0, PALETTE["bg_dark"])
    line(d, (0, 130), (W, 130), PALETTE["gold"], width=2)

    # eyebrow
    text_centered(d, (220, 78), "CREW-SHARABLE SITUATIONAL AWARENESS", PALETTE["gold"],
                  _font(30, True))

    # title
    title_font = _font(58, True)
    text_centered(d, (220, 300), "EAGLE EYE", PALETTE["text"], title_font, anchor="mm")
    sub_font = _font(40, True)
    text_centered(d, (220, 370), "Live Shared Detection for Phone Crews", PALETTE["gold"],
                  sub_font, anchor="mm")

    # face-outline silhouette on the right, hand-holding-phone pose
    _draw_person_with_phone(d, 1180, 430, scale=280)

    # bottom bar
    line(d, (220, 820), (1380, 820), PALETTE["line_soft"], width=1)
    meta = [
        ("Civilian computer-vision prototype", "Headline"),
        ("WebXR + WebRTC + YOLOv8n", "Tech"),
        ("Zero configuration — works in any room", "Promise"),
    ]
    x = 220
    for label, val in meta:
        text_centered(d, (x + 120, 850), label, PALETTE["text_dim"], _font(22, True))
        text_centered(d, (x + 120, 885), val, PALETTE["text"], _font(20, False))
        x += 360

    # corner marks
    for (cx, cy) in [(220, 150), (1380, 150), (220, 760), (1380, 760)]:
        d.arc([cx - 30, cy - 30, cx + 30, cy + 30], start=0, end=360,
              fill=PALETTE["line"], width=1)

    return vignette(img, PALETTE["bg_dark"], (18, 26, 30))


def _draw_person_with_phone(d: ImageDraw.ImageDraw, cx: int, cy: int,
                            scale: int) -> None:
    """Stroke-only silhouette: head + shoulders, one arm extended holding a
    phone. Read as 'person wearing a phone'. Scale sets the figure size."""
    s = scale
    head_r = s * 0.085
    shoulder_w = s * 0.42
    body_top = cy - s * 0.5
    body_bot = cy + s * 0.18

    # head
    ellipse(d, (cx - head_r, body_top - s * 0.18, cx + head_r, body_top + s * 0.12),
            fill=None, outline=PALETTE["text"], width=max(2, s // 120))

    # body / shoulders
    line(d, (cx - shoulder_w, body_top), (cx, body_top), PALETTE["text"],
         width=max(2, s // 120))
    line(d, (cx, body_top), (cx + shoulder_w, body_top), PALETTE["text"],
         width=max(2, s // 120))
    line(d, (cx - shoulder_w, body_top), (cx - shoulder_w * 0.55, body_bot),
         PALETTE["text"], width=max(2, s // 120))
    line(d, (cx + shoulder_w, body_top), (cx + shoulder_w * 0.62, body_bot),
         PALETTE["text"], width=max(2, s // 120))
    line(d, (cx, body_top), (cx, body_bot), PALETTE["text"],
         width=max(2, s // 120))

    # right arm extended toward phone
    hand_x = cx + shoulder_w * 0.75
    hand_y = body_top - s * 0.02
    line(d, (cx + shoulder_w * 0.55, body_top + s * 0.06),
         (hand_x, hand_y), PALETTE["text"], width=max(2, s // 120))
    # phone
    px, py = hand_x, hand_y
    p_w, p_h = s * 0.12, s * 0.07
    d.rounded_rectangle(
        [px - p_w / 2, py - p_h / 2, px + p_w / 2, py + p_h / 2],
        radius=p_h * 0.18, fill=None, outline=PALETTE["gold"],
        width=max(2, s // 120),
    )
    line(d, (px - p_w / 2 + p_h * 0.3, py), (px + p_w / 2 - p_h * 0.3, py),
         PALETTE["gold"], width=max(1, s // 160))


def make_family_composition() -> Image.Image:
    """Visual: three phone cameras feed one central 'you see everything' spot."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # title strip
    rounded_rect(d, (0, 0, W, 96), 0, PALETTE["bg_dark"])
    line(d, (0, 96), (W, 96), PALETTE["gold"], width=2)
    text_centered(d, (80, 50), "THREE PHONES — ONE SHARED VIEW", PALETTE["gold"],
                  _font(26, True), anchor="lm")

    # three camera 'devices' at lower-left, lower-center, lower-right
    cams = [
        (160, 720, "CAM 1", 0),
        (470, 720, "CAM 2", -12),
        (780, 720, "CAM 3", 8),
    ]
    for (cx, cy, label, tilt) in cams:
        _draw_phone(d, cx, cy, label, tilt, scale=60)

    # streams going up (dashed lines) to a shared point
    targets = [160, 470, 780]
    center_x = 1280
    center_y = 220
    for tx in targets:
        dash(d, (tx + 40, 690), (center_x, center_y), PALETTE["signal_blue"],
             dash_len=12, gap=8, width=2)
        # small glowing dot at top
        ellipse(d, (center_x - 6, center_y - 6, center_x + 6, center_y + 6),
                fill=PALETTE["signal_blue"], outline=None)

    # central shared view block
    rounded_rect(d, (center_x - 300, center_y - 150, center_x + 300, center_y + 200),
                 22, PALETTE["panel"], outline=PALETTE["line"], width=2)
    d.line([(center_x - 300, center_y + 40), (center_x + 300, center_y + 40)],
           fill=PALETTE["line_soft"], width=1)
    d.line([(center_x, center_y - 150), (center_x, center_y + 200)],
           fill=PALETTE["line_soft"], width=1)

    text_centered(d, (center_x, center_y - 80), "SHARED WORLD STATE", PALETTE["gold"],
                  _font(30, True))
    text_centered(d, (center_x, center_y - 10), "one detection → every camera's view",
                  PALETTE["text"], _font(22, False))

    # inside: three small person + wall projection scenes stacked
    _mini_scene(d, center_x - 200, center_y + 60, 180, 120, "CAM 1 view")
    _mini_scene(d, center_x, center_y + 60, 180, 120, "CAM 2 view")
    _mini_scene(d, center_x + 200, center_y + 60, 180, 120, "CAM 3 view")

    # bottom caption
    caption = ("No markers. No tape. No setup.\n"
               "Each phone locates itself live via ARCore;\n"
               "detections land in one shared 3D space.")
    text_block(d, (80, 810, 1480, 880), caption, PALETTE["text_dim"], _font(22, False))

    return vignette(img, PALETTE["bg_dark"], (20, 28, 32))


def _draw_phone(d: ImageDraw.ImageDraw, cx: int, cy: int, label: str,
                tilt: int = 0, scale: int = 60) -> None:
    """Simple phone device glyph: rounded rectangle with camera-dot and label."""
    s = scale
    w, h = s * 2.6, s * 5.2
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    rounded_rect(d, box, radius=h * 0.14, fill=PALETTE["panel"],
                 outline=PALETTE["gold"], width=3)
    # camera module
    cam_w, cam_h = s * 0.18, s * 0.18
    ellipse(d, [cx - cam_w / 2, cy - h / 2 - cam_h, cx + cam_w / 2, cy - h / 2],
            fill=PALETTE["text"])
    # label
    text_centered(d, (cx, cy + h / 2 + 22), label, PALETTE["gold"], _font(18, True),
                  anchor="mm")
    # small frame view if tilted toward world
    if tilt != 0:
        dash(d, (cx, cy - h / 2 - 4), (cx + tilt, cy - h / 2 - 24),
             PALETTE["signal_blue"], dash_len=8, gap=6, width=1)


def _mini_scene(d: ImageDraw.ImageDraw, cx: int, cy: int, w: int, h: int,
               title: str) -> None:
    """Tiny framed scene: wall + person outline + red-X marker."""
    d.rounded_rectangle([cx, cy, cx + w, cy + h], radius=8,
                        fill=PALETTE["bg_slate"], outline=PALETTE["line"],
                        width=1)
    d.line([(cx, cy + h * 0.62), (cx + w, cy + h * 0.62)],
           fill=PALETTE["line_soft"], width=1)
    # a red X marker near the wall
    mx, my = cx + w * 0.7, cy + h * 0.52
    s = 10
    d.line([(mx - s, my - s), (mx + s, my + s)], fill=PALETTE["crimson"], width=2)
    d.line([(mx + s, my - s), (mx - s, my + s)], fill=PALETTE["crimson"], width=2)
    text_centered(d, (cx + w / 2, cy + h * 0.07), title, PALETTE["text_dim"],
                  _font(14, True), anchor="mm")


def make_detection_scene() -> Image.Image:
    """One camera view with a live YOLO detection + confidence + red X dot."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # top strip
    rounded_rect(d, (0, 0, W, 96), 0, PALETTE["bg_dark"])
    line(d, (0, 96), (W, 96), PALETTE["gold"], width=2)
    text_centered(d, (80, 50), "ONE CAMERA — ONE DETECTION — ONE 3D POINT", PALETTE["gold"],
                  _font(24, True), anchor="lm")

    # main camera-view panel
    px, py, pw, ph = 90, 150, 860, 680
    rounded_rect(d, (px, py, px + pw, py + ph), 18, PALETTE["bg_slate"],
                 outline=PALETTE["line"], width=2)
    line(d, (px, py + 56), (px + pw, py + 56), PALETTE["line"], width=1)
    text_centered(d, (px + pw / 2, py + 32), "CAM 1 · 640 × 480 · ~30 FPS",
                  PALETTE["text_dim"], _font(18, True), anchor="mm")

    # live frame content drawn as a scene
    _draw_live_scene(d, px, py, pw, ph)

    # side panel: detection readout
    sx, sy, sw, sh = px + pw + 40, py, 600, ph
    rounded_rect(d, (sx, sy, sx + sw, sy + sh), 18, PALETTE["panel"],
                 outline=PALETTE["line"], width=2)
    text_centered(d, (sx + sw / 2, sy + 44), "DETECTION", PALETTE["gold"],
                  _font(26, True))
    d.line([(sx + 60, sy + 62), (sx + sw - 60, sy + 62)], fill=PALETTE["line"],
           width=1)

    x = sx + 50
    rows = [
        ("Class", "person", PALETTE["text"]),
        ("Confidence", "0.87", PALETTEDEMO := PALETTE["green"]),
        ("Bbox px", "320, 240, 80, 160", PALETTE["text"]),
        ("", "", PALETTE["text"]),
        ("→ 3D point", "( 0.6 m, 1.3 m, 2.4 m )", PALETTE["crimson"]),
        ("", "", PALETTE["text"]),
        ("Camera pose", "x 0.0  y 1.3  z 0.0", PALETTE["text"]),
        ("", "", PALETTE["text"]),
        ("Distance", "~2.6 m from camera", PALETTE["amber"]),
    ]
    yy = sy + 84
    for label, val, col in rows:
        if not label:
            yy += 16
            continue
        d.text((x, yy), label, font=_font(22, True), fill=PALETTE["text_dim"])
        if col == PALETTE["crimson"]:
            d.text((x + 320, yy), val, font=_font(24, True), fill=col)
        else:
            d.text((x + 320, yy), val, font=_font(24, False), fill=col)
        yy += 54

    # bottom strip
    line(d, (90, 836), (1510, 836), PALETTE["line"], width=1)
    d.text((90, 856), "Person located in shared room space by pose × bbox depth",
           font=_font(22, False), fill=PALETTE["text_dim"])

    return vignette(img, PALETTE["bg_dark"], (20, 30, 34))


def _draw_live_scene(d: ImageDraw.ImageDraw, px: int, py: int, w: int,
                     h: int) -> None:
    """Arted camera frame: room with a person, bounding box, and a red X."""
    # floor line
    floor_y = py + h * 0.72
    d.line([(px, floor_y), (px + w, floor_y)], fill=PALETTE["line_soft"], width=1)
    # back wall
    d.line([(px, py), (px + w, py)], fill=PALETTE["line"], width=1)
    # side wall (perspective)
    d.line([(px, py), (px + w * 0.28, floor_y)], fill=PALETTE["line_soft"], width=1)

    # a person silhouette standing near center-left
    px_person = px + w * 0.26
    feet_y = floor_y
    head_y = feet_y - h * 0.30
    body_top = head_y + h * 0.05
    shoulder_w = w * 0.04
    body_w = w * 0.028
    # head
    ellipse(d, (px_person - w * 0.018, head_y, px_person + w * 0.018,
                head_y + h * 0.07), outline=PALETTE["text"], width=1)
    # body
    d.line([(px_person - shoulder_w, body_top),
             (px_person + shoulder_w, body_top)], fill=PALETTE["text"], width=1)
    d.line([(px_person - shoulder_w, body_top),
             (px_person - body_w, feet_y)], fill=PALETTE["text"], width=1)
    d.line([(px_person + shoulder_w, body_top),
             (px_person + body_w, feet_y)], fill=PALETTE["text"], width=1)
    d.line([(px_person, body_top), (px_person, feet_y)], fill=PALETTE["text"],
           width=1)

    # bounding box (YOLO)
    bbox = [px_person - w * 0.022, head_y, px_person + w * 0.05, feet_y + h * 0.02]
    d.rectangle(bbox, outline=PALETTE["green"], width=2)
    text_centered(d, (bbox[0] + 14, bbox[1] - 10), "person 0.87", PALETTE["green"],
                  _font(16, True))

    # red X marker on the person
    mx = px_person + w * 0.014
    my = head_y + h * 0.03
    s = 12
    d.line([(mx - s, my - s), (mx + s, my + s)], fill=PALETTE["crimson"], width=2)
    d.line([(mx + s, my - s), (mx - s, my + s)], fill=PALETTE["crimson"], width=2)


def make_flux_diagram() -> Image.Image:
    """Process / data-flow diagram: three phones → fusion → world state → viewers."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # title
    rounded_rect(d, (0, 0, W, 90), 0, PALETTE["bg_dark"])
    line(d, (0, 90), (W, 90), PALETTE["gold"], width=2)
    text_centered(d, (80, 48), "HOW IT WORKS — THREE STREAMS INTO ONE SHARED WORLD",
                  PALETTE["gold"], _font(22, True), anchor="lm")

    # three source nodes at the top
    sources = [
        (140, "CAM 1", "ARCore pose + camera frame"),
        (470, "CAM 2", "ARCore pose + camera frame"),
        (800, "CAM 3", "ARCore pose + camera frame"),
    ]
    node_y = 200
    for (cx, label, sub) in sources:
        _node(d, cx, node_y, label, sub, PALETTE["panel"], PALETTE["gold"])

    # arrows down into a fusion hub
    hub_cx, hub_cy = 470, 430
    hub_w, hub_h = 480, 120
    _rounded_node(d, hub_cx - hub_w / 2, hub_cy - hub_h / 2,
                  hub_cx + hub_w / 2, hub_cy + hub_h / 2,
                  PALETTE["bg_slate"], PALETTE["gold"], "FUSION ENGINE",
                  "pose × bbox → 3D point per person")

    for (sx, _, _) in sources:
        line(d, (sx, node_y + 70), (hub_cx, hub_cy - hub_h / 2),
             PALETTE["signal_blue"], width=2)
        # arrowhead
        ang = -90
        ax, ay = hub_cx, hub_cy - hub_h / 2
        _arrowhead(d, ax, ay, ang, PALETTE["signal_blue"], size=12)

    # output to right
    out_cx = 980
    _rounded_node(d, out_cx - 200, hub_cy - 70, out_cx + 200, hub_cy + 70,
                  PALETTE["panel_soft"], PALETTE["amber"], "WORLD STATE",
                  "/world JSON — every track at true location")

    line(d, (hub_cx + hub_w / 2, hub_cy), (out_cx - 200, hub_cy),
         PALETTE["amber"], width=2)
    _arrowhead(d, out_cx - 200, hub_cy, 0, PALETTE["amber"], size=12)

    # viewers on the far right
    vw_cx = 1460
    _rounded_node(d, vw_cx - 140, hub_cy - 90, vw_cx + 140, hub_cy + 90,
                  PALETTE["bg_slate"], PALETTE["crimson"], "VIEWERS",
                  "live red-X overlays on every screen")

    line(d, (out_cx + 200, hub_cy), (vw_cx - 140, hub_cy),
         PALETTE["crimson"], width=2)
    _arrowhead(d, vw_cx - 140, hub_cy, 0, PALETTE["crimson"], size=12)

    # bottom note
    note = ("Real upside: all streams are plain HTTPS / WebRTC — nothing exotic.\n"
            "A phone trusts the cert (one tap), enters AR, and the rest is automatic.")
    text_block(d, (80, 770, 1520, 860), note, PALETTE["text_dim"], _font(22, False))

    return vignette(img, PALETTE["bg_dark"], (20, 28, 32))


def _node(d: ImageDraw.ImageDraw, cx: int, cy: int, label: str,
         sub: str, fill: Tuple[int, int, int], accent: Tuple[int, int, int]) -> None:
    w, h = 280, 110
    _rounded_node(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                  fill, accent, label, sub)


def _rounded_node(d: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int,
                  fill: Tuple[int, int, int], accent: Tuple[int, int, int],
                  label: str, sub: str) -> None:
    rounded_rect(d, (x0, y0, x1, y1), 18, fill, outline=accent, width=2)
    text_centered(d, ((x0 + x1) / 2, (y0 + y1) / 2 - 14), label, accent,
                  _font(20, True))
    text_centered(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 18), sub, PALETTE["text_dim"],
                  _font(16, False))


def _arrowhead(d: ImageDraw.ImageDraw, x: int, y: int, ang_deg: float,
               color: Tuple[int, int, int], size: int = 12) -> None:
    import math
    a = math.radians(ang_deg)
    p1 = (x - math.cos(a - 0.4) * size, y - math.sin(a - 0.4) * size)
    p2 = (x - math.cos(a + 0.4) * size, y - math.sin(a + 0.4) * size)
    d.polygon([p1, p2, (x, y)], fill=color)


def make_opener() -> Image.Image:
    """Section opener: 3x5 camera grid with one glowing viewed-through-the-wall."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # title
    rounded_rect(d, (0, 0, W, 90), 0, PALETTE["bg_dark"])
    line(d, (0, 90), (W, 90), PALETTE["gold"], width=2)
    text_centered(d, (80, 48), "YOU DON'T NEED TO BE THERE TO KNOW THEY'RE THERE",
                  PALETTE["gold"], _font(24, True), anchor="lm")

    # central 3x5 camera grid
    grid_img = _make_camera_grid()
    gx, gy = 80, 220
    gw, gh = 900, 580
    rounded_rect(d, (gx, gy, gx + gw, gy + gh), 18, PALETTE["panel"],
                 outline=PALETTE["line"], width=2)
    # center the image
    ix = gx + (gw - grid_img.width) / 2
    iy = gy + (gh - grid_img.height) / 2
    img.paste(grid_img, (int(ix), int(iy)))

    # spotlight in center of grid (the 'viewed' camera)
    spot_cx = gx + gw / 2
    spot_cy = gy + gh / 2
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for r in range(200, 0, -8):
        a = int(40 * (1 - r / 200))
        od.ellipse([spot_cx - r, spot_cy - r, spot_cx + r, spot_cy + r],
                    fill=(255, 69, 58, a))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # caption beside it
    cap_x = gx + gw + 40
    cap_str = ("Each phone streams its live view and its ARCore location to one server.\n"
               "When a person is detected, every other camera shows a red X at their\n"
               "true 3D position — even through a wall.")
    text_block(d, (cap_x, gy, 1480, gy + 260), cap_str, PALETTE["text"],
               _font(24, False))

    features = [
        ("Real-time", "detections appear on all screens within ~1 s"),
        ("Shared", "every crew member sees the same world"),
        ("Through walls", "wall occlusion handled by projection, not magic"),
        ("No setup", "open the page, enter AR, it works"),
    ]
    yy = gy + 300
    for title_s, desc_s in features:
        d.ellipse([cap_x, yy + 6, cap_x + 12, yy + 18], fill=PALETTE["gold"])
        d.text((cap_x + 26, yy), title_s, font=_font(20, True), fill=PALETTE["text"])
        d.text((cap_x + 26, yy + 26), desc_s, font=_font(18, False),
               fill=PALETTE["text_dim"])
        yy += 90

    return vignette(img, PALETTE["bg_dark"], (20, 28, 32))


def _make_camera_grid() -> Image.Image:
    """3x5 grid of camera-view thumbnails, one glowing."""
    cols, rows = 5, 3
    cell = 180
    pad = 8
    w = cols * cell + (cols - 1) * pad
    h = rows * cell + (rows - 1) * pad
    g = Image.new("RGB", (w, h), PALETTE["bg_slate"])
    gd = ImageDraw.Draw(g)
    # build six distinct views
    scenes: List[Image.Image] = [
        _scene_street(),
        _scene_room(),
        _scene_dark_room(),
        _scene_walls(),
        _scene_corridor(),
        _scene_pair(),
    ]
    for idx, scene in enumerate(scenes):
        col = idx % cols
        row = idx // cols
        x = col * (cell + pad)
        y = row * (cell + pad)
        # thumbnail
        thumb = scene.copy()
        td = ImageDraw.Draw(thumb)
        td.rounded_rectangle([0, 0, cell - 1, cell - 1], radius=6,
                             outline=PALETTE["line"], width=1)
        # overlay vignette
        ov = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
        ovd = ImageDraw.Draw(ov)
        for rx in range(0, cell, 6):
            a = int(60 * rx / cell)
            od_ = Image.new("L", (cell, cell), a)
            # simpler: light border
            pass
        # frame highlight for the 'viewed' one (center of grid: idx 7? no, idx 4)
        if idx == 4:
            gd.rectangle([x - 3, y - 3, x + cell + 3, y + cell + 3],
                         outline=PALETTE["crimson"], width=3)
            # red-X on scene
            tx, ty = x + cell * 0.5, y + cell * 0.45
            s = 18
            td.line([(tx - s, ty - s), (tx + s, ty + s)], fill=PALETTE["crimson"],
                     width=4)
            td.line([(tx + s, ty - s), (tx - s, ty + s)], fill=PALETTE["crimson"],
                     width=4)
        g.paste(thumb, (x, y))
    return g


def _scene_street() -> Image.Image:
    img = Image.new("RGB", (180, 180), (40, 46, 54))
    d = ImageDraw.Draw(img)
    d.line([(0, 120), (180, 120)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["ink"], width=2)
    # person silhouette
    cx, feet = 118, 120
    d.ellipse([cx - 8, feet - 38, cx + 8, feet - 18], outline=PALETTE["text"],
              width=1)
    d.line([(cx - 16, feet - 34), (cx + 16, feet - 34)], fill=PALETTE["text"], width=1)
    d.line([(cx - 16, feet - 34), (cx - 10, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx + 16, feet - 34), (cx + 10, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx, feet - 34), (cx, feet)], fill=PALETTE["text"], width=1)
    return img


def _scene_room() -> Image.Image:
    img = Image.new("RGB", (180, 180), (54, 58, 64))
    d = ImageDraw.Draw(img)
    d.line([(0, 100), (180, 100)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["ink"], width=2)
    d.line([(0, 0), (40, 100)], fill=PALETTE["ink_soft"], width=1)
    cx, feet = 120, 100
    d.ellipse([cx - 8, feet - 34, cx + 8, feet - 14], outline=PALETTE["text"],
              width=1)
    d.line([(cx - 14, feet - 30), (cx + 14, feet - 30)], fill=PALETTE["text"], width=1)
    d.line([(cx - 14, feet - 30), (cx - 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx + 14, feet - 30), (cx + 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx, feet - 30), (cx, feet)], fill=PALETTE["text"], width=1)
    return img


def _scene_dark_room() -> Image.Image:
    img = Image.new("RGB", (180, 180), (20, 22, 26))
    d = ImageDraw.Draw(img)
    d.line([(0, 110), (180, 110)], fill=PALETTE["line"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["line"], width=1)
    cx, feet = 110, 110
    d.ellipse([cx - 8, feet - 32, cx + 8, feet - 12], outline=PALETTE["text"],
              width=1)
    d.line([(cx - 14, feet - 28), (cx + 14, feet - 28)], fill=PALETTE["text"], width=1)
    d.line([(cx - 14, feet - 28), (cx - 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx + 14, feet - 28), (cx + 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx, feet - 28), (cx, feet)], fill=PALETTE["text"], width=1)
    return img


def _scene_walls() -> Image.Image:
    img = Image.new("RGB", (180, 180), (48, 54, 60))
    d = ImageDraw.Draw(img)
    d.line([(0, 110), (180, 110)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["ink"], width=2)
    d.line([(0, 0), (50, 110)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (0, 50)], fill=PALETTE["ink_soft"], width=1)
    # two people
    for (px, pw) in [(60, 10), (120, 10)]:
        feet = 110
        d.ellipse([px - 9, feet - 36, px + 9, feet - 12], outline=PALETTE["text"],
                  width=1)
        d.line([(px - pw, feet - 30), (px + pw, feet - 30)], fill=PALETTE["text"],
               width=1)
        d.line([(px - pw, feet - 30), (px - pw * 0.7, feet)], fill=PALETTE["text"],
               width=1)
        d.line([(px + pw, feet - 30), (px + pw * 0.7, feet)], fill=PALETTE["text"],
               width=1)
        d.line([(px, feet - 30), (px, feet)], fill=PALETTE["text"], width=1)
    return img


def _scene_corridor() -> Image.Image:
    img = Image.new("RGB", (180, 180), (44, 50, 56))
    d = ImageDraw.Draw(img)
    d.line([(0, 105), (180, 105)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["ink"], width=2)
    d.line([(0, 0), (180, 0)], fill=PALETTE["line"], width=1)
    # converging walls
    d.line([(30, 0), (0, 105)], fill=PALETTE["line_soft"], width=1)
    d.line([(150, 0), (180, 105)], fill=PALETTE["line_soft"], width=1)
    cx, feet = 90, 105
    d.ellipse([cx - 8, feet - 32, cx + 8, feet - 12], outline=PALETTE["text"],
              width=1)
    d.line([(cx - 14, feet - 28), (cx + 14, feet - 28)], fill=PALETTE["text"],
           width=1)
    d.line([(cx - 14, feet - 28), (cx - 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx + 14, feet - 28), (cx + 8, feet)], fill=PALETTE["text"], width=1)
    d.line([(cx, feet - 28), (cx, feet)], fill=PALETTE["text"], width=1)
    return img


def _scene_pair() -> Image.Image:
    img = Image.new("RGB", (180, 180), (50, 56, 62))
    d = ImageDraw.Draw(img)
    d.line([(0, 105), (180, 105)], fill=PALETTE["ink_soft"], width=1)
    d.line([(0, 0), (180, 0)], fill=PALETTE["ink"], width=2)
    for (px, pw) in [(70, 12), (120, 12)]:
        feet = 105
        d.ellipse([px - 10, feet - 40, px + 10, feet - 16], outline=PALETTE["text"],
                  width=1)
        d.line([(px - pw, feet - 34), (px + pw, feet - 34)], fill=PALETTE["text"],
               width=1)
        d.line([(px - pw, feet - 34), (px - pw * 0.7, feet)], fill=PALETTE["text"],
               width=1)
        d.line([(px + pw, feet - 34), (px + pw * 0.7, feet)], fill=PALETTE["text"],
               width=1)
        d.line([(px, feet - 34), (px, feet)], fill=PALETTE["text"], width=1)
    # red X on the left person
    mx, my = 70, feet - 28
    s = 16
    d.line([(mx - s, my - s), (mx + s, my + s)], fill=PALETTE["crimson"], width=3)
    d.line([(mx + s, my - s), (mx - s, my + s)], fill=PALETTE["crimson"], width=3)
    return img


def make_timing_chart() -> Image.Image:
    """Simple bar chart: per-step latency bars, huge headline number."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    rounded_rect(d, (0, 0, W, 90), 0, PALETTE["bg_dark"])
    line(d, (0, 90), (W, 90), PALETTE["gold"], width=2)
    text_centered(d, (80, 48), "FROM DETECTION TO EVERY SCREEN", PALETTE["gold"],
                  _font(24, True), anchor="lm")

    # headline number
    big = "≤ 1.5 s"
    text_centered(d, (220, 280), big, PALETTE["crimson"], _font(120, True))
    text_centered(d, (220, 372), "end-to-end: detected → every viewer",
                  PALETTE["text"], _font(26, False))

    # bars
    steps = [
        ("Phone capture + encode", 300, PALETTE["signal_blue"]),
        ("WebRTC transmit (LAN)", 180, PALETTE["signal_blue2"]),
        ("PC decode + YOLO detect", 500, PALETTE["amber"]),
        ("Fusion: pose × depth", 200, PALETTE["teal"]),
        ("Broadcast to every viewer", 60, PALETTE["green"]),
    ]
    bar_x = 360
    bar_w = 260
    bar_gap = 70
    max_h = 320
    unit = max_h / 800  # 1 ms → max_h/800 px
    base_y = 840
    for i, (name, ms, col) in enumerate(steps):
        bx = bar_x + i * (bar_w + bar_gap)
        bh = ms * unit
        by = base_y - bh
        rounded_rect(d, (bx, by, bx + bar_w, base_y), 8, col)
        text_centered(d, (bx + bar_w / 2, base_y - 18), f"{ms} ms", col,
                      _font(20, True))
        text_centered(d, (bx + bar_w / 2, base_y + 18), name, PALETTE["text_dim"],
                      _font(18, False))

    # axis line
    d.line([(bar_x - 10, base_y), (bar_x + len(steps) * (bar_w + bar_gap) - 10,
                                   base_y)], fill=PALETTE["line"], width=1)

    # bottom caption
    cap = ("Six phones, one server, sub-second detection in every camera's view.\n"
           "The hard part — locating the person in the real room — is done once,\n"
           "then it's shared everywhere.")
    text_block(d, (80, 860, 1500, 900), cap, PALETTE["text_dim"], _font(18, False))

    return vignette(img, PALETTE["bg_dark"], (20, 30, 34))


def make_roadmap() -> Image.Image:
    """Four phase roadmap: M1 → M2 (proven) → M3 (this) → M4 (later)."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    rounded_rect(d, (0, 0, W, 90), 0, PALETTE["bg_dark"])
    line(d, (0, 90), (W, 90), PALETTE["gold"], width=2)
    text_centered(d, (80, 48), "ROADMAP", PALETTE["gold"], _font(26, True), anchor="lm")

    phases = [
        ("M1", "Phone → PC live video",
         "WebRTC, ~25 FPS decode, zero drops — proven.",
         True, PALETTE["green"]),
        ("M2", "Pose streaming + YOLO",
         "ARCore x/y/z into the PC; person detection live on the stream — proven.",
         True, PALETTE["green"]),
        ("M3", "Shared world + red-X overlay",
         "Fuse pose with detections → 3D track; project a red X in every camera's view — this build.",
         False, PALETTE["gold"]),
        ("M4", "Depth + identity + multi-room",
         "Scene mapping on the M4 Mac, ReID for friend/enemy, scale through any room — later.",
         False, PALETTE["text_dim"]),
    ]
    n = len(phases)
    x0 = 100
    total_w = 1400
    seg_w = total_w / (n - 1)
    y = 260
    box_h = 380
    first_x = x0

    for i, (code, title, body, done, col) in enumerate(phases):
        cx = x0 + i * seg_w
        # node circle
        r = 30
        ellipse(d, (cx - r, y - r, cx + r, y + r), fill=col, outline=None)
        if done:
            d.line([(cx - r + 6, y - r + 6), (cx + r - 6, y + r - 6)], fill=PALETTE["ink"],
                   width=1)
            d.line([(cx - r + 6, y + r - 6), (cx + r - 6, y - r + 6)], fill=PALETTE["ink"],
                   width=1)
        text_centered(d, (cx, y), code, PALETTE["bg_dark"], _font(16, True))

        # connector line between nodes
        if i > 0:
            d.line([(first_x + (i - 1) * seg_w + 28, y),
                    (cx - 28, y)], fill=PALETTE["line"], width=2)
            # tick
            d.line([(cx - 28, y - 16), (cx - 28, y + 16)], fill=PALETTE["line"], width=1)

        # card
        card_x = cx - 220
        card_w = 440
        card_y = y + 60
        card_h = box_h
        rounded_rect(d, (card_x, card_y, card_x + card_w, card_y + card_h),
                     16, PALETTE["panel"], outline=PALETTE["line"], width=1)
        # left accent bar
        d.rectangle([card_x, card_y, card_x + 6, card_y + card_h],
                    fill=col)
        text_centered(d, (card_x + 220, card_y + 36), title, PALETTE["text"],
                      _font(26, True))
        text_block(d, (card_x + 22, card_y + 80, card_x + card_w - 22,
                       card_y + card_h - 20), body, PALETTE["text_dim"],
                   _font(18, False))

        first_x = x0

    # bottom note
    note = ("Today: we have M1 + M2 proven and M3 is the current build.\n"
             "M4 makes the prototype serious; M3 makes it useful.")
    text_block(d, (80, 820, 1500, 880), note, PALETTE["text_dim"], _font(20, False))

    return vignette(img, PALETTE["bg_dark"], (20, 30, 34))


def make_status() -> Image.Image:
    """Status board: what's proven (green) and what's the build (amber)."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    rounded_rect(d, (0, 0, W, 90), 0, PALETTE["bg_dark"])
    line(d, (0, 90), (W, 90), PALETTE["gold"], width=2)
    text_centered(d, (80, 48), "STATUS TODAY", PALETTE["gold"], _font(26, True),
                  anchor="lm")

    rows = [
        ("Phone → PC live video (WebRTC)", "~25 FPS decode, zero drops", True, "M1"),
        ("ARCore pose streaming to the PC", "ARCore x/y/z + quaternion, two phones simultaneously", True, "M2"),
        ("YOLOv8n person detection", "conf 0.35, live on the stream, ~15 FPS on CPU", True, "M2"),
        ("Clock sync + latency telemetry", "NTP-style sync; rtt and one-way latency every 5 s", True, "M2"),
        ("Fusion: detections × pose → 3D track", "depth from bbox height; one world per person", False, "M3"),
        ("Cross-camera red-X overlay", "project a person's point into every other camera's view", False, "M3"),
        ("Shared world state broadcast", "/world JSON → live viewer page", False, "M3"),
        ("Person identity across cameras", "v1 nearest-ray matching; ReID later", False, "M4"),
        ("Friend vs enemy distinction", "v1 marks all people", False, "M4"),
        ("Scene mapping / walls in 3D", "depth-anything on the M4 later", False, "M4"),
    ]
    x0, y0 = 80, 150
    col_w = 900
    row_h = 66
    for i, (label, detail, done, who) in enumerate(rows):
        ry = y0 + i * row_h
        bg = PALETTE["panel"] if i % 2 == 0 else PALETTE["panel_soft"]
        rounded_rect(d, (x0, ry, x0 + col_w, ry + row_h), 10, bg, outline=None)
        d.line([(x0, ry), (x0 + col_w, ry)], fill=PALETTE["line_soft"], width=1)

        mark = "✓" if done else "○"
        mcol = PALETTE["green"] if done else PALETTE["gold"]
        d.text((x0 + 24, ry + 22), mark, font=_font(26, True), fill=mcol)
        d.text((x0 + 64, ry + 22), label, font=_font(22, True), fill=PALETTE["text"])
        d.text((x0 + 64, ry + 44), detail, font=_font(18, False), fill=PALETTE["text_dim"])

        wc = PALETTE["gold"] if not done else PALETTE["green"]
        d.text((x0 + col_w - 60, ry + 22), who, font=_font(16, True), fill=wc)

    # who band
    last_y = y0 + len(rows) * row_h + 20
    rounded_rect(d, (x0, last_y, x0 + col_w, last_y + 44), 0, PALETTE["bg_dark"])
    text_centered(d, (x0 + col_w / 2, last_y + 22),
                  "M1–M2 proven  ·  M3 in progress  ·  M4 planned",
                  PALETTE["gold"], _font(20, True))

    return vignette(img, PALETTE["bg_dark"], (20, 30, 34))


def make_close() -> Image.Image:
    """Closing slide: one promise, one number, one action."""
    img = _canvas(PALETTE["bg_dark"])
    d = ImageDraw.Draw(img)

    # big centered mark
    cx, cy = W / 2, H / 2 - 60
    s = 140
    # crosshair
    d.line([(cx - s, cy), (cx + s, cy)], fill=PALETTE["crimson"], width=8)
    d.line([(cx, cy - s), (cx, cy + s)], fill=PALETTE["crimson"], width=8)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=PALETTE["crimson"])
    # halo
    for r in range(90, 160, 8):
        a = int(60 * (1 - r / 160))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=PALETTE["crimson"],
                  width=2)

    big = "ONE PERSON\nIN EVERY VIEW"
    lines = big.split("\n")
    y = cy + 180
    for ln in lines:
        text_centered(d, (cx, y), ln, PALETTE["text"], _font(40, True))
        y += 52

    sub = "Eagle Eye — shared situational awareness for phone crews"
    text_centered(d, (cx, y + 30), sub, PALETTE["gold"], _font(22, False))
    text_centered(d, (cx, y + 68), "Civilian computer-vision prototype",
                  PALETTE["text_dim"], _font(18, False))

    # corner marks
    for (px, py) in [(60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)]:
        d.arc([px - 24, py - 24, px + 24, py + 24], start=0, end=360,
              fill=PALETTE["line"], width=1)

    return vignette(img, PALETTE["bg_dark"], (18, 26, 30))


DRAWERS: Dict[str, Any] = {
    "cover": make_cover,
    "family": make_family_composition,
    "detection": make_detection_scene,
    "flux": make_flux_diagram,
    "opener": make_opener,
    "timing": make_timing_chart,
    "roadmap": make_roadmap,
    "status": make_status,
    "close": make_close,
}


def make_drawing(name: str) -> Image.Image:
    fn = DRAWERS.get(name)
    if not fn:
        raise KeyError(f"unknown drawing name: {name!r} "
                       f"(known: {list(DRAWERS.keys())})")
    return fn()


# ---------------------------------------------------------------------------
# Standalone: write every drawing to the current folder
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    def _enc(text: str) -> str:
        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()[:8]
        return text.lower().replace(" ", "-") + "-" + h + ".png"

    out_dir = Path(".")
    created: List[Path] = []
    for name in DRAWERS:
        img = make_drawing(name)
        p = out_dir / _enc(name)
        img.save(p, "PNG")
        created.append(p)

    print("wrote", len(created), "drawings:", ", ".join(str(p.name) for p in created))
