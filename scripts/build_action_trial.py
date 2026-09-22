#!/usr/bin/env python3
"""Package manually reviewed action sheets and compose a draft diary preview."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from build_diary_template import content_box, compose, scene_boxes
from build_diary_text_layer import render_png
from diary_style_lock import asset

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'assets/style-reference/style-lock-v1'
LIBRARY = BASE / 'action-library-v2.json'
JOBS = [
    ('human', [('human-walk-right', '人物 · 走路', 'walking'), ('human-read-right', '人物 · 坐着看书', 'reading')]),
    ('cat', [('cat-walk-right', '猫 · 走路', 'walking'), ('cat-lie-right', '猫 · 趴卧', 'lying-awake')]),
    ('dog', [('dog-walk-right', '狗 · 走路', 'walking'), ('dog-sniff-right', '狗 · 低头闻闻', 'sniffing')]),
]


def ref(path):
    return {'path': path.relative_to(BASE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_action(action_id, preview=False, library_path=LIBRARY):
    catalog = json.loads(library_path.read_text())
    if not preview and (catalog.get('status') != 'approved' or catalog.get('approvedBy') != 'user'):
        raise ValueError('action library is draft; user approval required for production')
    entries = [item for item in catalog['actions'] if item['id'] == action_id]
    if len(entries) != 1:
        raise ValueError('action missing or duplicated; do not change the event to fit another action')
    entry = entries[0]
    if not preview and (entry['status'] != 'approved' or entry.get('approvedBy') != 'user'):
        raise ValueError('action is draft; user approval required for production')
    for required in catalog['requiredReferences']:
        asset(library_path.parent, required)
    filename = asset(library_path.parent, entry['image'])
    with Image.open(filename) as image:
        return image.convert('RGBA'), entry


def package():
    if LIBRARY.exists():
        raise ValueError('library exists; do not overwrite reviewed action versions')
    approved = json.loads((BASE / 'components-v1.json').read_text())
    if approved.get('status') != 'approved' or approved.get('approvedBy') != 'user':
        raise ValueError('base components need user approval before expansion')
    master = BASE / approved['source']
    if ref(master)['sha256'] != approved['sourceSha256']:
        raise ValueError('approved master checksum mismatch')
    extracted, entries = {}, []
    for species, actions in JOBS:
        source = BASE / f'actions-v1/sheets/{"cat-v2" if species == "cat" else species}.png'
        with Image.open(source) as original:
            sheet = original.convert('RGBA')
        for side, (key, label, pose) in enumerate(actions):
            left, right = round(sheet.width * side / 2), round(sheet.width * (side + 1) / 2)
            region = sheet.crop((left, 0, right, sheet.height))
            bounds = content_box(region)
            if bounds is None:
                raise ValueError('empty action sprite')
            x0, y0, x1, y1 = bounds
            if min(x0, y0, region.width - x1, region.height - y1) < 4:
                raise ValueError('sprite crosses an edge or central gutter')
            rect = [max(0, x0-10), max(0, y0-10), min(region.width, x1+10), min(region.height, y1+10)]
            sprite = region.crop(rect)
            alpha = sprite.getchannel('A')
            if alpha.getextrema()[0] != 0:
                raise ValueError('requested transparency absent; do not remove white interiors')
            extracted[key] = sprite
            entries.append({'id':key, 'label':label, 'species':species, 'pose':pose,
                'facing':'reference-side-right', 'status':'draft', 'approvedBy':None,
                'identityScope':'fictional-demo-only', 'source':ref(source),
                'sourceRect':[left+rect[0],rect[1],left+rect[2],rect[3]],
                'background':'generated-alpha-preserved', 'facePreservation':'reference-guided-not-pixel-identical'})
    destination = BASE / 'actions-v1/components-v2'
    if destination.exists():
        raise ValueError('components already exist; use a new version')
    destination.mkdir()
    for entry in entries:
        filename = destination / (entry['id']+'.png')
        extracted[entry['id']].save(filename, optimize=True)
        entry['image'] = ref(filename)
    inputs = sorted((BASE/'actions-v1/reference-inputs').glob('*.png'))
    if len(inputs) != 6:
        raise ValueError('all six approved identity inputs must be packaged')
    catalog = {'schemaVersion':1, 'id':'actions-v2', 'status':'draft',
        'requiredReferences':[ref(master)] + [ref(p) for p in inputs],
        'allowedTransforms':['uniform-scale','translate'],
        'actions':entries}
    LIBRARY.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n')


def arrange(items):
    sprites, instances = [], []
    for key, target_height in items:
        sprite, entry = load_action(key, preview=True)
        scale = target_height / sprite.height
        size = (round(sprite.width * scale), target_height)
        sprites.append(sprite.resize(size, Image.Resampling.LANCZOS))
        instances.append({'id':key, 'image':entry['image'], 'scale':scale})
    result = Image.new('RGBA', (sum(s.width for s in sprites)+40*(len(sprites)-1)+20, 350), (255,255,255,0))
    x = 10
    for sprite, record in zip(sprites, instances):
        y = 340-sprite.height
        result.alpha_composite(sprite, (x,y))
        record['bounds'] = [x,y,*sprite.size]
        x += sprite.width+40
    bounds = content_box(result)
    if bounds is None:
        raise ValueError('empty composed scene')
    x0,y0,x1,y1 = bounds
    crop = (max(0,x0-8),max(0,y0-8),min(result.width,x1+8),min(result.height,y1+8))
    for record in instances:
        record['bounds'][0] -= crop[0]
        record['bounds'][1] -= crop[1]
    return result.crop(crop), instances


def build(output):
    if output.exists():
        raise ValueError('preview exists; choose a new output directory')
    catalog = json.loads(LIBRARY.read_text())
    catalog_approved = catalog.get('status') == 'approved' and catalog.get('approvedBy') == 'user'
    fully_approved = catalog_approved and all(
        item.get('status') == 'approved' and item.get('approvedBy') == 'user'
        for item in catalog['actions'])
    library_label = '已确认动作库' if fully_approved else '待确认动作预览'
    approval_note = ('以下六个动作均已确认；只在其批准范围内复用。' if fully_approved else
                     '本页包含待确认动作；请按卡片状态查看，不得用于正式成品。')
    rows = [[('human-walk-right',320),('dog-walk-right',190)],
            [('cat-walk-right',185),('dog-sniff-right',175)],
            [('human-read-right',310),('cat-lie-right',155)]]
    scenes, instances = zip(*(arrange(row) for row in rows))
    story = {'header':'2026.09.21 周一','title':'走走再歇歇','fictional':True,
        'sourceText':'我和狗一起慢慢走了一段。后来狗停下闻闻，猫在旁边走了几步。回去后我坐下看书，猫趴在身边休息。',
        'events':[{'caption':'出门慢慢走'},{'caption':'停下闻一闻'},{'caption':'坐下翻几页'}]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        dest = Path(tmp)/'result'
        (dest/'components').mkdir(parents=True)
        (dest/'references').mkdir()
        cards=[]
        for entry in catalog['actions']:
            load_action(entry['id'],preview=True)
            filename=entry['id']+'.png'
            shutil.copyfile(BASE/entry['image']['path'],dest/'components'/filename)
            approved = catalog_approved and entry.get('status') == 'approved' and entry.get('approvedBy') == 'user'
            action_state = '已确认 · 可正式复用' if approved else '新增动作 · 待确认'
            cards.append(f'<article><h3>{html.escape(entry["label"])}</h3><img src="components/{filename}" alt="{html.escape(entry["label"])}"><p>{action_state}</p></article>')
        reference_cards=[]
        for species in ['human','cat','dog']:
            filename=species+'-face-neutral.png'
            shutil.copyfile(BASE/'actions-v1/reference-inputs'/filename,dest/'references'/filename)
            reference_cards.append(f'<article><img src="references/{filename}" alt="{species} 已确认五官"><p>已确认的五官参考</p></article>')
        boxes = scene_boxes(3)
        for scene, box in zip(scenes, boxes):
            center = box[1]+box[3]/2
            box[3] = min(box[3],scene.height/1600)
            box[1] = center-box[3]/2
        image, centers, placed = compose(scenes,boxes)
        image.convert('RGB').save(dest/'illustration.png',optimize=True)
        render_png(story,dest/'illustration.png',dest/'poster.png',centers)
        record={'status':'approved' if fully_approved else 'draft',
            'approvedBy':catalog.get('approvedBy') if fully_approved else None,
            'approvedOn':catalog.get('approvedOn') if fully_approved else None,
            'story':story,'sceneInstances':instances,'sceneCenters':centers,'placedBounds':placed,
            'compositionGenerationCalls':0, 'note':'Action sprites were generated once, then reused unchanged except uniform scale and translation.'}
        (dest/'reuse-record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        for filename in ['Yozai-Regular.ttf','OFL.txt']:
            shutil.copyfile(ROOT/'assets/fonts/yozai'/filename,dest/filename)
        page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>六个动作 · '''+library_label+'''</title><style>
@font-face{font-family:Yozai;src:url('Yozai-Regular.ttf')}*{box-sizing:border-box}body{margin:0;background:#fff;color:#111;font-family:Yozai,sans-serif;line-height:1.7}main{max-width:1160px;margin:auto;padding:36px 24px}h1{font-size:32px}h2{margin-top:44px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.actions{grid-template-columns:repeat(2,1fr)}article{border:1px solid #ddd;border-radius:12px;padding:16px}article img{width:100%;height:220px;object-fit:contain}.actions img{height:330px}article p{margin-bottom:0;font-size:15px}.poster{display:block;width:100%;max-width:780px;margin:20px auto;border:1px solid #ddd}a{color:inherit;text-underline-offset:4px}@media(max-width:650px){main{padding:20px 16px}.grid{grid-template-columns:1fr}.actions img{height:290px}h1{font-size:27px}}
</style><main><h1>六个动作，同一套角色</h1><p>'''+approval_note+'''旧组件不替换；复用时只允许等比缩放与移动。</p>
<h2>已确认的五官参考</h2><div class="grid">'''+''.join(reference_cards)+'''</div>
<h2>首批动作</h2><p>人物走路、坐着看书；猫走路、趴卧；狗走路、低头闻闻。均沿用侧向画法。图形外部保留生成的透明通道，身体内部保留白色。</p><div class="grid actions">'''+''.join(cards)+'''</div>
<h2>放进日记会怎样？</h2><p>虚构示例，不进入真实日记。海报直接调用上面的动作素材，没有再次生成人脸。</p><a href="poster.png"><img class="poster" src="poster.png" alt="走走再歇歇，完整三场景日记海报"></a><p><a href="poster.png">查看完整 PNG</a> · <a href="reuse-record.json">查看复用记录</a></p>
<details><summary>本次实现与边界</summary><p>新增动作使用内置 ImageGen，并实际附上母版、已确认全身与脸部参考。'''+approval_note+'''复用选定动作时只等比缩放、移动，没有自动评分或循环重生。未提供左向版本或任意头身拼接。人物和宠物都是风格示例，不替代用户角色卡。</p></details></main></html>'''
        (dest/'index.html').write_text(page)
        dest.rename(output)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',action='store_true')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.package: package()
        print(build(args.output_dir))
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,str(exc)+'\n')
