#!/usr/bin/env python3
"""Deterministic layout trial using existing, unchanged character sprites."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from build_diary_template import compose, scene_boxes
from build_diary_text_layer import render_png

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'assets/style-reference/style-lock-v1/components-v1.json'
LABELS = ['人物 · 站姿', '猫 · 坐姿', '狗 · 坐姿', '人物 · 五官整体', '猫 · 五官整体', '狗 · 五官整体']
STORY = {
    'header': '2026.09.21 周一', 'title': '陪它们待一会',
    'sourceText': '今天没有安排别的事。先陪猫待了一会，又在狗旁边站了一会。最后，猫和狗都坐在身边，就这样安静地待着。',
    'fictional': True,
    'events': [
        {'caption': '先陪猫待一会', 'components': ['human-standing-right', 'cat-sitting-right']},
        {'caption': '再陪狗歇一会', 'components': ['human-standing-right', 'dog-sitting-right']},
        {'caption': '一起安静待着', 'components': ['human-standing-right', 'cat-sitting-right', 'dog-sitting-right']},
    ],
}


def load_components(manifest_path=MANIFEST):
    spec = json.loads(manifest_path.read_text())
    source = (manifest_path.parent / spec['source']).resolve()
    if not source.is_relative_to(manifest_path.parent.resolve()):
        raise ValueError('source must stay in the component library')
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec['sourceSha256']:
        raise ValueError('master checksum mismatch; no fallback')
    if spec['transforms'] != ['uniform-scale', 'translate']:
        raise ValueError('only uniform scale and translation are supported')
    with Image.open(source) as original:
        if list(original.size) != spec['sourceSize']:
            raise ValueError('master dimensions mismatch')
        sprites = {}
        for item in spec['components']:
            x, y, w, h = item['crop']
            if (item['id'] in sprites or any(type(v) is not int for v in item['crop'])
                    or min(x, y) < 0 or min(w, h) <= 0
                    or x + w > original.width or y + h > original.height):
                raise ValueError('invalid or duplicate component')
            # Unchanged source pixels; no segmentation, recoloring or face editing.
            sprites[item['id']] = original.crop((x, y, x + w, y + h))
    return spec, sprites


def arrange(ids, sprites):
    """One shared scale preserves master character proportions across scenes."""
    scale, gap, height = .66, 24, 340
    widths = [round(sprites[key].width * scale) for key in ids]
    canvas = Image.new('RGBA', (sum(widths) + gap * (len(ids) - 1) + 20, height), (255,255,255,0))
    left, instances = 10, []
    for key, width in zip(ids, widths):
        sprite = sprites[key]
        size = (width, round(sprite.height * scale))
        top = height - size[1] - 5
        if top < 0:
            raise ValueError('component does not fit scene')
        canvas.alpha_composite(sprite.convert('RGBA').resize(size, Image.Resampling.LANCZOS), (left, top))
        instances.append({'componentId': key, 'scale': scale, 'placedBounds': [left, top, *size]})
        left += width + gap
    return canvas, instances


def build(output):
    if output.exists():
        raise ValueError('output exists; choose a new version directory')
    spec, sprites = load_components()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        dest = Path(tmp) / 'result'
        (dest / 'components').mkdir(parents=True)
        component_records, cards = [], []
        for item, label in zip(spec['components'], LABELS):
            key = item['id']
            filename = 'components/' + key + '.png'
            sprites[key].save(dest / filename, optimize=True)
            with Image.open(dest / filename) as saved:
                if saved.mode != sprites[key].mode or saved.tobytes() != sprites[key].tobytes():
                    raise ValueError('component pixels changed during export')
            component_records.append(dict(item, file=filename,
                sha256=hashlib.sha256((dest / filename).read_bytes()).hexdigest(),
                sourcePixelsEqual=True))
            cards.append(f'<article><h3>{label}</h3><img src="{filename}" alt="{label}"><small>{html.escape(key)}</small></article>')
        scenes, instances = [], []
        for event in STORY['events']:
            scene, items = arrange(event['components'], sprites)
            scenes.append(scene)
            instances.append(items)
        illustration, centers, bounds = compose(scenes, scene_boxes(len(scenes)))
        illustration.convert('RGB').save(dest / 'illustration.png', optimize=True)
        render_png(STORY, dest / 'illustration.png', dest / 'poster.png', centers)
        record = dict(schemaVersion=1, status='draft', scope='fictional-demo-only',
            source=spec['source'], sourceSha256=spec['sourceSha256'],
            components=component_records, story=STORY, sceneInstances=instances,
            sceneCenters=centers, placedBounds=bounds, generationCalls=0,
            allowedTransforms=spec['transforms'],
            unsupported=['new-pose','head-body-replacement','left-facing','new-expression'])
        (dest / 'reuse-record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
        shutil.copyfile(ROOT / 'assets/fonts/yozai/Yozai-Regular.ttf', dest / 'Yozai-Regular.ttf')
        shutil.copyfile(ROOT / 'assets/fonts/yozai/OFL.txt', dest / 'OFL.txt')
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>固定五官 · 组件复用试用版</title><style>
@font-face{font-family:Yozai;src:url('Yozai-Regular.ttf')}*{box-sizing:border-box}body{margin:0;background:white;color:#111;font-family:Yozai,sans-serif;line-height:1.7}main{max-width:1100px;margin:auto;padding:40px 24px}h1{font-size:32px}h2{margin-top:50px}p{max-width:850px}a{color:inherit;text-underline-offset:4px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}article{border:1px solid #ddd;border-radius:12px;padding:18px}article img{display:block;width:100%;height:230px;object-fit:contain}small{display:block;overflow-wrap:anywhere;margin-top:12px}.poster{display:block;width:100%;max-width:780px;margin:24px auto;border:1px solid #ddd}summary{cursor:pointer} @media(max-width:650px){main{padding:20px 16px}.grid{grid-template-columns:1fr}h1{font-size:27px}}
</style><main><h1>固定五官，不再每次重画</h1>
<p>这是一版素材复用试验。一个人物、一只猫、一只狗，全部取自你确认的母版。本轮没有调用生图；每次出现都复用同一组件，只移动、等比缩放，不改变五官或朝向。</p>
<p>当前只验证站姿和坐姿。面部视窗供对照，不代表已实现头身拼接。新动作、新表情仍需另外制作。</p>
<h2>01 · 角色与五官组件</h2><div class="grid">''' + ''.join(cards) + '''</div>
<h2>02 · 组合海报</h2><p>以下是虚构的陪伴小记，不进入真实日记。三个场景里的角色使用相同源组件，备注按实际场景位置排版。</p>
<a href="poster.png"><img class="poster" src="poster.png" alt="陪它们待一会，三场景完整日记海报"></a>
<p><a href="poster.png">查看完整 PNG</a> · <a href="reuse-record.json">查看组件复用记录</a></p>
<details><summary>此次验证的边界</summary><p>六个组件导出后与母版对应区域逐像素一致；缩放有正常平滑重采样。脸部没有重新生成，但尚未证明任意新姿势都能直接复用。本版保留原图白底，不做全白透明化；可看到插画附近的白底区域，后续透明素材需要单独制作。本试用版未发布，未覆盖已安装 Skill。</p></details>
</main></html>'''
        (dest / 'index.html').write_text(page)
        dest.rename(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--legacy', action='store_true', help='Explicit historical v1 reproduction only')
    args = parser.parse_args()
    try:
        if args.legacy:
            print(build(args.output_dir))
        else:
            from build_action_trial import build as build_current
            print(build_current(args.output_dir))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, str(exc)+'\n')
