#!/usr/bin/env python3
"""Render a terminal-style PNG of a real mcp-verified CLI session.

The text rendered below is the *verbatim* output of the quickstart commands
(`mcp-verified version` and `mcp-verified audit ... --provider mock`); the raw
captures also live under ``docs/demo/cli/``. This script only paints that real
output onto a terminal-themed canvas so the README has a visual demo asset.

Usage:
    python scripts/render_demo.py            # writes docs/demo/quickstart.png

Dependencies: Pillow only (a docs/dev tool; not a runtime dependency of the
package, which ships zero runtime PyPI deps).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Catppuccin Mocha palette (terminal-friendly, high contrast).
BG = (30, 30, 46)
BAR = (49, 50, 68)
FG = (205, 214, 244)
DIM = (108, 112, 134)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
BLUE = (137, 180, 250)

# (kind, text) — kind drives the color. Text is the real CLI session.
SESSION = [
    ("prompt", "mcp-verified version"),
    ("out", "0.1.0"),
    ("blank", ""),
    ("prompt", "mcp-verified audit \\"),
    ("cont", "    --fixture tests/fixtures/registry-snapshot-2026-05-28.json \\"),
    ("cont", "    --top 3 --provider mock --out my-audit"),
    ("out", "audited=3  verified=0  caution=0  risky=1  unknown=2  timeout=0  error=0"),
    ("blank", ""),
    ("prompt", "cat my-audit/audits/github.com/frumu-ai/tandem/.../security-assessment.md"),
    ("head", "# Security assessment"),
    ("out", "  Target    https://github.com/frumu-ai/tandem"),
    ("verdict", "  Verdict   risky"),
    ("out", "  Findings  28 high   (EXEC-EXEC-CALL, CWE-95)"),
    ("dim", "  Provider  mock  -  no network  -  no code execution  -  local-first"),
]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/CascadiaMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _color(kind: str) -> tuple[int, int, int]:
    return {
        "prompt": FG,
        "cont": FG,
        "out": FG,
        "head": BLUE,
        "verdict": RED,
        "dim": DIM,
        "blank": FG,
    }[kind]


def main() -> None:
    font = _load_font(22)
    bar_font = _load_font(20)

    pad = 28
    line_h = 34
    bar_h = 52
    width = 1180
    height = bar_h + pad * 2 + line_h * len(SESSION)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # Title bar with traffic-light dots.
    d.rectangle([0, 0, width, bar_h], fill=BAR)
    cy = bar_h // 2
    for i, col in enumerate(((237, 106, 94), (245, 191, 79), (98, 197, 84))):
        d.ellipse([20 + i * 26, cy - 8, 36 + i * 26, cy + 8], fill=col)
    title = "mcp-verified  -  quickstart (provider=mock, no network)"
    tb = d.textbbox((0, 0), title, font=bar_font)
    d.text(
        ((width - (tb[2] - tb[0])) / 2, cy - (tb[3] - tb[1]) / 2 - 2),
        title,
        font=bar_font,
        fill=DIM,
    )

    y = bar_h + pad
    for kind, text in SESSION:
        x = pad
        if kind in ("prompt",):
            d.text((x, y), "$ ", font=font, fill=GREEN)
            w = d.textlength("$ ", font=font)
            d.text((x + w, y), text, font=font, fill=FG)
        elif kind == "verdict":
            # paint the "risky" token red, rest dim-fg
            label, _, val = text.partition("risky")
            d.text((x, y), label, font=font, fill=FG)
            w = d.textlength(label, font=font)
            d.text((x + w, y), "risky", font=font, fill=RED)
        else:
            d.text((x, y), text, font=font, fill=_color(kind))
        y += line_h

    out = Path(__file__).resolve().parent.parent / "docs" / "demo" / "quickstart.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out}  ({width}x{height})")


if __name__ == "__main__":
    main()
