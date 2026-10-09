"""
build.py — generates the receipt-style GitHub profile README.

Purpose
    RECEIPT below is the single source of truth. Running this script writes:
      receipt/receipt-light.svg   receipt for GitHub's light theme
      receipt/receipt-dark.svg    same receipt, dimmed paper for dark theme
      README.md (repo root)       <picture> that swaps the two + a links line

    Edit RECEIPT, then run:  uv run --with segno python receipt/build.py

Constraints
    - GitHub renders SVGs through <img>, so they cannot load web fonts, run
      scripts, or contain clickable regions. Real links therefore live in the
      line of links under the image.
    - Text uses the viewer's system monospace font, so the layout must not
      depend on glyph widths: centered text, right-anchored values, and dotted
      leaders hidden behind a paper-colored text halo.
    - The QR code needs `segno` (pulled in by `uv run --with segno`). Without
      it a decorative barcode is drawn instead.
"""

import html
import random
from pathlib import Path

OUT = Path(__file__).parent
README = OUT.parent / "README.md"

# --------------------------------------------------------------------------
# Content. Each entry is (kind, *fields):
#   ("center", text)                   centered line
#   ("rule", char)                     full-width separator
#   ("section", text)                  bold section label
#   ("item", left, right, href, note, note_href)  dotted-leader row
#   ("total", left, right)             bold right-aligned totals row
#   ("text", text)                     indented free text
#   ("blank",)                         empty line
#   ("footer",)                        QR code + barcode block
# Links (href) are not clickable inside the image; every item with an href is
# also listed in the links line under the receipt.
# --------------------------------------------------------------------------
GH = "https://github.com/clemmbn/"
RECEIPT = [
    ("center", "HI, I'M CLÉMENT 👨🏼‍💻"),
    ("center", "builder of everyday-life apps"),
    # TODO: remove this line when I graduate
    ("center", "ISAE-SUPAERO · aerospace -> data & ML"),
    ("rule", "="),
    ("section", "SHIPPED"),
    ("item", "typstiz", "OK", GH + "typstiz",
     "Typst/LaTeX typesetting game", None),
    ("item", "Seed", "300 USERS", "https://lnkd.in/p/ednZSQE8",
     "closed. my first true project", None),
    ("item", "auriga-extract", "OK", GH + "auriga-extract",
     "University timetable -> .ics", None),
    ("blank",),
    ("section", "FOR FUN (with a thermal printer)"),
    ("item", "flashcard-printer", "OK", GH + "flashcard-printer", None, None),
    ("item", "mail-printer", "WIP", GH + "mail-printer", None, None),
    ("item", "task-printer", "OK", GH + "task-printer", None, None),
    ("blank",),
    ("section", "IN PROGRESS"),
    ("item", "Legacya", "WIP", None, "succession tool for notaries", None),
    ("blank",),
    ("section", "STARTED, NOT FINISHED"),
    ("item", "Remindy", "SHELVED", None, None, None),
    ("item", "Enigmate", "MAYBE LATER", None, None, None),
    ("item", "Deap", "DREAMING", None, None, None),
    ("rule", "-"),
    ("total", "PROJECTS STARTED", "10"),
    ("total", "PROJECTS FINISHED", "5"),
    ("total", "FINISH RATE", "50%"),
    ("rule", "-"),
    ("section", "NOW PRINTING"),
    ("text", "ML & DL coursework"),
    ("text", "satellite mission optimisation"),
    ("text", "w/ Airbus Defence and Space"),
    ("rule", "="),
    ("center", "building in public on IG & TikTok"),
    ("center", "clemobz.com"),
    ("blank",),
    ("center", "THANK YOU, COME AGAIN"),
    ("footer",),
]
SITE = "https://clemobz.com"


# ================================== SVG ===================================

THEMES = {
    # Paper stays paper in dark mode (a receipt is a physical object); it is
    # only dimmed so it doesn't glare on GitHub's #0d1117 background.
    "light": dict(paper="#fdfcf8", ink="#1f1f1f", soft="#6b6b6b", shadow=0.16),
    "dark": dict(paper="#e6e2d8", ink="#1a1a1a", soft="#5d5a54", shadow=0.55),
}
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
CANVAS_W, PAPER_X, PAPER_W = 400, 20, 360
PAD = 22                      # inner horizontal margin on the paper
LH, NOTE_LH, BLANK_LH = 22, 18, 10
TOOTH = 10                    # zigzag tooth width (px)


