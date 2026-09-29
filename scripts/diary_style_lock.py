"""Deterministic template selection, never image scoring or user approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'assets/style-reference/style-lock-v1/library.json'
CONTRACT = ROOT / 'references/style-contract.md'
DEFAULT_VERSION = 'style-lock-v2'
EXTENSION_LIBRARY = ROOT / 'assets/style-reference/character-extension-v1/library.json'
HUMAN_COMPONENT_IDS = (
    'appearance-variants-v1',
    'age-proportions-v1',
    'age-variety-example-v2',
    'human-expression-reference-v6',
)


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


def load_extension(path=EXTENSION_LIBRARY):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('invalid character extension library')
    entries = data.get('assets', [])
    if len({entry['id'] for entry in entries}) != len(entries):
        raise ValueError('duplicate character extension id')
    for entry in entries:
        asset(path.parent, entry)
    return data


def human_component_references(character_ids, library_path=LIBRARY, extension_path=EXTENSION_LIBRARY):
    """Return the mandatory, character-scoped visual references for human characters."""
    character_ids = list(character_ids)
    if not character_ids:
        return []
    extension = load_extension(extension_path)
    extension_by_id = {entry['id']: entry for entry in extension['assets']}
    style_library = load_library(library_path)
    expression = style_library.get('expressionReference')
    if not expression or expression.get('status') != 'approved' or expression.get('approvedBy') != 'user':
        raise ValueError('human expression reference must be user-approved')
    entries = []
    for reference_id in HUMAN_COMPONENT_IDS:
        if reference_id == 'human-expression-reference-v6':
            entry = expression
            path = asset(library_path.parent, entry)
        else:
            entry = extension_by_id.get(reference_id)
            if entry is None:
                raise ValueError('required human component reference is missing: ' + reference_id)
            path = asset(extension_path.parent, entry)
        entries.append({'path': path, 'role': 'style', 'origin': 'bundled', 'id': reference_id,
                        'characterIds': character_ids.copy()})
    return entries


def validate_human_component_references(references, character_ids, library_path=LIBRARY,
                                        extension_path=EXTENSION_LIBRARY):
    """Fail closed if a human generation request omits any mandatory visual guide."""
    expected_references = human_component_references(character_ids, library_path, extension_path)
    for expected in expected_references:
        for character_id in character_ids:
            if not any(reference.get('id') == expected['id']
                       and reference.get('path') == expected['path']
                       and reference.get('role') == 'style'
                       and reference.get('origin') == 'bundled'
                       and character_id in reference.get('characterIds', [])
                       for reference in references):
                raise ValueError('missing mandatory human reference for character '
                                 + character_id + ': ' + expected['id'])


def validate_species_references(references, characters, library_path=LIBRARY):
    """Pet guides are mandatory even for revisions and prebuilt requests."""
    library = load_library(library_path)
    for character in characters:
        species = character['species']
        if species == 'human':
            continue
        guides = [r for r in library.get('speciesReferences', []) if r['species'] == species]
        if not guides:
            raise ValueError('missing mandatory species guide: ' + species)
        for guide in guides:
            expected = asset(library_path.parent, guide)
            if not any(r.get('id') == guide['id'] and r.get('path') == expected
                       and r.get('role') == 'style' and r.get('origin') == 'bundled'
                       and character['id'] in r.get('characterIds', []) for r in references):
                raise ValueError('missing mandatory species reference for ' + character['id'])


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
    species = {c['species'] for c in brief.get('characters', [])}
    human_ids = [c['id'] for c in brief.get('characters', []) if c['species'] == 'human']
    if human_ids:
        # These are component references, not example identities. Scope them to
        # humans so single-scene requests omit the pack when no human is visible.
        references[1:1] = human_component_references(human_ids, library_path)
    for reference in library.get('speciesReferences', []):
        if reference['species'] in species:
            references.insert(1, {'path': asset(library_path.parent, reference), 'role': 'style',
                               'origin': 'bundled', 'id': reference['id'],
                               'characterIds': [c['id'] for c in brief['characters'] if c['species'] == reference['species']]})
    result = {'version': library['styleVersion'], 'status': master['status'],
              'referenceDuties': {'master': 'approved drawing language and geometry',
                                  'identity': 'the mapped real character identity and visible anchors',
                                  'human-components': 'mandatory feature-by-feature appearance, age/body and expression guidance; never copy a whole example character',
                                  'template': 'scene organization only', 'photo': 'facts only'}}
    if brief['kind'] == 'diary' and request.get('templateId'):
        used = set(cid for e in brief['events'] for cid in e['characters'])
        people = [c for c in brief['characters'] if c['id'] in used]
        composition = 'pets' if any(c['species'] != 'human' for c in people) else ('group' if len(people) > 1 else 'solo')
        template = select_template(library, len(brief['events']), composition, tags, request.get('templateId'))
        if not preview and template.get('status') != 'approved':
            raise ValueError('selected template is not user-approved')
        if template.get('styleVersion', library['styleVersion']) != library['styleVersion']:
            raise ValueError('historical template style differs from current master; use scene placement without old illustration')
        references.append({'path': asset(library_path.parent, template['illustration']),
                           'role': 'layout', 'origin': 'bundled', 'id': template['id']})
        result.update(templateId=template['id'], sceneCount=template['sceneCount'],
                      sceneBoxes=template['sceneBoxes'])
    # Paths with different semantic roles are not duplicates; preserve role information.
    unique = {(r['path'], r['role']): r for r in references}
    brief['references'] = list(unique.values())
    validate_species_references(brief['references'], brief.get('characters', []), library_path)
    brief['styleLock'] = result
    return brief
