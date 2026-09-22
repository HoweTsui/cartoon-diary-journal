#!/usr/bin/env python3
"""Lay out public README artwork from approved fictional sprites; no AI redraw."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from build_action_trial import build, load_action, LIBRARY

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / 'assets/fonts/yozai/Yozai-Regular.ttf'
SCALE = 2


def font(size):
    return ImageFont.truetype(str(FONT), round(size * SCALE))


def text(draw, xy, value, size, anchor='la'):
    draw.text(tuple(round(v * SCALE) for v in xy), value, font=font(size),
              fill='#171715', anchor=anchor)


def place(canvas, source, box):
    x, y, w, h = box
    ratio = min(w * SCALE / source.width, h * SCALE / source.height)
    size = (round(source.width * ratio), round(source.height * ratio))
    left = round((x + w / 2) * SCALE - size[0] / 2)
    top = round((y + h / 2) * SCALE - size[1] / 2)
    canvas.alpha_composite(source.convert('RGBA').resize(size, Image.Resampling.LANCZOS), (left, top))


def save(canvas, path):
    canvas.convert('RGB').resize((canvas.width // SCALE, canvas.height // SCALE),
        Image.Resampling.LANCZOS).save(path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        demo = build(Path(tmp) / 'public-demo')
        shutil.copyfile(demo / 'poster.png', args.output_dir / 'diary-poster.png')
        reuse = json.loads((demo / 'reuse-record.json').read_text())
    with Image.open(args.output_dir / 'diary-poster.png') as original:
        poster = original.copy()
    cover = Image.new('RGBA', (1280 * SCALE, 720 * SCALE), 'white')
    draw = ImageDraw.Draw(cover)
    for y in range(64, 720, 65):
        draw.line((0, y * SCALE, 1280 * SCALE, y * SCALE), fill='#d9f1f6', width=SCALE)
    text(draw, (64, 67), '小屁孩日记 · Codex Skill', 25)
    text(draw, (64, 145), '把日常，', 68)
    text(draw, (64, 231), '画进日记。', 68)
    text(draw, (64, 351), '一段经历，几张照片。', 30)
    text(draw, (64, 400), '留下一页海报，慢慢收成一本日记。', 30)
    for x, label in zip((64, 198, 332), ('日记正文', '人物形象', '海报收藏')):
        draw.rounded_rectangle((x * SCALE, 484 * SCALE, (x + 118) * SCALE, 538 * SCALE),
                               radius=9 * SCALE, fill='white', outline='#171715', width=SCALE)
        text(draw, (x + 59, 510), label, 23, 'mm')
    place(cover, poster, (798, 34, 450, 600))
    draw.rectangle((798 * SCALE, 34 * SCALE, 1248 * SCALE, 634 * SCALE), outline='#d0d0d0', width=SCALE)
    text(draw, (928, 660), '每天一页，翻回那一天。', 23)
    save(cover, args.output_dir / 'cover.png')
    catalog = json.loads(LIBRARY.read_text())
    board = Image.new('RGBA', (1280 * SCALE, 800 * SCALE), 'white')
    draw = ImageDraw.Draw(board)
    text(draw, (48, 34), '同一套角色，六个常用动作', 36)
    for index, entry in enumerate(catalog['actions']):
        x, y = 32 + (index % 3) * 416, 110 + (index // 3) * 334
        draw.rounded_rectangle((x * SCALE, y * SCALE, (x + 392) * SCALE, (y + 310) * SCALE),
                               radius=12 * SCALE, outline='#ddd', width=SCALE)
        sprite, _ = load_action(entry['id'])
        place(board, sprite, (x + 24, y + 18, 344, 226))
        text(draw, (x + 196, y + 275), entry['label'], 24, 'mm')
    save(board, args.output_dir / 'action-library.png')
    record = {'scope': 'fictional-public-example', 'generationCalls': 0,
              'description': 'Existing approved sprites; uniform scale, translation and Yozai text layout only.',
              'master': 'assets/style-reference/style-lock-v1/master-approved-v1.png',
              'actionLibrary': LIBRARY.relative_to(ROOT).as_posix(), 'reuse': reuse,
              'outputs': {name: hashlib.sha256((args.output_dir / name).read_bytes()).hexdigest()
                          for name in ('cover.png', 'diary-poster.png', 'action-library.png')}}
    (args.output_dir / 'asset-sources.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(args.output_dir)


if __name__ == '__main__':
    main()
