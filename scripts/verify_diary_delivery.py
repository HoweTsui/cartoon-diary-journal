#!/usr/bin/env python3
"""Read-only check of recorded steps, local note embedding and v3 book contents.

Evidence files must be real outputs/call records. Hashes establish consistency,
not that an agent followed every instruction or that a screenshot was reviewed.
Remote note destinations require live connector readback outside this checker.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

from PIL import Image
from diary_images import validate_copy

STEPS = ('references', 'photos', 'identity', 'scenes', 'poster', 'graph-book', 'note')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    errors, pending, checked = [], [], []
    base = manifest_path.parent

    def file(value):
        if not isinstance(value, str) or not value:
            raise ValueError('artifact path required')
        path = (base / value).resolve()
        if not path.is_file():
            raise ValueError(f'missing artifact: {value}')
        return path

    def evidence(item):
        if not isinstance(item, dict):
            raise ValueError('evidence must contain path and sha256')
        path = file(item.get('path'))
        if digest(path) != item.get('sha256'):
            raise ValueError(f'evidence changed or hash absent: {path.name}')
        return path

    def check(label, operation):
        try:
            operation()
            checked.append(label)
        except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
            errors.append(f'{label}: {exc}')

    def steps():
        if data.get('schemaVersion') != 1:
            raise ValueError('schemaVersion must be 1')
        if date.fromisoformat(data['date']).isoformat() != data['date']:
            raise ValueError('date must be YYYY-MM-DD')
        count = data['photoCount']
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('photoCount must be a nonnegative integer')
        records = data['steps']
        if [s['id'] for s in records] != list(STEPS):
            raise ValueError('record all seven existing steps once in order')
        for step in records:
            if step.get('status') == 'not-needed' and step['id'] == 'photos' and count == 0 and step.get('reason'):
                continue
            if step.get('status') != 'done' or not step.get('evidence'):
                raise ValueError(f"step {step['id']} is incomplete or has no evidence")
            for item in step['evidence']:
                evidence(item)

    def poster():
        path = file(data['poster'])
        with Image.open(path) as image:
            if image.format != 'PNG' or image.width * 4 != image.height * 3:
                raise ValueError('finished poster must be a 3:4 PNG')
            image.verify()

    def reader():
        path = file(data['readerManifest'])
        book = json.loads(path.read_text(encoding='utf-8'))
        matches = [e for e in book['entries'] if e.get('date') == data['date']]
        if len(matches) != 1 or matches[0].get('isBlank'):
            raise ValueError('book must contain exactly one nonblank entry for the diary date')
        media = (path.parent / unquote(matches[0]['posterSrc'])).resolve()
        try:
            media.relative_to(path.parent)
        except ValueError:
            raise ValueError('book poster escapes its data directory') from None
        if digest(media) != digest(file(data['poster'])):
            raise ValueError('book still contains a different or stale poster')

    def note():
        target = data['note']
        if not target.get('tool'):
            raise ValueError('name the actual user note tool')
        if target.get('kind') == 'remote':
            if not re.match(r'^https://', target.get('url', '')):
                raise ValueError('remote note URL required')
            evidence(target['readback'])
            pending.append('remote-note: confirm live tool readback, image blocks and persistent attachments; local files cannot certify remote publication')
            return
        if target.get('kind') != 'local-markdown':
            raise ValueError('supported note kinds: local-markdown, remote')
        document = file(target['document'])
        if document.stem != data['date']:
            raise ValueError('note filename must match diary date')
        text = document.read_text(encoding='utf-8')
        embedded = re.findall(r'!\[[^\]]*\]\(([^)]+)\)|!\[\[([^\]]+)\]\]', text)
        images = [(document.parent / unquote(a or b.split('|')[0])).resolve() for a, b in embedded]
        note_poster = file(target['poster'])
        if note_poster not in images:
            raise ValueError('note must embed the finished poster, not only link to it')
        validate_copy(file(data['poster']), note_poster)
        photos = target.get('photos', [])
        if len(photos) != data['photoCount']:
            raise ValueError('note photo count differs from input count')
        if photos:
            archive_path = file(data['photoArchive'])
            archive = json.loads(archive_path.read_text(encoding='utf-8'))
            if archive['date'] != data['date'] or len(archive['photos']) != len(photos):
                raise ValueError('photo archive date/count mismatch')
            for i, (record, photo) in enumerate(zip(archive['photos'], photos), 1):
                if record.get('order', i) != i:
                    raise ValueError('archive photo order mismatch')
                original = archive_path.parent / record['originalPath']
                compressed = archive_path.parent / record['compressedPath']
                validate_copy(original, compressed)
                if digest(file(photo)) != digest(compressed):
                    raise ValueError('note photos missing, changed or out of input order')
            gallery = file(target['gallery'])
            if gallery not in images or images.index(gallery) <= images.index(note_poster):
                raise ValueError('embed the three-column gallery after the poster')
            with Image.open(gallery) as image:
                image.verify()

    def previews():
        for name in ('note', 'reader', 'poster'):
            item = data.get('previews', {}).get(name)
            if not item:
                pending.append(f'{name}: actual preview evidence missing')
            else:
                evidence(item)
        if not data.get('contentReview'):
            pending.append('source meaning and visual style still require inspection')
        else:
            evidence(data['contentReview'])

    for name, fn in (('step-records', steps), ('poster', poster), ('reader', reader), ('note', note), ('preview-records', previews)):
        check(name, fn)
    return {'status': 'blocked' if errors else ('pending' if pending else 'evidence-complete'),
            'checked': checked, 'errors': errors, 'pending': pending,
            'scope': 'Recorded evidence and artifact consistency only; not independent proof of model behavior, semantic fidelity, approval or remote writes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.manifest)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'blocked', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'evidence-complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