def zigzag(x0, x1, y, depth, down):
    """Return path points for a torn receipt edge between x0 and x1 at y.

    down (bool): teeth point downward (bottom edge) when True.
    Returns (list[str]): "x,y" points, left to right.
    """
    pts, x, i = [], x0, 0
    while x <= x1:
        # Alternate between the edge line and the tooth tip
        dy = (depth if down else -depth) if i % 2 else 0
        pts.append(f"{x},{y + dy}")
        x += TOOTH / 2
        i += 1
    return pts


def paper_path(top, bottom, torn_top, torn_bottom):
    """Build the paper outline, optionally with torn top/bottom edges."""
    x0, x1 = PAPER_X, PAPER_X + PAPER_W
    top_pts = zigzag(x0, x1, top + 5, 5, False) if torn_top else [f"{x0},{top}", f"{x1},{top}"]
    bot_pts = zigzag(x0, x1, bottom - 5, 5, True) if torn_bottom else [f"{x0},{bottom}", f"{x1},{bottom}"]
    return "M" + " L".join(top_pts + list(reversed(bot_pts))) + " Z"


def qr_rects(url, x, y, scale):
    """Return SVG <rect>s for a QR code of `url`, or None if segno is missing.

    Trade-off: drawing modules as rects (vs. segno's own SVG output) lets the
    QR inherit the receipt's ink color and sit inside our coordinate system.
    """
    try:
        import segno
    except ImportError:
        print("[build] segno not installed -> barcode instead of QR")
        return None, 0
    qr = segno.make(url, error="m", boost_error=False)
    rects = []
    for r, row in enumerate(qr.matrix):
        for c, on in enumerate(row):
            if on:
                rects.append(f'<rect x="{x + c * scale}" y="{y + r * scale}" width="{scale}" height="{scale}"/>')
    return "".join(rects), len(qr.matrix) * scale


def barcode(cx, y, h):
    """Return a deterministic decorative barcode centered on cx."""
    rnd = random.Random("clemmbn")  # fixed seed so rebuilds don't churn diffs
    bars, x = [], 0
    while x < 200:
        w = rnd.choice([1, 1, 2, 3])
        if rnd.random() > 0.35:
            bars.append((x, w))
        x += w + rnd.choice([1, 2, 2])
    off = cx - x / 2
    return "".join(f'<rect x="{off + bx:.0f}" y="{y}" width="{bw}" height="{h}"/>' for bx, bw in bars)


