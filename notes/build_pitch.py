"""
build_pitch.py
Assemble the Eagle Eye pitch deck from the vector PNGs.

Slides (editorial sequence, not bullet-list):
  1. Cover         — cover-*.png
  2. The idea      — family-*.png   (what it is, in one scene)
  3. How it works  — flux-*.png     (three streams → one world)
  4. The moment    — opener-*.png   (through-wall, plain English)
  5. Timing        — timing-*.png   (≤1.5 s, per-step bars)
  6. Status        — status-*.png   (what's proven vs in progress)
  7. Roadmap       — roadmap-*.png   (M1→M4, honest)
  8. Close         — close-*.png    (one promise, one action)
"""
from __future__ import annotations

import glob
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt, Emu
from pptx.oxml.ns import qn

# ---------------------------------------------------------------- palette
GOLD      = RGBColor(0xFF, 0xB0, 0x20)
GOLD_DIM  = RGBColor(0xC8, 0x86, 0x1A)
CRIMSON   = RGBColor(0xFF, 0x45, 0x3A)
TEAL      = RGBColor(0x2D, 0xC7, 0xB9)
GREEN     = RGBColor(0x34, 0xCF, 0x94)
AMBER     = RGBColor(0xFF, 0xB0, 0x20)
TEXT      = RGBColor(0xC9, 0xD6, 0xD9)
TEXT_DIM  = RGBColor(0x8F, 0xA0, 0xA6)
INVERSE   = RGBColor(0x0C, 0x12, 0x14)
LINE      = RGBColor(0x40, 0x4E, 0x54)

FONT_TITLE   = "Calibri Light"      # display face on dark
FONT_BODY    = "Calibri"            # neutral, reads cleanly
FONT_MONO    = "Consolas"           # numbers / code feel

# ---------------------------------------------------------------- canvas
EMU_PER_IN = 914400
SW_IN, SH_IN = 13.333, 7.5  # 16:9 widescreen


def _slug(name: str) -> str:
    h = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{name.lower().replace(' ', '-')}-{h}"


def _find_png(blob: str) -> Path:
    # match by stable core name, ignoring the trailing hash suffix
    for p in sorted(Path(".").glob("*.png")):
        stem = p.stem
        core = re.sub(r"-[0-9a-f]{8}$", "", stem)
        if core == blob.lower():
            return p
    raise FileNotFoundError(f"no png for {blob!r}")


def _add_full_bleed_image(slide, path: Path) -> None:
    """Place an image filling the entire slide (13.333 x 7.5 in)."""
    slide.shapes.add_picture(str(path), 0, 0, SW_IN * EMU_PER_IN,
                             SH_IN * EMU_PER_IN)


def _blank_slide(prs: Presentation) -> "SlideType":
    layout = prs.slide_layouts[6]  # blank
    return prs.slides.add_slide(layout)


def _rgba(r, g, b, a: float = 0.0) -> Tuple[int, int, int]:
    return (r, g, b)


def _solid_fill(shape, color: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def _no_line(shape) -> None:
    shape.line.fill.background()


def _textbox(slide, left, top, width, height) -> "ShapeType":
    tb = slide.shapes.add_textbox(Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    return tb


def _set_run(run, text: str, size_pt: float, color: RGBColor,
             bold: bool = False, font_name: str = FONT_BODY,
             italic: bool = False) -> None:
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font_name
    run.font.color.rgb = color


def _line(slide, x1, y1, x2, y2, color: RGBColor,
          weight_pt: float = 1.0) -> None:
    """Thin connector line drawn as a thin rectangle (sharp edges)."""
    # Use a connector shape for crisp lines
    connector = slide.shapes.add_connector(
        1,  # straight
        Inches(x1), Inches(y1), Inches(x2), Inches(y2),
    )
    connector.line.color.rgb = color
    connector.line.width = Pt(weight_pt)
    return connector


def _rect(slide, x, y, w, h, fill: Optional[RGBColor] = None,
          line_color: Optional[RGBColor] = None,
          line_weight_pt: float = 1.0, rounded: bool = False,
          radius_pt: float = 0.0) -> "ShapeType":
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    if fill is not None:
        _solid_fill(shape, fill)
    else:
        shape.fill.background()
    if line_color is not None:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(line_weight_pt)
    else:
        shape.line.fill.background()
    if rounded and radius_pt:
        try:
            shape.adjustments[0] = radius_pt / max(w, h)
        except Exception:
            pass
    return shape


# ---------------------------------------------------------------- slide builders


def _title_over_image(slide, title: str, subtitle: str,
                      eyebrow: Optional[str] = None,
                      align: str = "left", top_px: float = 0.0) -> None:
    """Render a title block in the lower-left. Intended for dark slides
    with a clear dark sky area on the right of the image."""
    y = 5.0 + top_px
    if eyebrow:
        tb = _textbox(slide, align == "center" and 1.0 or 1.0, y, 11.3, 0.5)
        p = tb.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if align == "center" else PP_ALIGN.LEFT
        r = p.add_run(); _set_run(r, eyebrow.upper(), 14, GOLD, bold=True)
        y += 0.55
    tb = _textbox(slide, 1.0, y, 11.3, 1.4)
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER if align == "center" else PP_ALIGN.LEFT
    r = p.add_run(); _set_run(r, title, 46, TEXT, bold=True,
                               font_name=FONT_TITLE)
    if subtitle:
        p2 = tb.text_frame.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER if align == "center" else PP_ALIGN.LEFT
        r2 = p2.add_run(); _set_run(r2, subtitle, 20, GOLD, font_name=FONT_BODY)


def _slide_number(slide, n: int, total: int) -> None:
    txt = f"{n:02d} / {total:02d}"
    tb = _textbox(slide, 12.2, 7.05, 1.0, 0.35)
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); _set_run(r, txt, 10, TEXT_DIM, font_name=FONT_MONO)


def _slide_caption(slide, text: str, top: float = 6.7,
                   color: RGBColor = TEXT_DIM) -> None:
    tb = _textbox(slide, 1.0, top, 11.3, 0.5)
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); _set_run(r, text, 13, color, italic=True)


