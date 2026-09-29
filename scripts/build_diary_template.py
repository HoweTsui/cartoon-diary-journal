#!/usr/bin/env python3
"""Compose isolated scenes onto fixed paper; no generative editing or style scoring."""
from __future__ import annotations

import argparse
import json
import math
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
from build_diary_text_layer import render_png

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'assets/templates/diary-poster-text-layout.json'


def scene_boxes(count):
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 5:
        raise ValueError('scene count must be 1-5')
    zone = json.loads(LAYOUT.read_text())['reservedZones']['illustration']
    step = zone['height'] / count
    gap = min(.012, step / 8)
    return [[zone['x'], zone['y'] + i * step + gap / 2,
             zone['width'], step - gap] for i in range(count)]


def paper():
    canvas = json.loads(LAYOUT.read_text())['canvas']
    image = Image.new('RGBA', (canvas['width'], canvas['height']), 'white')
    draw = ImageDraw.Draw(image)
    for i in range(16):
        y = round(image.height * (.04 + .92 * i / 15))
        draw.line((round(image.width * .05), y, round(image.width * .95), y), fill='#c9edf2', width=2)
    return image


def content_box(image):
    """Measure visible ink without removing any white fill or changing alpha."""
    flat = Image.new('RGBA', image.size, 'white')
    flat.alpha_composite(image.convert('RGBA'))
    diff = ImageChops.difference(flat.convert('RGB'), Image.new('RGB', image.size, 'white'))
    mask = diff.convert('L').point(lambda p: 255 if p > 24 else 0)
    return mask.getbbox()


def validate_scene(scene):
    """Require an isolated alpha cutout, with at least three clear border pixels.

    Never infer transparency from RGB white: white inside a subject is paint.
    A one-level alpha encoding fringe (1/255) is ignored for measurement only;
    source pixels, opaque whites and normal antialiasing remain unchanged.
    This checks isolation, not whether the drawing has an approved style.
    """
    rgba = scene.convert('RGBA')
    alpha = rgba.getchannel('A')
    if alpha.getextrema()[0] != 0:
        raise ValueError('scene is an opaque rectangle or lacks real transparency; '
                         'supply an isolated scene with transparent margins (RGB white is never removed)')
    bounds = alpha.point(lambda p: 255 if p > 1 else 0).getbbox()
    if bounds is None or content_box(rgba) is None:
        raise ValueError('scene is empty: no visible ink')
    x0, y0, x1, y1 = bounds
    if min(x0, y0, rgba.width - x1, rgba.height - y1) < 3:
        raise ValueError('scene touches an edge or has clipped content; require at least '
                         '3 transparent border pixels (alpha <= 1) around all margins')
    if alpha.crop(bounds).getextrema()[0] == 255:
        raise ValueError('scene contains an opaque rectangle; supply a free-form transparent cutout')
    return rgba


def extract_rows(source, count, boundaries=None, *, strict=False):
    """Only split a prearranged sheet across verified empty gutters."""
    scene_boxes(count)  # validate count before division or image work
    if boundaries is None:
        if count != 1:
            raise ValueError('rowBoundaries required: implicit equal slicing may create a split edge; '
                             'supply verified empty-gutter boundaries or use --scenes')
        boundaries = [0, 1]
    with Image.open(source) as original:
        image = original.convert('RGBA')
    if (not isinstance(boundaries, (list, tuple)) or len(boundaries) != count+1 or
        boundaries[0] != 0 or boundaries[-1] != 1 or
        any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) for v in boundaries) or
        any(a >= b for a,b in zip(boundaries, boundaries[1:]))):
        raise ValueError('rowBoundaries must increase from 0 to 1, one boundary per scene gap')
    scenes, rects = [], []
    for i in range(count):
        rect = (0, round(boundaries[i] * image.height), image.width, round(boundaries[i+1] * image.height))
        if rect[3] <= rect[1]:
            raise ValueError('rowBoundaries produce an empty pixel row')
        row = image.crop(rect)
        if strict:
            # Keep the entire source row, including alpha and all white paint.
            scenes.append(validate_scene(row))
            rects.append(list(rect))
            continue
        bounds = content_box(row)
        if bounds is None:
            raise ValueError(f'scene {i + 1} is empty')
        x0, y0, x1, y1 = bounds
        if min(x0, y0, row.width - x1, row.height - y1) < 3:
            raise ValueError(f'scene {i + 1} touches split edge; supply correctly isolated scenes')
        # Trim blank margins only; retain existing alpha and opaque interior white.
        padded = (max(0, x0 - 6), max(0, y0 - 6), min(row.width, x1 + 6), min(row.height, y1 + 6))
        scenes.append(row.crop(padded))
        rects.append([padded[0], rect[1] + padded[1], padded[2], rect[1] + padded[3]])
    return scenes, rects


