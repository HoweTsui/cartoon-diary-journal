#!/usr/bin/env python3
"""Export a dated Markdown diary and portable HTML preview with durable attachments.

Input JSON: date, sourceText, body, title, events[{caption}], poster (finished PNG),
photoArchive (manifest path). Paths are relative to the JSON file. This does not
infer semantic fidelity or certify that a supplied poster contains its text.
"""
import argparse
import datetime
import html
import json
import math
import shutil
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from diary_images import normalized, validate_copy


def build(input_path, output):
    data = json.loads(input_path.read_text(encoding='utf-8'))
    date = data['date']
    if datetime.date.fromisoformat(date).isoformat() != date:
        raise ValueError('date must be YYYY-MM-DD')
    for key in ('sourceText', 'body', 'title'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'{key} is required')
    base = input_path.resolve().parent
    poster = (base / data['poster']).resolve()
    with Image.open(poster) as im:
        if im.format != 'PNG':
            raise ValueError('poster must be a finished PNG')
    manifest_path = (base / data['photoArchive']).resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['date'] != date:
        raise ValueError('photo archive date does not match diary date')
    photos = manifest['photos']
    for index, record in enumerate(photos, 1):
        if record.get('order', index) != index:
            raise ValueError('photo order must match input order')
        validate_copy(manifest_path.parent / record['originalPath'],
                      manifest_path.parent / record['compressedPath'])
    output = output.resolve()
    document = output / f'{date}.md'
    start, end = f'<!-- diary:{date}:start -->', f'<!-- diary:{date}:end -->'
    previous = document.read_text(encoding='utf-8') if document.exists() else ''
    if previous.count(start) != previous.count(end) or previous.count(start) > 1:
        raise ValueError('ambiguous diary block; review existing document manually')
    if start in previous and previous.index(start) > previous.index(end):
        raise ValueError('invalid diary block order')
    # A new attachment folder prevents replacing assets used by an existing note.
    attachments = output / 'attachments' / date
    suffix = 2
    while attachments.exists():
        attachments = output / 'attachments' / f'{date}-{suffix}'
        suffix += 1
    attachments.mkdir(parents=True)
    shutil.copy2(poster, attachments / f'{date}-海报-高清.png')
    compressed = normalized(poster)
    compressed.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    poster_name = f'{date}-海报.png'
    compressed.save(attachments / poster_name, 'PNG', optimize=True)
    validate_copy(poster, attachments / poster_name)
    originals = attachments / 'original'
    originals.mkdir()
    names = []
    for index, record in enumerate(photos, 1):
        name = f'{date}-照片-{index:03d}.jpg'
        shutil.copy2(manifest_path.parent / record['compressedPath'], attachments / name)
        # Preserve original basename even when different source folders share names.
        original_dir = originals / f'{index:03d}'
        original_dir.mkdir()
        original = manifest_path.parent / record['originalPath']
        shutil.copy2(original, original_dir / original.name)
        names.append(name)
    gallery_name = f'{date}-照片宫格.jpg'
    if names:
        cell, gap = 600, 16
        gallery = Image.new('RGB', (3 * cell + 4 * gap, math.ceil(len(names) / 3) * (cell + gap) + gap), 'white')
        for index, name in enumerate(names):
            photo = normalized(attachments / name)
            photo.thumbnail((cell, cell), Image.Resampling.LANCZOS)
            x = gap + (index % 3) * (cell + gap) + (cell - photo.width) // 2
            y = gap + (index // 3) * (cell + gap) + (cell - photo.height) // 2
            gallery.paste(photo, (x, y))
        gallery.save(attachments / gallery_name, 'JPEG', quality=95, subsampling=0)
    rel = attachments.relative_to(output).as_posix()
    def url(name):
        return quote(f'{rel}/{name}')
    block = f'{start}\n## 日记内容\n\n{data["body"]}\n\n## 日记海报\n\n![{date} 完整日记海报]({url(poster_name)})\n'
    if names:
        block += f'\n## 原照片\n\n![按提供顺序排列的三列照片宫格]({url(gallery_name)})\n'
    block += f'\n{end}'
    if start in previous:
        result = previous[:previous.index(start)] + block + previous[previous.index(end) + len(end):]
    else:
        result = previous.rstrip() + ('\n\n' if previous else f'# {date}\n\n') + block + '\n'
    if document.exists():
        shutil.copy2(document, attachments / f'{date}-正文备份.md')
    document.write_text(result, encoding='utf-8')
    # Store verbatim source and a human review worksheet beside the durable images.
    (attachments / 'source.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    review = {'status': 'pending-human-review', 'sourceText': data['sourceText'], 'body': data['body'],
              'title': data['title'], 'captions': [e['caption'] for e in data.get('events', [])],
              'checks': ['人物时间事件因果', '否定与情绪强度', '用户立场', '标题备注逐条有原文依据', '完整PNG文字及正文实际预览']}
    (attachments / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    gallery_html = ''.join(f'<img src="{url(name)}" alt="原照片 {i}">' for i, name in enumerate(names, 1))
    font_src = Path(__file__).resolve().parents[1] / 'assets/fonts/yozai'
    for name in ('Yozai-Regular.ttf', 'OFL.txt'):
        shutil.copy2(font_src / name, attachments / name)
    preview = output / f'{date}.html'
    preview.write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{date}</title>
<style>@font-face{{font-family:Yozai;src:url('{url('Yozai-Regular.ttf')}')}}
body{{font-family:Yozai,sans-serif;margin:24px auto;padding:0 20px;max-width:900px;line-height:1.8;color:#111;background:white}}
.body{{white-space:pre-wrap}}.poster{{display:block;max-width:100%;max-height:1000px;margin:auto}}
.gallery{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.gallery img{{width:100%;height:220px;object-fit:contain}}
@media(max-width:600px){{.gallery img{{height:120px}}}}</style><h1>{date}</h1>
<h2>日记内容</h2><div class="body">{html.escape(data['body'])}</div>
<h2>日记海报</h2><img class="poster" src="{url(poster_name)}" alt="完整日记海报">
<h2>原照片</h2><div class="gallery">{gallery_html}</div></html>''', encoding='utf-8')
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.input, args.output_dir))
