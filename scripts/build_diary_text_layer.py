#!/usr/bin/env python3
"""Build a portable local-Yozai HTML text layer for a finished diary illustration."""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

from build_diary_prompt import build_prompt, load_brief, validate_brief


SKILL_ROOT = Path(__file__).resolve().parents[1]
LAYOUT = SKILL_ROOT / "assets" / "templates" / "diary-poster-text-layout.json"
FONT_DIR = SKILL_ROOT / "assets" / "fonts" / "yozai"


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def build(brief_path: Path, illustration: Path, output: Path, preview: bool, anchors_path: Path = None) -> Path:
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
    return output / "poster.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--illustration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--anchors", type=Path, required=True, help="JSON with visually verified sceneCenters, normalized against the entire image height")
    args = parser.parse_args()
    try:
        print(build(args.brief, args.illustration, args.output_dir, args.preview, args.anchors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("Text layer failed: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