def svg_rows(entries, t, y):
    """Render receipt entries as SVG elements starting at height y.

    entries (list): slice of RECEIPT. t (dict): theme colors.
    Returns (str, float): SVG markup and the y after the last row.
    """
    left, right, cx = PAPER_X + PAD, PAPER_X + PAPER_W - PAD, CANVAS_W / 2
    halo = f'paint-order="stroke" stroke="{t["paper"]}" stroke-width="8" stroke-linejoin="round"'
    out = []
    for kind, *f in entries:
        if kind == "center":
            # The greeting is the receipt's "store name": larger and bold
            title = f[0].startswith("HI,")
            weight = ' font-weight="700"' if title or f[0] == "THANK YOU, COME AGAIN" else ""
            y += LH + (6 if title else 0)
            out.append(f'<text x="{cx}" y="{y}" text-anchor="middle" font-size="{19 if title else 14}"'
                       f'{weight}>{html.escape(f[0])}</text>')
        elif kind == "rule":
            y += LH * 0.7
            dash = "6 4" if f[0] == "-" else "none"
            width = 1 if f[0] == "-" else 1.6
            out.append(f'<line x1="{left}" x2="{right}" y1="{y}" y2="{y}" stroke="{t["ink"]}" '
                       f'stroke-width="{width}" stroke-dasharray="{dash}"/>')
            y += LH * 0.3
        elif kind == "section":
            y += LH
            out.append(f'<text x="{left}" y="{y}" font-weight="700" letter-spacing="1">{html.escape(f[0])}</text>')
        elif kind in ("item", "total"):
            y += LH
            l, r = f[0], f[1]
            weight = ' font-weight="700"' if kind == "total" else ""
            if kind == "item":
                # Dots run the full width; the text halo erases them under the
                # words, so the leader adapts to any font's glyph widths.
                out.append(f'<line x1="{left}" x2="{right}" y1="{y - 4}" y2="{y - 4}" stroke="{t["soft"]}" '
                           f'stroke-width="1.4" stroke-dasharray="0.1 4.5" stroke-linecap="round"/>')
            out.append(f'<text x="{left}" y="{y}" {halo}{weight}>{html.escape(l)}</text>')
            out.append(f'<text x="{right}" y="{y}" text-anchor="end" {halo}{weight}>{html.escape(r)}</text>')
            note = f[3] if kind == "item" else None
            if note:
                y += NOTE_LH
                out.append(f'<text x="{left + 14}" y="{y}" font-size="12" fill="{t["soft"]}">{html.escape(note)}</text>')
        elif kind == "text":
            y += NOTE_LH + 2
            out.append(f'<text x="{left + 14}" y="{y}">{html.escape(f[0])}</text>')
        elif kind == "blank":
            y += BLANK_LH
        elif kind == "footer":
            y += 14
            qr, size = qr_rects(SITE, cx - 0, y, 3)
            if qr:
                # QR on the right, barcode on the left: scannable from a screen
                qx = right - size
                qr, size = qr_rects(SITE, qx, y, 3)
                out.append(f'<g fill="{t["ink"]}">{qr}</g>')
                out.append(f'<g fill="{t["ink"]}">{barcode(left + (qx - left) / 2 - 8, y + 10, size - 30)}</g>')
                out.append(f'<text x="{left + (qx - left) / 2 - 8}" y="{y + size - 4}" text-anchor="middle" '
                           f'font-size="11" fill="{t["soft"]}" letter-spacing="3">CLEMMBN</text>')
                y += size + 6
            else:
                out.append(f'<g fill="{t["ink"]}">{barcode(cx, y, 46)}</g>')
                y += 52
    return "\n  ".join(out), y


def svg_doc(entries, theme, torn_top=True, torn_bottom=True):
    """Wrap rendered rows in a full SVG document with paper + shadow.

    Returns (str): standalone SVG; height is computed from the content.
    """
    t = THEMES[theme]
    top = 6
    body, y = svg_rows(entries, t, top + (16 if torn_top else 4))
    bottom = y + (24 if torn_bottom else 12)
    h = bottom + 10
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{h:.0f}" viewBox="0 0 {CANVAS_W} {h:.0f}" role="img">
  <defs>
    <filter id="s" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="{t["shadow"]}"/>
    </filter>
  </defs>
  <path d="{paper_path(top, bottom, torn_top, torn_bottom)}" fill="{t["paper"]}" filter="url(#s)"/>
  <g font-family="{FONT}" font-size="14" fill="{t["ink"]}">
  {body}
  </g>
</svg>
'''


def write(path, content):
    """Write a generated file (path: Path) and log its size."""
    path.write_text(content, encoding="utf-8")
    print(f"[build] wrote {path.relative_to(OUT.parent)} ({len(content)} bytes)")


def readme():
    """Return the README markup: themed <picture> + a line of real links.

    GitHub wraps <picture> in its themed-picture element, so the dark source
    follows GitHub's theme setting, not only the OS.
    """
    links = " · ".join(
        f'<a href="{f[2]}">{f[0]}</a>' for k, *f in RECEIPT if k == "item" and f[2]
    )
    alt = "A receipt listing Clément's projects: shipped, for fun, in progress and unfinished."
    return (
        "<!-- Generated by receipt/build.py: edit RECEIPT there, then rebuild. -->\n"
        '<p align="center"><picture>'
        '<source media="(prefers-color-scheme: dark)" srcset="receipt/receipt-dark.svg">'
        f'<img src="receipt/receipt-light.svg" width="380" alt="{html.escape(alt)}">'
        "</picture></p>\n\n"
        f'<p align="center"><sub>{links} · <a href="{SITE}">clemobz.com</a></sub></p>\n'
    )


if __name__ == "__main__":
    print(f"[build] {len(RECEIPT)} receipt entries")
    for theme in THEMES:
        write(OUT / f"receipt-{theme}.svg", svg_doc(RECEIPT, theme))
    write(README, readme())
    print("[build] done")
