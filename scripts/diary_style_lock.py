"""Deterministic template selection, never image scoring or user approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'assets/style-reference/style-lock-v1/library.json'
CONTRACT = ROOT / 'references/style-contract.md'
DEFAULT_VERSION = 'style-lock-v1'


def asset(root, item):
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('style-lock asset missing or outside library: ' + item['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('style-lock asset checksum mismatch: ' + item['path'])
    return str(path)


def load_library(path=LIBRARY):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or not data.get('styleVersion'):
        raise ValueError('invalid style-lock library')
    ids = [t['id'] for t in data['templates']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate template id')
    return data


def select_template(library, count, composition, tags=(), template_id=None):
    """Exact count, then composition, then authored tags; stable catalog order."""
    candidates = [t for t in library['templates'] if t['sceneCount'] == count]
    if template_id:
        candidates = [t for t in candidates if t['id'] == template_id]
        if not candidates:
            raise ValueError('templateId missing or scene count differs')
        return candidates[0]
    exact = [t for t in candidates if t['composition'] == composition]
    candidates = exact or [t for t in candidates if t.get('generic')]
    if not candidates:
        raise ValueError('no same-count generic template; do not change events')
    for tag in tags:
        matched = [t for t in candidates if tag in t['tags']]
        if matched:
            return matched[0]
    return candidates[0]


def attach(brief, request, preview, library_path=LIBRARY):
    if not isinstance(request, dict) or set(request) - {'version', 'templateId', 'tags'}:
        raise ValueError('styleLock accepts version, templateId, tags only')
    library = load_library(library_path)
    if request.get('version') != library['styleVersion']:
        raise ValueError('styleLock.version must match packaged library')
    tags = request.get('tags', [])
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError('styleLock.tags must be a string list')
    references = [dict(r) for r in brief['references'] if r.get('origin') != 'bundled']
    if any(r['role'] in {'style', 'layout'} for r in references):
        raise ValueError('styleLock owns style/layout references; do not stack old packs')
    master = library['master']
    if master.get('status') != 'approved' or master.get('approvedBy') != 'user':
        raise ValueError('style master must be user-approved, including in preview')
    # Approval of the master is independent from experimental layout templates.
    references.insert(0, {'path': asset(library_path.parent, master), 'role': 'style',
                         'origin': 'bundled', 'id': 'style-lock-master'})
    result = {'version': library['styleVersion'], 'status': master['status'],
              'referenceDuties': {'master': 'drawing language only', 'identity': 'current character',
                                  'template': 'scene organization only', 'photo': 'facts only'}}
    if brief['kind'] == 'diary' and request.get('templateId'):
        used = set(cid for e in brief['events'] for cid in e['characters'])
        people = [c for c in brief['characters'] if c['id'] in used]
        composition = 'pets' if any(c['species'] != 'human' for c in people) else ('group' if len(people) > 1 else 'solo')
        template = select_template(library, len(brief['events']), composition, tags, request.get('templateId'))
        if not preview and template.get('status') != 'approved':
            raise ValueError('selected template is not user-approved')
        references.append({'path': asset(library_path.parent, template['illustration']),
                           'role': 'layout', 'origin': 'bundled', 'id': template['id']})
        result.update(templateId=template['id'], sceneCount=template['sceneCount'],
                      sceneBoxes=template['sceneBoxes'])
    # Paths with different semantic roles are not duplicates; preserve role information.
    unique = {(r['path'], r['role']): r for r in references}
    brief['references'] = list(unique.values())
    brief['styleLock'] = result
    return brief
