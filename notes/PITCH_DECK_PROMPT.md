# Eagle Eye — Pitch Deck: Full Build Prompt

> Copy everything below the line into a capable coding agent (or hand it to a designer).
> It is self-contained: no other context is needed to produce the deck.

---

## The prompt

You are the design lead at a studio known for decks that never look templated.
Build an **8-slide investor/demo pitch deck for "Eagle Eye"** and deliver it as
**both a 16:9 PPTX and a matching PDF**, rendered at presentation quality —
not a bullet list with clip art. Work in two passes: first a short design plan
(palette, type, layout, principles), review it against this brief, then build.

### 1. Product context (use this, do not invent)

**Eagle Eye** is a civilian computer-vision prototype inspired by the shared
situational-awareness concept of military AR systems:

- 2–3 phones run a WebXR AR page in the browser (Android Chrome, ARCore).
- Each phone streams its **live ARCore pose** (x, y, z + quaternion, ~30 FPS)
  and its **camera frames** to one server over HTTPS WebSockets — one-tap
  certificate trust, no app install, no room scanning, no markers, no setup.
- The server runs **YOLOv8n** on every frame, converts each person detection
  into **one real 3D world point** (camera pose × bbox-height monocular depth),
  and broadcasts a JSON **world state** (`/world`) to every viewer.
