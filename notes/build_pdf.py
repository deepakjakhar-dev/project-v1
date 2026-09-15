"""
build_pdf.py
Render the Eagle Eye pitch deck to a PDF directly from PIL, re-creating the
exact same on-slide text that the PPTX builder places, so the PDF and PPTX
are visually identical.

Page size: 13.333 x 7.5 in at 150 DPI → 2000 x 1125 px.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from build_pitch import (FONT_BODY, FONT_MONO, FONT_TITLE, GOLD, GOLD_DIM,
                         CRIMSON, TEAL, GREEN, AMBER, TEXT, TEXT_DIM, LINE,
                         _slug, _find_png)

DPI = 150
PW_IN, PH_IN = 13.333, 7.5
W = int(PW_IN * DPI)   # 2000
H = int(PH_IN * DPI)   # 1125


def _fp(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    names = [FONT_MONO if mono else FONT_BODY, "Calibri"]
    if bold:
        alt: list[str] = []
        for n in names:
            # try bold variant by name if available
            alt.append(n.replace("Calibri", "Calibri Bold")
                       .replace("Consolas", "Consolas Bold")
                       .replace("Calibri Light", "Calibri Light"))
        names = alt + names
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    # ultimate fallback — no crash, keeps text legible
    try:
        return ImageFont.truetype("DejaVuSans" + ("-Bold" if bold else ""), size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _rgb(t) -> tuple:
    return (t[0], t[1], t[2])


def _text_centered(d: ImageDraw.ImageDraw, cx: int, y: int, s: str,
                   color, font: ImageFont.FreeTypeFont) -> None:
    d.text((cx, y), s, font=font, fill=color, anchor="mm")


def _text_left(d: ImageDraw.ImageDraw, x: int, y: int, s: str,
               color, font: ImageFont.FreeTypeFont) -> None:
    d.text((x, y), s, font=font, fill=color, anchor="la")


def _line_h(d: ImageDraw.ImageDraw, y: int, color, width_px: int = 1,
            x0: int = 0, x1: int = W) -> None:
    d.line([(x0, y), (x1, y)], fill=color, width=width_px)


# ---------------------------------------------------------------- scene renderers
# These mirror the PPTX builders' placed text exactly.


def _cover(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _line_h(d, int(H * 0.1533), GOLD, 3)      # 1.15in top accent
    _line_h(d, int(H * 0.8467), LINE, 1)      # 6.35in bottom rule
    _text_left(d, int(W * 0.075), int(H * 0.177),
               "CREW-SHARABLE SITUATIONAL AWARENESS  ·  CIVILIAN COMPUTER VISION",
               GOLD, _fp(int(H * 0.018), bold=True))
    _text_left(d, int(W * 0.075), int(H * 0.266), "EAGLE EYE",
               TEXT, _fp(int(H * 0.065), bold=True, mono=False))
    _text_left(d, int(W * 0.075), int(H * 0.413),
               "Live Shared Detection for Phone Crews",
               GOLD, _fp(int(H * 0.026), bold=True))
    _text_left(d, int(W * 0.075), int(H * 0.866),
               "WebXR + WebRTC + YOLOv8n   ·   Zero configuration — works in any room",
               TEXT_DIM, _fp(int(H * 0.012), mono=True))
    _slide_num(d, 1)


def _idea(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _box(d, int(H * 0.04), int(H * 0.65), W - int(W * 0.15), int(H * 0.18),
         eyebrow="THE IDEA",
         title="THREE PHONES — ONE SHARED VIEW",
         sub=("Each phone streams its view and its live ARCore location to one server. "
              "When a person is spotted, every other screen shows a red X at their real "
              "3D position — even through a wall."))
    _slide_num(d, 2)


def _process(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _box(d, int(H * 0.04), int(H * 0.62), W - int(W * 0.15), int(H * 0.22),
         eyebrow="PROCESS",
         title="HOW IT WORKS",
         sub=("Three plain streams — ARCore pose, camera frame, video — converge in a "
              "fusion engine that turns each detection into one real 3D point, then "
              "broadcasts it to every viewer. Nothing exotic: HTTPS, WebRTC, a "
              "WebSocket. A phone trusts the cert (one tap), enters AR, and it just "
              "works."))
    _slide_num(d, 3)


def _moment(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _box(d, int(H * 0.04), int(H * 0.65), W - int(W * 0.15), int(H * 0.2),
         eyebrow="THE MOMENT",
         title="YOU DON'T NEED TO BE THERE",
         sub=("Detections appear on every screen, in every camera's view, within about "
              "a second — including on a wall that blocks the line of sight."))
    _slide_num(d, 4)


def _timing(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _box(d, int(H * 0.04), int(H * 0.62), W - int(W * 0.15), int(H * 0.22),
         eyebrow="TIMING",
         title="FROM DETECTION TO EVERY SCREEN",
         sub=("≤ 1.5 seconds, end to end — captured, decoded, detected, fused, and "
              "broadcast to every viewer. The hard part — locating the person in the "
              "real room — is done once, then shared everywhere."))
    _slide_num(d, 5)


def _status(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _line_h(d, int(H * 0.9267), GOLD_DIM, 1, x0=int(W * 0.075),
            x1=int(W * 0.925))
    _text_centered(d, W // 2, int(H * 0.9267), "M1–M2 proven  ·  M3 in progress  ·  M4 planned",
                   GOLD_DIM, _fp(int(H * 0.015), bold=True))
    _slide_num(d, 6)


def _roadmap(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _box(d, int(H * 0.04), int(H * 0.62), W - int(W * 0.15), int(H * 0.22),
         eyebrow="WHAT'S NEXT",
         title="ROADMAP",
         sub=("Today: M1 and M2 are proven, M3 is the current build. M4 makes the "
              "prototype serious — scene mapping, identity across cameras, friend vs "
              "enemy. But M3 is what makes it useful right now."))
    _slide_num(d, 7)


def _close(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    d._image.paste(img, (0, 0))
    _line_h(d, int(H * 0.1533), GOLD, 3)
    _line_h(d, int(H * 0.8467), LINE, 1)
    _text_left(d, int(W * 0.075), int(H * 0.177),
               "EAGLE EYE  ·  CIVILIAN COMPUTER-VISION PROTOTYPE",
               GOLD, _fp(int(H * 0.018), bold=True))
    _text_left(d, int(W * 0.075), int(H * 0.866),
               "One person in every view, at their true location, in real time.",
               TEXT, _fp(int(H * 0.02), bold=False))
    _slide_num(d, 8)


def _slide_num(d: ImageDraw.ImageDraw, n: int) -> None:
    s = f"{n:02d} / 08"
    fnt = _fp(int(H * 0.009), mono=True)
    bb = d.textbbox((0, 0), s, font=fnt)
    tw = bb[2] - bb[0]
    d.text((W - int(W * 0.075) - tw, int(H * 0.934)), s,
           font=fnt, fill=TEXT_DIM, anchor="la")


def _box(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
         eyebrow: str, title: str, sub: str) -> None:
    # subtle dark backing plate so text stays readable over art
    plate = Image.new("RGBA", (w, h), (10, 16, 19, 200))
    d._image.paste(plate, (x, y), plate)
    fnt_ey = _fp(int(H * 0.013), bold=True)
    fnt_ti = _fp(int(H * 0.032), bold=True, mono=False)
    fnt_su = _fp(int(H * 0.014))
    _text_left(d, x + int(W * 0.075), y + int(H * 0.06), eyebrow.upper(),
               GOLD, fnt_ey)
    _text_left(d, x + int(W * 0.075), y + int(H * 0.12), title,
               TEXT, fnt_ti)
    # wrap subtitle manually
    max_w = w - int(W * 0.15)
    words = sub.split(" ")
    lines: list[str] = []
    cur: list[str] = []
    for w_ in words:
        trial = " ".join(cur + [w_])
        bb = d.textbbox((0, 0), trial, font=fnt_su)
        if bb[2] - bb[0] > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w_]
        else:
            cur.append(w_)
    if cur:
        lines.append(" ".join(cur))
    yy = y + int(H * 0.24)
    for ln in lines:
        _text_left(d, x + int(W * 0.075), yy, ln, TEXT_DIM, fnt_su)
        yy += int(H * 0.022)


RENDERERS: dict[str, callable] = {
    "cover":     _cover,
    "family":    _idea,
    "flux":      _process,
    "opener":    _moment,
    "timing":    _timing,
    "status":    _status,
    "roadmap":   _roadmap,
    "close":     _close,
}

ORDER = ["cover", "family", "flux", "opener", "timing", "status", "roadmap", "close"]


def build_pdf(out_path: Path, images_dir: Path) -> None:
    pages: list[Image.Image] = []
    for name in ORDER:
        blob = RENDERERS[name]
        png = _find_png(name)
        img = Image.open(png).convert("RGB")
        page = Image.new("RGB", (W, H), (12, 18, 20))
        drawer = ImageDraw.Draw(page)
        blob(drawer, img)
        pages.append(page)
    # write multi-page PDF
    if pages:
        pages[0].save(out_path, "PDF", resolution=DPI, save_all=True,
                      append_images=pages[1:])
    out = Path(out_path)
    print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build_pdf(Path("Eagle_Eye_Pitch_Deck.pdf"), Path("."))
