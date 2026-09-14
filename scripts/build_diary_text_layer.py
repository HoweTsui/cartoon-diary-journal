#!/usr/bin/env python3
"""Build a portable local-Yozai HTML text layer for a finished diary illustration."""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

from build_diary_prompt import build_prompt, load_brief, validate_brief


SKILL_ROOT = Path(__file__).resolve().parents[1]
LAYOUT = SKILL_ROOT / "assets" / "templates" / "diary-poster-text-layout.json"
FONT_DIR = SKILL_ROOT / "assets" / "fonts" / "yozai"


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def text_lines(draw, value, font, max_width):
    lines, line = [], ""
    for char in value:
        candidate = line + char
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(line)
            line = char
        else:
            line = candidate
    return lines + ([line] if line else [])


def render_png(brief, illustration, output, centers):
    if Image is None:
        raise ValueError("PNG export requires Pillow: python3 -m pip install Pillow")
    with Image.open(illustration) as original:
        image = original.convert("RGBA")
    width, height = image.size
    if abs(width * 4 - height * 3) > 4:
        raise ValueError("final diary poster must be 3:4")
    scale = width / 1200
    regular = ImageFont.truetype(str(FONT_DIR / "Yozai-Regular.ttf"), round(30 * scale))
    title_font = ImageFont.truetype(str(FONT_DIR / "Yozai-Medium.ttf"), round(42 * scale))
    caption_font = ImageFont.truetype(str(FONT_DIR / "Yozai-Regular.ttf"), round(28 * scale))
    draw = ImageDraw.Draw(image)
    ink = "#171715"
    draw.text((width / 2, height * .042), brief["header"], font=regular, fill=ink, anchor="ma")
    draw.text((width / 2, height * .079), brief["title"], font=title_font, fill=ink, anchor="ma")
    lane_width = width * .18
    for center, event in zip(centers, brief["events"]):
        lines = text_lines(draw, event["caption"], caption_font, lane_width)
        draw.multiline_text((width * .85, height * center), "\n".join(lines), font=caption_font,
                            fill=ink, anchor="mm", align="center", spacing=round(5 * scale))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "PNG", optimize=True)


def build(brief_path: Path, illustration: Path, output: Path, preview: bool, anchors_path: Path = None, poster_png: Path = None) -> Path:
    brief_path = brief_path.resolve()
    illustration = illustration.resolve()
    output = output.resolve()
    if output == brief_path or output == illustration:
        raise ValueError("text-layer output must not overwrite an input")
    if output.exists():
        raise ValueError("text-layer output already exists; choose a new review directory")
    if not illustration.is_file():
        raise ValueError("illustration is missing")
    brief = validate_brief(load_brief(brief_path), brief_path.parent, preview)
    if brief["kind"] != "diary":
        raise ValueError("text layer is only for diary briefs")
    build_prompt(brief)  # also integrity-checks the fixed reference pack
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    if layout.get("schemaVersion") != 1:
        raise ValueError("invalid diary text layout")
    anchors = json.loads(anchors_path.read_text(encoding="utf-8")) if anchors_path else None
    if anchors is None:
        raise ValueError("provide --anchors with visually checked scene centers in full-page coordinates")
    centers = anchors.get("sceneCenters", [])
    if (len(centers) != len(brief["events"]) or
            any(isinstance(y, bool) or not isinstance(y, (int, float)) or not .17 < y < .96 for y in centers) or
            any(a >= b for a, b in zip(centers, centers[1:]))):
        raise ValueError("sceneCenters must contain one increasing full-page y fraction per event")
    layout["sceneCenters"] = centers
    output.mkdir(parents=True)
    fonts = output / "fonts"
    fonts.mkdir()
    for name in ("Yozai-Regular.ttf", "Yozai-Medium.ttf", "OFL.txt"):
        shutil.copy2(FONT_DIR / name, fonts / name)
    illustration_copy = output / ("illustration" + illustration.suffix.lower())
    shutil.copy2(illustration, illustration_copy)
    captions = "\n".join(
        f'<p class="caption" data-scene="{index + 1}" style="top:{centers[index] * 100:.2f}%">{e(event["caption"])}</p>'
        for index, event in enumerate(brief["events"])
    )
    output.joinpath("poster.html").write_text(f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(brief['header'])} {e(brief['title'])}</title>
<style>
@font-face{{font-family:Yozai;src:url('fonts/Yozai-Regular.ttf') format('truetype');font-weight:400;font-style:normal}}
@font-face{{font-family:Yozai;src:url('fonts/Yozai-Medium.ttf') format('truetype');font-weight:500;font-style:normal}}
*{{box-sizing:border-box}} html,body{{margin:0;background:#fff}} body{{font-family:Yozai,sans-serif;-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}}
#poster{{position:relative;width:1200px;height:1600px;overflow:hidden;background:#fff;color:#171715}}
#illustration{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0}}
#header{{position:absolute;z-index:1;left:10%;top:2.5%;width:80%;height:12%;padding-top:7px;background:#fff;text-align:center;display:flex;flex-direction:column;align-items:center}}
#date{{font-size:30px;line-height:1.35;letter-spacing:.07em}} #title{{font-size:42px;line-height:1.35;font-weight:500;letter-spacing:.05em}}
#captions{{position:absolute;z-index:1;inset:0;pointer-events:none}}
.caption{{position:absolute;left:76%;width:18%;transform:translateY(-50%);margin:0;font-size:28px;line-height:1.42;overflow-wrap:anywhere}}
</style><body><main id="poster"><img id="illustration" src="{e(illustration_copy.name)}" alt="日记插画">
<section id="header"><div id="date">{e(brief['header'])}</div><div id="title">{e(brief['title'])}</div></section>
<aside id="captions" aria-label="场景备注">{captions}</aside></main></body></html>\n""", encoding="utf-8")
    output.joinpath("text-layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if poster_png:
        poster_png = poster_png.resolve()
        if poster_png == illustration or poster_png == brief_path:
            raise ValueError("poster PNG must not overwrite an input")
        if poster_png.exists():
            raise ValueError("poster PNG already exists; choose a new review path")
        render_png(brief, illustration, poster_png, centers)
    return output / "poster.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--illustration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--anchors", type=Path, required=True, help="JSON with visually verified sceneCenters, normalized against the entire image height")
    parser.add_argument("--poster-png", type=Path, help="optional finished 3:4 PNG with local-Yozai text composited")
    args = parser.parse_args()
    try:
        print(build(args.brief, args.illustration, args.output_dir, args.preview, args.anchors, args.poster_png))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("Text layer failed: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