- Every other phone's overlay draws a **red X at the person's true location** —
  including projected onto a wall when the person is behind it (occlusion from
  one camera is covered by another camera's information; nothing "sees through
  walls" literally — say it plainly, never as magic).
- Honest status: Milestones M1–M2 **proven** (WebXR pose+frame streaming, live
  YOLO detection, fusion math verified end-to-end offline), M3 **in progress**
  (multi-camera shared world on real phones), M4 **planned** (scene mapping,
  cross-camera identity, friend-vs-enemy).
- Key numbers you may use: **≤ 1.5 s** detection-to-every-screen end to end;
  ~30 FPS pose; one tap to trust; **zero configuration**.

### 2. Audience and job of the deck

Technical-early adopters and non-technical stakeholders in the same room.
The deck's single job: make them *feel* the one moment — **"you don't need to
be there to know they're there"** — and believe the status is real, not vapor.
Every slide supports that; cut anything that doesn't.

### 3. Design system (follow exactly)

**Mood:** dark, cinematic, tactical-but-civilian. Precision instrument, not
gamer RGB, not corporate SaaS. The one memorable element is the **crimson X
marker** — spend all boldness there and keep everything else quiet.

**Palette (hex, use only these):**

| Role | Hex |
|---|---|
| Background (dark) | `#0C1214` |
| Background (slate panels) | `#161E22` |
| Panel fill | `#1C2529` |
| Panel soft | `#222D32` |
| Hairlines | `#404E54` / soft `#303C42` |
| Text | `#C9D6D9` |
| Text dim | `#8FA0A6` |
| **Accent gold (brand)** | `#FFB020` (dim `#BE8418`) |
| **Crimson X (the motif)** | `#FF453A` (dim `#B23028`) |
| Signal blue (data flow) | `#42CEF0` |
| Green (verified/ok) | `#34CF94` |

**Type:** exactly three roles, no more —
- Display/headlines: **Calibri Light** (or a similar humanist light), bold weight, large.
- Body/subtitles: **Calibri**, 18–22 pt, sentence case.
- Numbers/meta/page numbers: **Consolas** (mono), 10–14 pt.
- Never all-caps body text. Headlines may be caps. Eyebrows are small gold caps.

**Layout:** 1600×900 px artboard per slide (→ 13.333 × 7.5 in PPTX).
One idea per slide. Full-bleed artwork; headline block sits lower-left or on a
clear dark area; a thin gold rule and mono page number (`01 / 08`) as the only
recurring chrome. Left-aligned text except the cover and close, which are
centered. Generous margins (~80 px at 1600 px width).

**Visual language (the signature):**
- People and rooms drawn as **thin stroke-only silhouettes** (1–2 px lines),
  never filled blobs, never stock illustrations.
- Data flows as **dashed signal-blue lines** ending in small solid dots.
- Rooms drawn in simple 1-point perspective: one floor line, one back-wall
  line, one diagonal side wall.
- The **red X** is two crossing 2–4 px strokes, always crimson, always the
  brightest thing near it. It appears on every content slide exactly once
  (or once per mini-scene).
- Cameras are minimal rounded-rect phone glyphs with a gold outline.
- Backgrounds get a subtle vertical vignette (dark → slightly darker), nothing else.

**Principles:**
1. One idea per slide; if a slide needs a paragraph, it's two slides.
2. The X does the selling; type stays disciplined.
3. Honest status over hype — "M1–M2 proven · M3 in progress" beats "world-changing AI".
4. Consistency: same palette, same line weights, same corner radius everywhere.

### 4. Slide-by-slide spec (exact copy)

**Slide 1 — Cover** (`cover`)
- Eyebrow (gold caps, small): `CREW-SHARABLE SITUATIONAL AWARENESS · CIVILIAN COMPUTER VISION`
- Title: `EAGLE EYE` (76 pt) with subtitle `Live Shared Detection for Phone Crews` (30 pt gold)
- Right side: stroke-only figure holding a phone (hand-drawn silhouette, gold phone outline).
- Bottom meta strip (mono, dim): `WebXR + WebRTC + YOLOv8n · Zero configuration — works in any room`
- Gold rule top, dim rule bottom, corner arc marks.

**Slide 2 — The idea** (`family`)
- Eyebrow: `THE IDEA`
- Headline: `THREE PHONES — ONE SHARED VIEW`
- Subtitle: "Each phone streams its view and its live ARCore location to one server. When a person is spotted, every other screen shows a red X at their real 3D position — even through a wall."
- Visual: three phone glyphs (CAM 1/2/3) at bottom, dashed blue streams rising into a "SHARED WORLD STATE" panel containing three mini-scenes (wall + person + red X), each labeled CAM n view.
- Bottom caption: "No markers. No tape. No setup. Each phone locates itself live via ARCore; detections land in one shared 3D space."

**Slide 3 — How it works** (`flux`)
- Eyebrow: `PROCESS`
- Headline: `HOW IT WORKS`
- Subtitle: "Three plain streams — ARCore pose, camera frame, video — converge in a fusion engine that turns each detection into one real 3D point, then broadcasts it to every viewer. Nothing exotic: HTTPS, WebRTC, a WebSocket. A phone trusts the cert (one tap), enters AR, and it just works."
- Visual: pipeline diagram — three CAM nodes → `FUSION ENGINE` ("pose × bbox → 3D point per person") → `WORLD STATE` ("/world JSON — every track at true location") → `VIEWERS` ("live red-X overlays on every screen"); arrows colored signal-blue → amber → crimson respectively.

**Slide 4 — The moment** (`opener`)
- Eyebrow: `THE MOMENT`
- Headline: `YOU DON'T NEED TO BE THERE`
- Subtitle: "Detections appear on every screen, in every camera's view, within about a second — including on a wall that blocks the line of sight."
- Visual: 3×5 grid of small camera-view scenes (street / room / dark room / walls / corridor / pair — thin silhouettes); the center cell glows crimson and carries the red X; a soft radial crimson spotlight behind the grid. Side panel lists four dot-bullets: Real-time · Shared · Through walls ("wall occlusion handled by projection, not magic") · No setup.

**Slide 5 — Timing** (`timing`)
- Eyebrow: `TIMING`
- Headline: `FROM DETECTION TO EVERY SCREEN`
- Subtitle: "≤ 1.5 seconds, end to end — captured, decoded, detected, fused, and broadcast to every viewer. The hard part — locating the person in the real room — is done once, then shared everywhere."
- Visual: horizontal per-step latency bars (capture → decode → YOLO detect → fuse → broadcast) in gold with the total called out ≤ 1.5 s; mono numbers.

**Slide 6 — Status** (`status`)
- Caption only (this slide is a visual status board, no headline block):
  `M1–M2 proven · M3 in progress · M4 planned` (gold-dim, bottom center)
- Visual: checklist board — green checks on proven items (pose streaming ~30 FPS, live YOLO person detection, fusion math verified, one-tap trust), amber "in progress" on shared multi-camera world, dim "planned" on scene mapping / identity / friend-vs-enemy.

**Slide 7 — Roadmap** (`roadmap`)
- Eyebrow: `WHAT'S NEXT`
- Headline: `ROADMAP`
- Subtitle: "Today: M1 and M2 are proven, M3 is the current build. M4 makes the prototype serious — scene mapping, identity across cameras, friend vs enemy. But M3 is what makes it useful right now."
- Visual: horizontal M1→M4 timeline, proven segments green, current segment gold, future segments dim hairline.

**Slide 8 — Close** (`close`)
- Eyebrow: `EAGLE EYE · CIVILIAN COMPUTER-VISION PROTOTYPE`
- Closing CTA (two lines, 22 pt, centered):
  "Put three phones in three rooms, point them, and one person in any of those rooms / shows up for every other screen — at their real location, through walls, in seconds."
- Mirror the cover's rules and corner marks.

### 5. Build pipeline (if you are a coding agent)

Generate everything with code — no screenshots, no external assets:

1. **Visuals** — Python + Pillow (`PIL`), one script producing nine 1600×900
   RGB PNGs (one per slide), all palette colors from the table above, thin
   stroke silhouettes, dashed flows, vignettes. Name them
   `cover-*.png, family-*.png, flux-*.png, opener-*.png, timing-*.png,
   status-*.png, roadmap-*.png, close-*.png` (a hash suffix is fine).
2. **Deck** — `python-pptx`: 16:9 (13.333 × 7.5 in), blank layout, one
   full-bleed picture per slide (exactly one picture per slide, covering
   0,0→13.333,7.5 in), then the headline/eyebrow/subtitle/page-number text
   boxes on top in the fonts and colors specified. Save as
   `Eagle_Eye_Pitch_Deck.pptx`.
3. **PDF** — save the same presentation to `Eagle_Eye_Pitch_Deck.pdf`.
4. **Verify** — re-open the PPTX: 8 slides, every slide has exactly one
   full-bleed image, no text overflow; open the PDF and confirm 8 pages.

### 6. Quality bar (reject your own first draft against this)

- No clip art, no stock photos, no gradient washes, no drop shadows under cards.
- Not the SaaS-card kit: no identical rounded cards with the same shadow everywhere.
- No tracked-out ALL-CAPS eyebrows on body content — eyebrows only on the six headline blocks.
- Consistent line weights and corner radii; one accent color doing one job per slide.
- Reads at 3 m: headline legible, X visible, numbers mono and exact.
- Accessible floor: text contrast ≥ 4.5:1 against its background, nothing conveyed by color alone without a label.

### 7. Acceptance checklist

- [ ] 8 slides, 16:9, PPTX + PDF, same visual content
- [ ] Every slide: exactly one full-bleed image + headline block or caption + mono page number
- [ ] Red X appears as specified per slide, always crimson `#FF453A`
- [ ] Copy matches section 4 verbatim (no embellishments, no "revolutionary")
- [ ] Status slide is honest: M1–M2 proven, M3 in progress, M4 planned
- [ ] Deck opens correctly in PowerPoint and any PDF viewer

### 8. Deliverables

- `Eagle_Eye_Pitch_Deck.pptx`
- `Eagle_Eye_Pitch_Deck.pdf`
- The generator scripts (visuals + deck) so any slide can be regenerated or reworded in seconds.