# ---------------------------------------------------------------- deck assembly


def build_deck(out_path: Path, images_dir: Path) -> None:
    prs = Presentation()
    prs.slide_width  = Inches(SW_IN)
    prs.slide_height = Inches(SH_IN)
    prs.slide_master  # touch to ensure initialized
    total = 8

    # 1. Cover
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "cover-3fa405a8.png")
    # gold accent rule at the top
    _line(slide, 1.0, 1.15, 12.333, 1.15, GOLD, 2.0)
    _line(slide, 1.0, 6.35, 12.333, 6.35, LINE, 1.0)
    # eyebrow
    tb = _textbox(slide, 1.0, 1.35, 11.3, 0.45)
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    _set_run(r, "CREW-SHARABLE SITUATIONAL AWARENESS  ·  CIVILIAN COMPUTER VISION",
             14, GOLD, bold=True)
    # title
    tb = _textbox(slide, 1.0, 2.0, 11.3, 1.6)
    p = tb.text_frame.paragraphs[0]
    r = p.add_run(); _set_run(r, "EAGLE EYE", 76, TEXT, bold=True,
                               font_name=FONT_TITLE)
    p2 = tb.text_frame.add_paragraph()
    r2 = p2.add_run()
    _set_run(r2, "Live Shared Detection for Phone Crews",
             30, GOLD, bold=True)
    # tagline strip
    tb = _textbox(slide, 1.0, 6.5, 11.3, 0.55)
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    _set_run(r, "WebXR + WebRTC + YOLOv8n   ·   Zero configuration — works in any room",
             14, TEXT_DIM, font_name=FONT_MONO)

    # 2. The idea
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "family-d34a569a.png")
    title_over = _title_over_image
    title_over(slide, "THREE PHONES — ONE SHARED VIEW",
               "Each phone streams its view and its live ARCore location to one server. "
               "When a person is spotted, every other screen shows a red X at their real "
               "3D position — even through a wall.",
               eyebrow="THE IDEA")

    # 3. How it works
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "flux-a2e10207.png")
    _title_over_image(slide, "HOW IT WORKS",
                      "Three plain streams — ARCore pose, camera frame, video — converge "
                      "in a fusion engine that turns each detection into one real 3D point, "
                      "then broadcasts it to every viewer. Nothing exotic: HTTPS, WebRTC, "
                      "a WebSocket. A phone trusts the cert (one tap), enters AR, and it "
                      "just works.",
                      eyebrow="PROCESS")

    # 4. The moment
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "opener-ac053ed0.png")
    _title_over_image(slide, "YOU DON'T NEED TO BE THERE",
                      "Detections appear on every screen, in every camera's view, within "
                      "about a second — including on a wall that blocks the line of sight.",
                      eyebrow="THE MOMENT")

    # 5. Timing
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "timing-f6cfb8c3.png")
    _title_over_image(slide, "FROM DETECTION TO EVERY SCREEN",
                      "≤ 1.5 seconds, end to end — captured, decoded, detected, fused, "
                      "and broadcast to every viewer. The hard part — locating the person "
                      "in the real room — is done once, then shared everywhere.",
                      eyebrow="TIMING")

    # 6. Status
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "status-073c1634.png")
    # burn a thin status caption under the image
    _caption = _slide_caption
    _caption(slide, "M1–M2 proven  ·  M3 in progress  ·  M4 planned",
             top=6.95, color=GOLD_DIM)

    # 7. Roadmap
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "roadmap-3de15804.png")
    _title_over_image(slide, "ROADMAP",
                      "Today: M1 and M2 are proven, M3 is the current build. M4 makes the "
                      "prototype serious — scene mapping, identity across cameras, "
                      "friend vs enemy. But M3 is what makes it useful right now.",
                      eyebrow="WHAT'S NEXT")

    # 8. Close
    slide = _blank_slide(prs)
    _add_full_bleed_image(slide, images_dir / "close-310ff200.png")
    _line(slide, 1.0, 1.15, 12.333, 1.15, GOLD, 2.0)
    _line(slide, 1.0, 6.35, 12.333, 6.35, LINE, 1.0)
    tb = _textbox(slide, 1.0, 1.35, 11.3, 0.45)
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    _set_run(r, "EAGLE EYE  ·  CIVILIAN COMPUTER-VISION PROTOTYPE",
             14, GOLD, bold=True)
    tb = _textbox(slide, 1.0, 6.5, 11.3, 0.6)
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    _set_run(r, "One person in every view, at their true location, in real time.",
             22, TEXT, bold=False, font_name=FONT_TITLE, italic=True)

    # slide numbers
    for i, s in enumerate(prs.slides, 1):
        _slide_number(s, i, total)

    prs.save(str(out_path))
    print(f"wrote {out_path}  ({len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    build_deck(Path("Eagle_Eye_Pitch_Deck.pptx"), Path("."))
