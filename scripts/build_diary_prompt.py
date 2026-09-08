#!/usr/bin/env python3
"""Build prompts from authored schema-v2 inputs; never summarize or approve."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import unquote
SKILL_ROOT = Path(__file__).resolve().parents[1]
GRAPH_DATA_PATTERN = re.compile(r'<script\s+id="graph-data"\s+type="application/json">\s*(.*?)\s*</script>', re.DOTALL)
DATE_PATTERN = re.compile(r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b")
PLACEHOLDER_MARKERS = ("actual-person-", "实际人物", "实际关系", "占位")
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
    if DATE_PATTERN.search(html):
        raise ValueError("global character graph must not contain date-like text")
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
        elif isinstance(actual, bool) or not isinstance(actual, (float, int)) or not math.isfinite(actual) or abs(actual / target - 1) > .100001:
            raise ValueError(label + " must be within 10% of canonical target")
    check(value, canonical, "geometry")
    if not math.isclose(value["outerWidth"], 2 * value["stroke"] + value["innerGap"], abs_tol=1e-8):
        raise ValueError("outerWidth must equal 2*stroke+innerGap")
    widths = [value["armWidth"], value["legWidth"]]
    if max(widths) / min(widths) > 1.100001 or any(w <= 2 * value["stroke"] for w in widths):
        raise ValueError("arm/leg widths must match within 10% and retain white channels")
    return value

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
    chars = data.get("characters")
    if chars is None and graph:
        chars = list(load_character_graph(graph)[0].values())
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
        anchors = c.get("anchors")
        if not isinstance(anchors, list) or not 2 <= len(anchors) <= 12 or any(not isinstance(a, str) or not a.strip() or len(a) > 160 for a in anchors):
            raise ValueError("character anchors require 2-12 short observable identity features")
    if not isinstance(data.get("protagonistId"), str) or data["protagonistId"] not in ids:
        raise ValueError("protagonistId must identify an explicit character")
    refs = data.get("references")
    if not isinstance(refs, list) or not refs:
        raise ValueError("references must be a non-empty list")
    resolved, roles = [], set()
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
        with full.open("rb") as f:
            signature = f.read(16)
        if not (signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff") or signature.startswith((b"GIF87a", b"GIF89a")) or (signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")):
            raise ValueError("reference must be PNG/JPEG/GIF/WebP: " + path)
        roles.add(ref["role"])
        resolved.append({"path": str(full), "role": ref["role"]})
    needed = {"identity-source"} if kind == "onboarding" else ({"identity-approved"} if not preview else {"identity-draft", "identity-approved"})
    if not roles.intersection(needed):
        raise ValueError("missing identity reference role: " + "/".join(sorted(needed)))
    result = {"kind": kind, "role": "draft-preview" if preview else "production", "identity": identity, "protagonistId": data["protagonistId"], "characters": chars, "references": resolved, "geometry": geometry(data)}
    if kind == "onboarding":
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
    if not isinstance(events, list) or not 1 <= len(events) <= 4:
        raise ValueError("events must contain 1-4 explicitly selected scenes")
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
    return result

def build_prompt(brief):
    # Preserve sourceText in the input archive only, never in the render prompt.
    render = {k: v for k, v in brief.items() if k != "sourceText"}
    rules = (SKILL_ROOT / "references/style-system.md").read_text(encoding="utf-8")
    purpose = "Create one full-body character lineup. Correct old geometry while preserving broad identity features. No preexisting approved atlas required. Use neutral_dot and no eyebrows." if brief["kind"] == "onboarding" else ("Create an expression/action test sheet from selected scenes." if brief["kind"] == "expression" else "Create one complete 3:4 diary poster from selected scenes.")
    return "\n".join([purpose, "Draft preview is not identity approval; never label it confirmed.", rules,
        "Reference roles: identity-source supplies broad features only; identity-draft is provisional; identity-approved locks identity; style/layout supply their named role only; scene supplies facts. Attach all listed images.",
        "Only header/title/caption/bubble/summary are renderable text; onboarding may label character names. All other metadata and scene descriptions are drawing instructions, never printed. No additional text.",
        "Use each character's own species dimensions and anchors. Per-character expressions override event expression for that character; event expression applies only to characters without an override. Never spread one person's emotion to a pet with its own override. Selected eye_state overrides neutral expression only: open eye dots remain circular, lids only occlude them, closed eyes remain arcs. Temporary eyebrows require an explicitly authored strong exaggerated expression. Preserve identity, nose, upper contour gap and proportions; mouth length/shape follows the authored emotion at its low rear-side position.",
        json.dumps(render, ensure_ascii=False, indent=2)])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--graph", type=Path, help="Optional legacy graph; explicit species still required")
    parser.add_argument("--preview", action="store_true", help="User-requested draft; never grants approval")
    args = parser.parse_args()
    try:
        brief = validate_brief(load_brief(args.brief), args.brief.parent, args.preview, args.graph)
        prompt = build_prompt(brief)
        if args.output:
            if args.output.resolve() == args.brief.resolve():
                raise ValueError("output must not overwrite source brief")
            args.output.write_text(prompt + "\n", encoding="utf-8")
        else:
            print(prompt)
    except (ValueError, OSError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