def compose(scenes, boxes, *, strict=False, fit_visible=False, scale_limit=None):
    """Place scenes using uniform scaling and translation only.

    strict=False retains historical opaque-sheet support and image-center
    anchors for direct callers. New isolated-scene builders and CLI use
    strict=True, with anchors measured from the placed visible ink.
    """
    if (not isinstance(boxes, (list, tuple)) or
            len(scenes) != len(boxes) or not 1 <= len(scenes) <= 5):
        raise ValueError('one scene per box required')
    if scale_limit is not None and (isinstance(scale_limit, bool) or not isinstance(scale_limit, (int,float)) or not math.isfinite(scale_limit) or scale_limit <= 0):
        raise ValueError('scale_limit must be positive and finite')
    canvas = paper()
    zone = json.loads(LAYOUT.read_text())['reservedZones']['illustration']
    placed, centers = [], []
    last_bottom = 0
    for index, (scene, box) in enumerate(zip(scenes, boxes), 1):
        if strict:
            try:
                scene = validate_scene(scene)
            except ValueError as exc:
                raise ValueError(f'scene {index}: {exc}') from exc
        if fit_visible:
            if not strict:
                raise ValueError('visible fitting requires validated transparent scenes')
            # Trim exactly-zero-alpha outer padding only, keeping every painted
            # pixel, opaque white interior and antialiased edge unchanged.
            bounds = scene.getchannel('A').getbbox()
            scene = scene.crop((max(0, bounds[0]-3), max(0, bounds[1]-3),
                                min(scene.width, bounds[2]+3), min(scene.height, bounds[3]+3)))
        if not isinstance(box, (list, tuple)) or len(box) != 4 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in box):
            raise ValueError('invalid scene box')
        x, y, w, h = box
        if (w <= 0 or h <= 0 or x < zone['x'] - 1e-9 or y < zone['y'] - 1e-9 or
            x + w > zone['x'] + zone['width'] + 1e-9 or
            y + h > zone['y'] + zone['height'] + 1e-9 or y < last_bottom - 1e-9):
            raise ValueError('scene box overlaps another box or enters reserved zones')
        last_bottom = y + h
        # Round inward so rounding cannot spill into a neighbouring safe zone.
        bx0, by0 = math.ceil(x * canvas.width - 1e-9), math.ceil(y * canvas.height - 1e-9)
        bx1, by1 = math.floor((x + w) * canvas.width + 1e-9), math.floor((y + h) * canvas.height + 1e-9)
        bw, bh = bx1 - bx0, by1 - by0
        if bw < 1 or bh < 1:
            raise ValueError('scene box must contain at least one pixel per dimension')
        scale = min(bw / scene.width, bh / scene.height)
        if scale_limit is not None:
            scale = min(scale, scale_limit)
        size = (max(1, round(scene.width * scale)), max(1, round(scene.height * scale)))
        resized = scene.convert('RGBA').resize(size, Image.Resampling.LANCZOS)
        left = bx0 + (bw - size[0]) // 2
        top = by0 + (bh - size[1]) // 2
        ink = content_box(resized)
        if ink is None:
            raise ValueError(f'scene {index} is empty or has no visible ink after scaling')
        canvas.alpha_composite(resized, (left, top))
        placed.append([left, top, *size])
        center_y = (ink[1] + ink[3]) / 2 if strict else size[1] / 2
        centers.append((top + center_y) / canvas.height)
    return canvas, centers, placed


