#!/usr/bin/env python3
"""Build prompts from authored schema-v2 inputs; never summarize or approve."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import unquote
SKILL_ROOT = Path(__file__).resolve().parents[1]
GRAPH_DATA_PATTERN = re.compile(r'<script\s+id="graph-data"\s+type="application/json">\s*(.*?)\s*</script>', re.DOTALL)
PLACEHOLDER_MARKERS = ("actual-person-", "实际人物", "实际关系", "占位")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
def require_text(data: dict, key: str, maximum: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{key} must be at most {maximum} characters")
    return value


def optional_text(value: object, label: str, maximum: int, default: str = "") -> str:
    if value is None or value == "":
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string when provided")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    return result


def valid_relative_asset_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative local asset path")
    result = value.strip()
    normalized = result.replace("\\", "/")
    decoded = unquote(normalized)
    if (
        "\x00" in decoded
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", decoded)
        or decoded.startswith("/")
        or any(part == ".." for part in decoded.split("/"))
    ):
        raise ValueError(f"{label} must be a relative local asset path")
    return result


def load_brief(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"brief not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("brief root must be a JSON object")
    return data


def load_character_graph(path: Path) -> tuple[dict[str, dict], list[dict]]:
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"character graph not found: {path}") from exc
    match = GRAPH_DATA_PATTERN.search(html)
    if not match:
        raise ValueError("character graph has no graph-data block")
    try:
        graph_data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid graph-data JSON at line {exc.lineno}") from exc
    if graph_data.get("status") != "actual":
        raise ValueError(
            "当前人物图谱仍是占位数据；先用本次任务的实际人物和关系完整重建图谱"
        )
    nodes = graph_data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("character graph must contain at least one actual person")
    atlas = graph_data.get("atlas")
    if not isinstance(atlas, dict):
        raise ValueError("character graph must contain atlas metadata")
    atlas_src = valid_relative_asset_path(atlas.get("src"), "character graph atlas.src")
    if not (path.parent / atlas_src).is_file():
        raise ValueError(f"character graph atlas is missing: {path.parent / atlas_src}")
    cols = atlas.get("cols")
    rows = atlas.get("rows")
    if not isinstance(cols, int) or cols < 1 or not isinstance(rows, int) or rows < 1:
        raise ValueError("character graph atlas.cols and atlas.rows must be positive integers")

    characters: dict[str, dict] = {}
    names: set[str] = set()
    avatar_sources: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"graph node {index + 1} must be an object")
        character_id = require_text(node, "id", 64)
        name = require_text(node, "name", 20)
        node_text = json.dumps(node, ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            if marker in node_text:
                raise ValueError(f"graph character {name} still contains placeholder text: {marker}")
        anchors = node.get("anchors")
        if not isinstance(anchors, list) or len(anchors) < 4 or not all(
            isinstance(item, str) and item.strip() for item in anchors
        ):
            raise ValueError(f"graph character {name} needs at least four anchors")
        if character_id in characters:
            raise ValueError(f"duplicate graph character ID: {character_id}")
        if name in names:
            raise ValueError(f"duplicate graph character name: {name}")
        col = node.get("col")
        row = node.get("row")
        if not isinstance(col, int) or not 0 <= col < cols:
            raise ValueError(f"graph character {name} has an invalid atlas column")
        if not isinstance(row, int) or not 0 <= row < rows:
            raise ValueError(f"graph character {name} has an invalid atlas row")
        if "avatarSrc" in node:
            avatar_sources.append(
                valid_relative_asset_path(node["avatarSrc"], f"graph character {name}.avatarSrc")
            )
        characters[character_id] = node
        names.add(name)

    if avatar_sources and len(avatar_sources) != len(characters):
        raise ValueError(
            "graph avatarSrc must be provided for every character when independent avatars are used"
        )
    if len(set(avatar_sources)) != len(avatar_sources):
        raise ValueError("graph avatarSrc paths must be unique per character")
    for avatar_src in avatar_sources:
        avatar_path = path.parent / avatar_src
        if not avatar_path.is_file():
            raise ValueError(f"graph independent avatar is missing: {avatar_path}")

    edges = graph_data.get("edges")
    if not isinstance(edges, list):
        raise ValueError("character graph edges must be a list")
    normalized_edges: list[dict] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"character relationship {index + 1} must be an object")
        source, target, label = edge.get("source"), edge.get("target"), edge.get("label")
        if source not in characters or target not in characters or source == target:
            raise ValueError(f"character relationship {index + 1} has invalid endpoints")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"character relationship {index + 1} needs a label")
        for marker in PLACEHOLDER_MARKERS:
            if marker in label:
                raise ValueError(f"character relationship {index + 1} still contains placeholder text: {marker}")
        normalized_edges.append(edge)
    return characters, normalized_edges



EYES = {"neutral_dot", "closed_arc", "half_lid", "wide_round", "crossed"}
ROLES = {"identity-source", "identity-draft", "identity-approved", "style", "layout", "scene"}
REFERENCE_MANIFEST = SKILL_ROOT / "assets" / "style-reference" / "reference-manifest.json"


def image_signature(path: Path, label: str) -> None:
    with path.open("rb") as handle:
        signature = handle.read(16)
    if not (
        signature.startswith(b"\x89PNG\r\n\x1a\n")
        or signature.startswith(b"\xff\xd8\xff")
        or signature.startswith((b"GIF87a", b"GIF89a"))
        or (signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
    ):
        raise ValueError("reference must be PNG/JPEG/GIF/WebP: " + label)


def bundled_references(kind: str) -> list[dict]:
    """Return, and integrity-check, the immutable visual reference pack."""
    try:
        data = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"bundled reference manifest is unreadable: {exc}") from exc
    if data.get("schemaVersion") != 1 or not isinstance(data.get("references"), list):
        raise ValueError("bundled reference manifest has an invalid schema")
    result = []
    for item in data["references"]:
        if not isinstance(item, dict) or kind not in item.get("appliesTo", []):
            continue
        relative = valid_relative_asset_path(item.get("path"), "bundled reference.path")
        full = (SKILL_ROOT / relative).resolve()
        if not full.is_file() or not is_within(full, SKILL_ROOT.resolve()):
            raise ValueError("bundled reference is missing: " + relative)
        expected = item.get("sha256")
        actual = hashlib.sha256(full.read_bytes()).hexdigest()
        if not isinstance(expected, str) or actual != expected:
            raise ValueError("bundled reference checksum does not match: " + relative)
        image_signature(full, relative)
        role = item.get("role")
        if role not in {"style", "layout"}:
            raise ValueError("bundled reference has an invalid role: " + relative)
        result.append({"path": str(full), "role": role, "id": item.get("id"), "origin": "bundled"})
    if not result or (kind == "diary" and "layout" not in {item["role"] for item in result}):
        raise ValueError("bundled reference manifest lacks required references for " + kind)
    return result


def validate_photo_archive(data: dict, base: Path, user_photo_paths: set[str]) -> None:
    if not user_photo_paths:
        return
    archive = data.get("photoArchive")
    if not isinstance(archive, dict):
        raise ValueError("user-photo references require photoArchive.manifest")
    manifest_path = valid_relative_asset_path(archive.get("manifest"), "photoArchive.manifest")
    full = (base / manifest_path).resolve()
    if not full.is_file() or not is_within(full, base.resolve()):
        raise ValueError("photo archive manifest is missing: " + manifest_path)
    try:
        manifest = json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid photo archive manifest at line {exc.lineno}") from exc
    photos = manifest.get("photos") if isinstance(manifest, dict) else None
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1 or not isinstance(photos, list):
        raise ValueError("photo archive manifest has an invalid schema")
    manifest_parent = Path(manifest_path).parent
    compressed = {
        (manifest_parent / item.get("compressedPath")).as_posix()
        for item in photos
        if isinstance(item, dict) and isinstance(item.get("compressedPath"), str)
    }
    missing = sorted(user_photo_paths - compressed)
    if missing:
        raise ValueError("user-photo reference is not the archived compressed copy: " + ", ".join(missing))
def geometry(data):
    canonical = json.loads((SKILL_ROOT / "references/geometry.json").read_text(encoding="utf-8"))
    value = json.loads(json.dumps(canonical))
    supplied = data.get("geometry", {})
    if not isinstance(supplied, dict) or set(supplied) - set(value):
        raise ValueError("unknown geometry fields")
    value.update(supplied)
    def check(actual, target, label):
        if isinstance(target, dict):
            if not isinstance(actual, dict) or set(actual) != set(target):
                raise ValueError(label + " requires all canonical dimensions")
            for k, v in target.items():
                check(actual[k], v, label + "." + k)
        elif isinstance(actual, bool) or not isinstance(actual, (float, int)) or not math.isfinite(actual) or (actual != 0 if target == 0 else abs(actual / target - 1) > .100001):
            raise ValueError(label + " must be within 10% of canonical target")
    check(value, canonical, "geometry")
    if not math.isclose(value["outerWidth"], 2 * value["stroke"] + value["innerGap"], abs_tol=1e-8):
        raise ValueError("outerWidth must equal 2*stroke+innerGap")
    widths = [value["armWidth"], value["legWidth"]]
    if max(widths) / min(widths) > 1.100001 or any(w <= 2 * value["stroke"] for w in widths):
        raise ValueError("arm/leg widths must match within 10% and retain white channels")
    return value


def validate_reference_mapping(references, events, character_ids):
    """Check authored reference scope; never infer it from image content."""
    ref_ids, scene_ids, by_asset = set(), set(), {}
    for ref in references:
        rid = ref.get('id')
        if 'id' in ref:
            if not isinstance(rid, str) or not rid.strip() or rid != rid.strip() or len(rid) > 64:
                raise ValueError('reference.id must be a non-empty ID of at most 64 characters without outer whitespace')
            if rid in ref_ids:
                raise ValueError('duplicate reference.id: ' + rid)
            ref_ids.add(rid)
        if ref['role'] == 'scene':
            if rid is None:
                raise ValueError('scene reference requires id and explicit event.referenceIds mapping')
            scene_ids.add(rid)
        if 'characterIds' in ref:
            cids = ref['characterIds']
            scoped_style = ref.get('origin') == 'bundled' and ref['role'] == 'style'
            if ((not ref['role'].startswith('identity-') and not scoped_style) or not isinstance(cids, list) or not cids or
                    any(not isinstance(cid, str) or cid not in character_ids for cid in cids) or
                    len(set(cids)) != len(cids)):
                raise ValueError('reference.characterIds must be a non-empty unique list of registered IDs on identity references only')
        # attach() deduplicates by path/role. Reject conflicting metadata before
        # that can discard an event ID or silently change an identity's scope.
        key = (ref['path'], ref['role'])
        if key in by_asset and by_asset[key] != ref:
            raise ValueError('duplicate reference path/role has conflicting mapping; reuse one reference across events/characters')
        by_asset[key] = ref
    used = set()
    for index, event in enumerate(events, 1):
        mapped = event.get('referenceIds', [])
        if (not isinstance(mapped, list) or any(not isinstance(rid, str) for rid in mapped) or
                len(set(mapped)) != len(mapped)):
            raise ValueError(f'event {index}.referenceIds must be a unique list of scene reference IDs')
        if set(mapped) - scene_ids:
            raise ValueError(f'event {index}.referenceIds must name declared role=scene references: ' +
                             ', '.join(sorted(set(mapped) - scene_ids)))
        used.update(mapped)
    if scene_ids - used:
        raise ValueError('scene references require explicit event.referenceIds mapping; unmapped: ' +
                         ', '.join(sorted(scene_ids - used)))


def validate_brief(data, base, preview=False, graph=None):
    if any(key in data for key in ("images", "sourceImages", "text")):
        raise ValueError("migrate legacy text/images/sourceImages to sourceText and references")
    if data.get("schemaVersion") != 2:
        raise ValueError("schemaVersion must be 2; agent must author title, captions and events")
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in {"onboarding", "expression", "diary"}:
        raise ValueError("kind must be onboarding, expression or diary")
    identity = data.get("identity")
    if not isinstance(identity, dict) or not isinstance(identity.get("status"), str) or identity["status"] not in {"draft", "confirmed"}:
        raise ValueError("identity.status must be draft or confirmed")
    version = require_text(identity, "version", 64)
    confirmed = identity["status"] == "confirmed"
    if confirmed and (identity.get("approvedVersion") != version or identity.get("approvedBy") != "user"):
        raise ValueError("confirmed identity requires user approvedBy and matching approvedVersion")
    if not preview and not confirmed:
        raise ValueError("unconfirmed identity blocked in production; use --preview for requested drafts")
    if kind == "onboarding" and not preview:
        raise ValueError("onboarding requires --preview")
    graph_characters = load_character_graph(graph)[0] if graph else {}
    chars = data.get("characters")
    if chars is None and graph:
        chars = list(graph_characters.values())
    if not isinstance(chars, list) or not chars:
        raise ValueError("characters must be a non-empty list")
    ids = set()
    for c in chars:
        if not isinstance(c, dict):
            raise ValueError("character must be an object")
        cid = require_text(c, "id", 64)
        require_text(c, "name", 20)
        if cid in ids or not isinstance(c.get("species"), str) or c["species"] not in {"human", "cat", "dog"}:
            raise ValueError("unique character id and explicit human/cat/dog species required")
        ids.add(cid)
        age = c.get('ageGroup', 'unknown')
        if c.get('bodyType', 'regular') not in {'slender', 'regular', 'full'}:
            raise ValueError('bodyType must be slender/regular/full')
        if age not in {'child', 'adolescent', 'adult', 'unknown'}:
            raise ValueError('ageGroup must be child/adolescent/adult/unknown, based on user information')
        stage = c.get('ageStage')
        if stage is not None and (age != 'adult' or stage not in {'young-adult', 'middle-aged', 'older-adult'}):
            raise ValueError('ageStage requires adult ageGroup and young-adult/middle-aged/older-adult')
        if c.get('chestContour', 'neutral') not in {'neutral', 'subtle-clothed'}:
            raise ValueError('chestContour must be neutral or subtle-clothed')
        if c.get('chestContour') == 'subtle-clothed' and age != 'adult':
            raise ValueError('subtle-clothed chest contour requires user-stated adult ageGroup')
        anchors = c.get("anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 12 or any(not isinstance(a, str) or not a.strip() or len(a) > 160 for a in anchors):
            raise ValueError("character anchors require 2-12 short observable identity features")
        if not preview and graph_characters.get(cid, {}).get("profile", {}).get("approval") == "draft":
            raise ValueError(f"character {cid} is still a draft in the character graph")
    if not isinstance(data.get("protagonistId"), str) or data["protagonistId"] not in ids:
        raise ValueError("protagonistId must identify an explicit character")
    refs = data.get("references")
    if not isinstance(refs, list) or not refs:
        raise ValueError("references must be a non-empty list")
    resolved, roles, user_photo_paths = [], set(), set()
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("role"), str) or ref["role"] not in ROLES:
            raise ValueError("invalid reference role")
        path = valid_relative_asset_path(ref.get("path"), "reference.path")
        full = (base / path).resolve()
        try:
            full.relative_to(base.resolve())
        except ValueError:
            raise ValueError("reference escapes brief directory")
        if not full.is_file():
            raise ValueError("reference missing: " + path)
        image_signature(full, path)
        origin = ref.get("origin", "task-asset")
        if origin not in {"task-asset", "user-photo"}:
            raise ValueError("reference.origin must be task-asset or user-photo")
        if origin == "user-photo":
            user_photo_paths.add(path)
        roles.add(ref["role"])
        item = {"path": str(full), "role": ref["role"], "origin": origin}
        for field in ('id', 'characterIds'):
            if field in ref:
                item[field] = list(ref[field]) if isinstance(ref[field], list) else ref[field]
        resolved.append(item)
    validate_photo_archive(data, base, user_photo_paths)
    needed = {"identity-source"} if kind == "onboarding" else ({"identity-approved"} if not preview else {"identity-draft", "identity-approved"})
    if not roles.intersection(needed):
        raise ValueError("missing identity reference role: " + "/".join(sorted(needed)))
    from diary_style_lock import DEFAULT_VERSION, attach
    style_request = data.get('styleLock', {'version': DEFAULT_VERSION})
    if not preview and identity.get('styleVersion') != DEFAULT_VERSION:
        raise ValueError('identity.styleVersion must match the current master; calibrate the character card in preview first')
    result = {"kind": kind, "role": "draft-preview" if preview else "production", "identity": identity, "protagonistId": data["protagonistId"], "characters": chars, "references": resolved, "geometry": geometry(data)}
    if kind == "onboarding":
        validate_reference_mapping(resolved, [], ids)
        attach(result, style_request, preview)
        return result
    if not isinstance(data.get("sourceText"), str) or not data["sourceText"].strip():
        raise ValueError("full sourceText required; do not truncate source")
    result["sourceText"] = data["sourceText"]
    result["title"] = require_text(data, "title", 12)
    result["summary"] = optional_text(data.get("summary"), "summary", 20)
    if kind == "diary":
        date = dt.date.fromisoformat(require_text(data, "date", 10))
        result["header"] = date.strftime("%Y.%m.%d") + " " + ("周一", "周二", "周三", "周四", "周五", "周六", "周日")[date.weekday()]
    events = data.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 5:
        raise ValueError("events must contain 1-5 explicitly selected scenes")
    selected = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        if any(key in event for key in ("images", "sourceImages", "source_images")):
            raise ValueError("declare all event images in references with role scene")
        e = {k: require_text(event, k, n) for k, n in (("scene", 180), ("caption", 10), ("emotion", 40))}
        if len(e["caption"]) < 4:
            raise ValueError("caption must contain 4-10 characters")
        e["bubble"] = optional_text(event.get("bubble"), "bubble", 6)
        cids = event.get("characters")
        if not isinstance(cids, list) or not cids or any(not isinstance(c, str) or c not in ids for c in cids) or len(set(cids)) != len(cids):
            raise ValueError("event characters must be unique registered IDs")
        e["characters"] = cids
        e['referenceIds'] = event.get('referenceIds', [])
        for field, allowed in (("eye_state", EYES), ("intensity", {"mild", "medium", "strong"}), ("eyebrows", {"none", "raised", "furrowed"})):
            if not isinstance(event.get(field), str) or event[field] not in allowed:
                raise ValueError(field + " must be explicitly authored from allowed values")
            e[field] = event[field]
        for field in ("must_keep", "flexible"):
            items = event.get(field, [])
            if not isinstance(items, list) or len(items) > 10 or any(not isinstance(x, str) or not x.strip() or len(x) > 160 for x in items):
                raise ValueError(field + " must be a list of short facts")
            e[field] = items
        overrides = event.get("expressions", {})
        if not isinstance(overrides, dict) or set(overrides) - set(cids):
            raise ValueError("expressions must map visible character IDs to expression objects")
        e["expressions"] = {}
        for cid, expression in overrides.items():
            if not isinstance(expression, dict):
                raise ValueError("per-character expression must be an object")
            override = {"emotion": require_text(expression, "emotion", 40)}
            for field, allowed in (("eye_state", EYES), ("intensity", {"mild", "medium", "strong"}), ("eyebrows", {"none", "raised", "furrowed"})):
                if not isinstance(expression.get(field), str) or expression[field] not in allowed:
                    raise ValueError("per-character " + field + " must be explicitly authored")
                override[field] = expression[field]
            e["expressions"][cid] = override
        for cid in cids:
            expression = e["expressions"].get(cid, e)
            if expression["eyebrows"] != "none" and expression["intensity"] != "strong":
                raise ValueError("eyebrows require an explicitly authored strong expression for " + cid)
        selected.append(e)
    result["events"] = selected
    validate_reference_mapping(resolved, selected, ids)
    attach(result, style_request, preview)
    return result

def validate_identity_coverage(brief):
    if brief['kind'] == 'onboarding':
        allowed_roles = {'identity-source'}
    elif brief['role'] == 'production':
        allowed_roles = {'identity-approved'}
    else:
        allowed_roles = {'identity-draft', 'identity-approved'}
    for character in brief['characters']:
        character_id = character['id']
        if not any(reference['role'] in allowed_roles
                   and ('characterIds' not in reference or character_id in reference['characterIds'])
                   for reference in brief['references']):
            raise ValueError('no matching identity reference for character: ' + character_id)


def build_prompt(brief):
    # Preserve sourceText in the input archive only, never in the render prompt.
    render = {k: v for k, v in brief.items() if k != "sourceText"}
    from diary_style_lock import (CONTRACT, load_library,
                                  validate_human_component_references, validate_species_references)
    validate_identity_coverage(brief)
    human_ids = [character['id'] for character in brief['characters']
                 if character['species'] == 'human']
    validate_human_component_references(brief['references'], human_ids)
    validate_species_references(brief['references'], brief['characters'])
    rules = CONTRACT.read_text(encoding='utf-8')
    rules += ('\nEXISTING POSTER / ADDITION RULE: These same style requirements apply to edits, '
              'additions and replacements, not just new posters. Scene references, including old posters, '
              'supply facts, actions and composition ONLY, never drawing style. Re-render the requested '
              'scene in the current reference language, including both existing and added visible humans '
              'and pets; do not paste a new-style figure into an old-style scene. Preserve identities, '
              'age/body anchors, events and requested expressions. Human facial, hair and limb rules '
              'apply ONLY to humans; cats and dogs must follow their attached species guides, not the '
              'human nose, hair, hands or expression atlas. Keep each pet\'s own markings, ears, tail '
              'and body identity. Unrelated scenes and diary text remain unchanged in local composition.')
    purpose = "Create one full-body character lineup. Correct old geometry while preserving broad identity features. No preexisting approved atlas required. Use neutral_dot and no eyebrows." if brief["kind"] == "onboarding" else "Create an expression/action test sheet from selected scenes."
    bundled = [item for item in brief["references"] if item.get("origin") == "bundled"]
    fixed_pack = "\n".join(f"- {item.get('id')}: {item['path']} ({item['role']})" for item in bundled)
    style_library = load_library()
    vocabulary = style_library.get('expressionVocabulary', [])
    if human_ids and len(vocabulary) != 24:
        raise ValueError('human expression reference must define exactly 24 named expressions')
    expression_map = "\n".join(
        f"- {index:02d} {item['name']} ({item['id']}): eyes={item['eye_state']}; "
        f"brows={item['eyebrows']}; mouth={item['mouth']}"
        for index, item in enumerate(vocabulary, 1))
    text_plan = ''
    if brief['kind'] == 'diary':
        purpose = ('Create exactly ONE isolated scene illustration, no paper, text or panel borders. Keep all characters and props complete.'
                   if len(brief['events']) == 1 else
                   'Planning overview only: do not render these events together. Export each event with --scene N --request-output before generation.')
        text_plan = ('Each single-scene request requires generous transparent margins on every side, '
                     'preserving opaque WHITE character and prop interiors. '
                     'Scene boxes are invisible placement limits, never rectangular image frames. Background lines end naturally '
                     'around a small necessary prop; no full rooms, panoramic counters, walls or floors filling a band. '
                     'Local composition fits complete scenes without cropping and adds paper rules and Yozai text. '
                     'Do not draw dates, titles, captions, bubbles, labels, letters, numbers or paper lines.')
    return "\n".join([purpose, "Draft preview is not identity approval; never label it confirmed.", rules,
        "HARD IDENTITY AND STYLE LOCK (zero-tolerance acceptance): preserve each mapped character's recognizable visible features from that character's own uploaded source image or user-approved identity card, including face silhouette, hairline/hairstyle, glasses, age presentation, body type and clothing/accessory anchors. Do not transfer features between people. Use the approved master and every mandatory Reference image as binding, component-specific visual constraints; do not intentionally simplify, redesign or introduce a visibly different face, age/body proportion, line language or expression. If any required anchor or expression is visibly wrong, the result fails review and must not be called complete. Reference characters are examples of separate components, never identities or complete character templates. Compare and translate feature-by-feature; never copy any example person's whole appearance.",
        "Identity translation: preserve observed face silhouette, hair, glasses, clothing and body shape from each person's own photo/card. Keep the round-face baseline, short non-drooping open nose with upper gap, equal ROUND dot eyes of equal diameter, modest eye spacing, outermost small ear. All open pupils are true circles, never ovals. Mouth stays visibly below and separate from the nose, in the lower face. No separate neck: visible jaw/clothing boundary, side-facing body, fine white double-line limbs; far arm hidden unless action exposes it. All skin and uninked clothing interiors are opaque pure white, without gray shading, gradients or texture. Fuller figures have a visible clothed belly curve. ageGroup and optional adult ageStage come only from user information, default unknown. Use age-proportions-v1 only for relative age/height; appearance-variants-v1 for observed hair/clothing/accessory variety; age-variety-example-v2 only as an open-ended face/age/body component reference, never as a roster, age assignment or complete identity; human-expression-reference-v6 for the corresponding emotion's eye/mouth design. The approved master always governs drawing language and geometry. Do not use expression-draft-v2. Children, adolescents and unknown ages have neutral loose tops. Only explicitly adult women may have a subtle clothed chest contour. Never infer age or add anatomical detail. For onboarding show full body AND face detail, no generated labels. Feature examples never substitute a user's identity.",
        "Reference roles: identity-source supplies the character's uploaded source appearance; identity-draft is provisional; identity-approved locks the user-confirmed identity, never obsolete drawing geometry. Current master defines drawing grammar. geometry.human is the regular baseline; use geometry.bodyProfiles[bodyType].torsoWidth for the specified body type, keeping limbs fine. neckWidth=0 means no separate neck, NOT missing head/body boundary. Scene references supply the mapped environment, key objects and spatial relationships; simplify details without replacing the location. An identity card without characterIds is an explicitly shared lineup: use only event characters. Attach every listed image and use each only for its declared duty.",
        "Mandatory bundled reference pack (all must be attached for each visible human; master is not a substitute for component references):", fixed_pack,
        "Approved 24-expression vocabulary in chart order; map each visible human's intended emotion to the closest matching eye/mouth combination, preserving the described emotion. Do not add a third eye, unrelated wink, or expression detail absent from the selected match:", expression_map,
        text_plan,
        ("No text anywhere in style-lock illustration assets; all text is local composition." if 'styleLock' in brief else "Only header/title/caption/bubble/summary are renderable text; onboarding may label character names. All other metadata and scene descriptions are drawing instructions, never printed. No additional text."),
        "Use each character's own species dimensions and observable identity anchors. Preserve hairstyle, clothing and accessories from identity references. Take nose shape, upper contour gap, eye structure and body proportions from the current master and canonical geometry, correcting conflicting old-card geometry even during onboarding or preview. Geometry dimensions use head width H as the unit. Per-character expressions override event expression for that character; event expression applies only to characters without an override. Never spread one person's emotion to a pet with its own override. Selected eye_state overrides neutral expression only: open eye dots remain circular, lids only occlude them, closed eyes remain arcs. Temporary eyebrows require an explicitly authored strong exaggerated expression. Mouth length/shape follows the authored emotion at its low rear-side position.",
        json.dumps(render, ensure_ascii=False, indent=2)])


def generation_request(brief, scene=None):
    """Return the exact built-in imagegen arguments, with a checked master first.

    This prepares inputs; only the actual tool invocation proves transmission.
    A diary call draws ONE isolated event to avoid dense strip/panel generation.
    """
    import copy
    from diary_style_lock import LIBRARY, asset, load_library
    expected = asset(LIBRARY.parent, load_library()['master'])
    refs = brief['references']
    if not refs or refs[0].get('id') != 'style-lock-master' or refs[0]['path'] != expected:
        raise ValueError('generation request requires the current master as the first attachment')
    selected = copy.deepcopy(brief)
    if brief['kind'] == 'diary':
        if isinstance(scene, bool) or not isinstance(scene, int) or not 1 <= scene <= len(brief['events']):
            raise ValueError('diary generation request requires --scene 1..N; do not generate horizontal strips')
        validate_reference_mapping(refs, brief['events'], {c['id'] for c in brief['characters']})
        selected['events'] = [selected['events'][scene - 1]]
        visible = set(selected['events'][0]['characters'])
        selected['characters'] = [c for c in selected['characters'] if c['id'] in visible]
        if selected['protagonistId'] not in visible:
            selected['protagonistId'] = next(c['id'] for c in selected['characters'])
        mapped = set(selected['events'][0].get('referenceIds', []))
        selected['references'] = [r for r in selected['references']
                                  if r['role'] != 'layout'
                                  and (r['role'] != 'scene' or r['id'] in mapped)
                                  and ('characterIds' not in r or visible.intersection(r['characterIds']))]
        identity_roles = {'identity-approved'} if brief['role'] == 'production' else {'identity-draft', 'identity-approved'}
        for cid in visible:
            if not any(r['role'] in identity_roles and ('characterIds' not in r or cid in r['characterIds'])
                       for r in selected['references']):
                raise ValueError('selected scene has no matching identity reference for character: ' + cid)
        selected['styleLock'] = {k:v for k,v in selected['styleLock'].items()
                                 if k not in {'templateId','sceneCount','sceneBoxes'}}
    elif scene is not None:
        raise ValueError('--scene is only for diary')
    prompt = build_prompt(selected)
    if brief['kind'] == 'diary':
        prompt += ('\nDraw exactly ONE isolated vignette, not a poster, strip, grid or contact sheet. '
                   'Transparent exterior with generous transparent margins on every side; opaque WHITE interiors. '
                   'One clear action focus with minimum props, entire heads/feet/tails intact. '
                   'Facts not depictable in this one moment stay in the diary prose; do not invent extra panels. '
                   'No paper lines, no text, no rectangular filled background or straight cut-off scenery edges.')
    paths = list(dict.fromkeys(r['path'] for r in selected['references']))
    return {'prompt': prompt + '\n', 'referenced_image_paths': paths}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--graph", type=Path, help="Optional legacy graph; explicit species still required")
    parser.add_argument("--preview", action="store_true", help="User-requested draft; never grants approval")
    parser.add_argument("--scene", type=int, help="Generate one isolated diary event, 1-based")
    parser.add_argument("--request-output", type=Path, help="Exact imagegen argument JSON; use these attachments in the tool call")
    args = parser.parse_args()
    try:
        brief = validate_brief(load_brief(args.brief), args.brief.parent, args.preview, args.graph)
        prompt = build_prompt(brief) + '\n'
        if args.request_output:
            destinations = [args.request_output.resolve()] + ([args.output.resolve()] if args.output else [])
            if args.brief.resolve() in destinations or len(set(destinations)) != len(destinations):
                raise ValueError('request, prompt and input brief paths must be different')
            request = generation_request(brief, args.scene)
            prompt = request['prompt']
            args.request_output.write_text(json.dumps(request, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        elif args.scene is not None:
            raise ValueError('--scene requires --request-output')
        if args.output:
            if args.output.resolve() == args.brief.resolve():
                raise ValueError("output must not overwrite source brief")
            args.output.write_text(prompt, encoding="utf-8")
        else:
            print(prompt, end='')
    except (ValueError, OSError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