def validate_config(config):
    """Accept template config captions or a diary brief's event captions."""
    if not isinstance(config, dict):
        raise ValueError('config/brief must be an object')
    captions = config.get('captions')
    if captions is None:
        events = config.get('events')
        if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
            raise ValueError('provide captions or events with captions')
        captions = [event.get('caption') for event in events]
    if not isinstance(captions, list):
        raise ValueError('captions must be a list')
    count = len(captions)
    scene_boxes(count)
    if 'sceneCount' in config:
        scene_boxes(config['sceneCount'])
        if config['sceneCount'] != count:
            raise ValueError('sceneCount must match the number of captions/events')
    if any(not isinstance(c, str) or not 4 <= len(c) <= 10 for c in captions):
        raise ValueError('captions require 4-10 characters, never truncate')
    if not isinstance(config.get('title'), str) or not 1 <= len(config['title']) <= 12:
        raise ValueError('title requires 1-12 characters')
    diary_header(config)
    return captions


def diary_header(config):
    """Never substitute a historical demo date for a user's diary date."""
    header = config.get('header')
    if isinstance(header, str) and header.strip():
        return header.strip()
    try:
        day = date.fromisoformat(config['date'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('provide an explicit diary header or date in YYYY-MM-DD format') from None
    return day.strftime('%Y.%m.%d') + ' 周' + '一二三四五六日'[day.weekday()]


def build_scenes(scenes, config, output, *, strict=True):
    """Build from ordered image paths or PIL images and a config/diary brief.

    Inputs are never modified. Strict assembly fits the full painted subject,
    trimming only transparent outer padding before uniform resizing.
    Output must be new.
    """
    captions = validate_config(config)
    if len(scenes) != len(captions):
        raise ValueError('one isolated scene per caption/event required')
    loaded = []
    for scene in scenes:
        if isinstance(scene, Image.Image):
            loaded.append(scene.copy())
        else:
            with Image.open(scene) as original:
                loaded.append(original.convert('RGBA'))
    return _build(loaded, config, Path(output), strict=strict,
                  source_rects=[[0, 0, s.width, s.height] for s in loaded])


def build(source, config, output, *, strict=False):
    """Historical sheet entry point; multiple rows require rowBoundaries."""
    captions = validate_config(config)
    scenes, rects = extract_rows(source, len(captions), config.get('rowBoundaries'), strict=strict)
    return _build(scenes, config, Path(output), strict=strict, source_rects=rects)


def _build(scenes, config, output, *, strict, source_rects):
    if output.exists():
        raise ValueError('output exists; choose a new version directory')
    captions = validate_config(config)
    count = len(captions)
    boxes = config.get('sceneBoxes', scene_boxes(count))
    image, centers, placed = compose(scenes, boxes, strict=strict, fit_visible=strict)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        dest = Path(tmp) / 'result'
        dest.mkdir()
        illustration = dest / 'illustration.png'
        image.convert('RGB').save(illustration, optimize=True)
        brief = {'header': diary_header(config), 'title': config['title'],
                 'events': [{'caption': c} for c in captions]}
        render_png(brief, illustration, dest / 'poster.png', centers)
        record = dict(config, sceneCount=count, sceneBoxes=boxes, sceneCenters=centers,
                      placedBounds=placed, sourceRects=source_rects, strictScenes=strict,
                      sizingMode='visible-alpha-fit' if strict else 'legacy-full-canvas', status='draft')
        (dest / 'config.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        dest.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--scenes', type=Path, nargs='+', help='ordered isolated images with transparent margins')
    inputs.add_argument('--source', type=Path, help='scene sheet; multiple rows require verified rowBoundaries in config')
    parser.add_argument('--legacy-sheet', action='store_true',
                        help='allow historical opaque --source sheets; white backgrounds remain opaque')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.legacy_sheet and not args.source:
        parser.error('--legacy-sheet is only valid with --source')
    try:
        config = json.loads(args.config.read_text())
        if args.scenes:
            result = build_scenes(args.scenes, config, args.output_dir)
        else:
            result = build(args.source, config, args.output_dir, strict=not args.legacy_sheet)
        print(result)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
