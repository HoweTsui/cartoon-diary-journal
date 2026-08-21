#!/usr/bin/env python3
"""Build a locked diary-image prompt from a small JSON brief."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
SKILL_ROOT = Path(__file__).resolve().parents[1]
GRAPH_DATA_PATTERN = re.compile(
    r'<script\s+id="graph-data"\s+type="application/json">\s*'
    r"(.*?)"
    r"\s*</script>",
    re.DOTALL,
)
DATE_PATTERN = re.compile(r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b")
PLACEHOLDER_MARKERS = ("actual-person-", "实际人物", "实际关系", "占位")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a stable cartoon diary prompt from JSON."
    )
    parser.add_argument("brief", type=Path, help="Path to the diary brief JSON")
    parser.add_argument(
        "--output", type=Path, help="Optional file path; otherwise print to stdout"
    )
    parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Task-specific character graph HTML; never use a stale template graph",
    )
    return parser.parse_args()


def require_text(data: dict, key: str, maximum: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{key} must be at most {maximum} characters")
    return value


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
    atlas_src = atlas.get("src")
    if (
        not isinstance(atlas_src, str)
        or not atlas_src.strip()
        or atlas_src.startswith(("/", ".."))
        or "://" in atlas_src
    ):
        raise ValueError("character graph atlas.src must be a relative local asset path")
    atlas_path = path.parent / atlas_src
    if not atlas_path.is_file():
        raise ValueError(f"character graph atlas is missing: {atlas_path}")
    cols = atlas.get("cols")
    rows = atlas.get("rows")
    if not isinstance(cols, int) or cols < 1 or not isinstance(rows, int) or rows < 1:
        raise ValueError("character graph atlas.cols and atlas.rows must be positive integers")
    characters: dict[str, dict] = {}
    names: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"graph node {index + 1} must be an object")
        character_id = require_text(node, "id", 64)
        name = require_text(node, "name", 20)
        node_text = json.dumps(node, ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            if marker in node_text:
                raise ValueError(
                    f"graph character {name} still contains placeholder text: {marker}"
                )
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
        characters[character_id] = node
        names.add(name)

    edges = graph_data.get("edges")
    if not isinstance(edges, list):
        raise ValueError("character graph edges must be a list")
    normalized_edges: list[dict] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"graph relationship {index + 1} must be an object")
        source = edge.get("source")
        target = edge.get("target")
        label = edge.get("label")
        if source not in characters or target not in characters or source == target:
            raise ValueError(f"graph relationship {index + 1} has invalid endpoints")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"graph relationship {index + 1} needs a label")
        for marker in PLACEHOLDER_MARKERS:
            if marker in label:
                raise ValueError(
                    f"graph relationship {index + 1} still contains placeholder text: {marker}"
                )
        normalized_edges.append(edge)
    return characters, normalized_edges


def resolve_character(reference: object, characters: dict[str, dict]) -> str:
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("character references must be non-empty strings")
    value = reference.strip()
    if value in characters:
        return value
    exact_name = [
        character_id
        for character_id, node in characters.items()
        if node.get("name", "").strip() == value
    ]
    if len(exact_name) == 1:
        return exact_name[0]
    fuzzy = []
    for character_id, node in characters.items():
        searchable = " ".join(
            [
                str(node.get("name", "")),
                str(node.get("role", "")),
                *[str(item) for item in node.get("anchors", [])],
                *[str(item) for item in node.get("notes", [])],
            ]
        )
        if value in searchable:
            fuzzy.append(character_id)
    if len(fuzzy) == 1:
        return fuzzy[0]
    if len(fuzzy) > 1:
        raise ValueError(f"角色信息“{value}”匹配到多人，请补充准确姓名或角色 ID")
    raise ValueError(
        f"角色“{value}”不在当前图谱中；请用户提供一张该角色图片，"
        "完成统一风格转绘并写入图谱后再生成日记"
    )


def normalize_brief(
    data: dict, characters: dict[str, dict]
) -> tuple[str, str, list[dict], str]:
    raw_date = require_text(data, "date", 10)
    try:
        date = dt.date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD and be a real date") from exc

    title = require_text(data, "title", 20)
    events = data.get("events")
    if not isinstance(events, list) or not 3 <= len(events) <= 6:
        raise ValueError("events must be a list containing 3 to 6 items")

    normalized: list[dict] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise ValueError(f"event {index} must be an object")
        scene = require_text(event, "scene", 120)
        caption = require_text(event, "caption", 12)
        character_ids = event.get("characters", [])
        if not isinstance(character_ids, list) or not character_ids:
            raise ValueError(f"event {index} characters must be a non-empty list")
        resolved_ids = [resolve_character(item, characters) for item in character_ids]
        normalized.append(
            {"scene": scene, "caption": caption, "characters": resolved_ids}
        )

    summary = data.get("summary", "")
    if summary:
        if not isinstance(summary, str) or len(summary.strip()) > 24:
            raise ValueError("summary must be a string of at most 24 characters")
        summary = summary.strip()

    header = f"{date:%Y.%m.%d} {WEEKDAYS[date.weekday()]}"
    return header, title, normalized, summary


def character_description(node: dict) -> str:
    anchors = "，".join(item.strip() for item in node["anchors"])
    return f"{node['name']}：{anchors}"


def build_prompt(
    header: str,
    title: str,
    events: list[dict],
    summary: str,
    characters: dict[str, dict],
    relationships: list[dict],
) -> str:
    used_ids: list[str] = []
    event_lines: list[str] = []
    for index, event in enumerate(events, start=1):
        for character_id in event["characters"]:
            if character_id not in used_ids:
                used_ids.append(character_id)
        names = "、".join(characters[item]["name"] for item in event["characters"])
        event_lines.append(
            f'{index}. {names}；{event["scene"]}；caption "{event["caption"]}"'
        )

    identity_lines = [f"- {character_description(characters[item])}" for item in used_ids]
    relationship_lines = []
    used_set = set(used_ids)
    for relation in relationships:
        if relation["source"] in used_set and relation["target"] in used_set:
            source_name = characters[relation["source"]]["name"]
            target_name = characters[relation["target"]]["name"]
            relationship_lines.append(
                f"- {source_name} —{relation['label']}→ {target_name}"
            )
    summary_line = f'Bottom closing line (verbatim): "{summary}"' if summary else ""

    sections = [
        "Use case: illustration-story",
        "Asset type: one original vertical Chinese diary-journal page",
        (
            "Input images: Image 1 is the current style anchor; Image 2 is this "
            "task's actual identity atlas. Any later user-uploaded photo is an "
            "identity-only reference and must be converted into this same atlas style "
            "before it is used."
        ),
        "",
        f'Exact top header (verbatim): "{header}"',
        f'Exact subtitle (verbatim): "{title}"',
        summary_line,
        "",
        "Story moments:",
        *event_lines,
        "",
        "Canonical identity anchors:",
        *identity_lines,
        "",
        "Graph relationships to preserve in scenes:",
        *(relationship_lines or ["- 本页只出现单人动作，不引入未登记关系"]),
        "",
        (
            "Style lock: original minimalist black-ink diary cartoon on smooth "
            "pure-white paper with exactly 14-18 evenly spaced very pale cyan "
            "notebook rules. Match the current atlas's medium-thick, slightly "
            "wobbly line weight and deliberately reduced detail. Every human keeps "
            "the atlas head silhouette (varied round-ish, pear, soft wedge, or "
            "rounded trapezoid), exactly two complete separated dot eyes with a "
            "slightly wider gap, one nose between eyes and mouth, and one mouth "
            "placed lower beneath the nose. Nose shapes may vary by identity: a "
            "small rounded, button-like, short curved, or longer silhouette-breaking "
            "nose; a rounded nose has a small open break in its own contour and is "
            "never a closed O or square block. Use readable arms, slender two-line "
            "lower legs with a visible white gap, readable hands/paws, oversized "
            "flat shoes, sparse hair strokes or "
            "one solid-black hair shape, and a few solid-black fills only. Pets keep "
            "their complete ears, eyes, nose, mouth and tail. No gray modeling, "
            "shading, realistic texture, or decorative color. Pets are flat simplified "
            "silhouettes with two ears, two eyes, a species-correct single solid-black "
            "nose (for cats: smaller and centered below the eyes; for dogs: at the "
            "muzzle tip), a tiny mouth, compact "
            "torso, clear legs/paws and a simple tail; dogs keep a visibly oversized "
            "head, widely spaced dot eyes and short thick rounded paws with one to "
            "three blunt toe notches. Never render realistic fur strands, whiskers, "
            "eye reflections, or fur shading. Expression changes may alter only eye "
            "openness/roundness, mouth shape and up to two temporary emotion marks; "
            "neutral faces have no brows. Never give an animal a human C-shaped nose, dog-sized cat nose, misplaced "
            "cat nose, nose bridge, nostrils, or a "
            "second nose. Do not alter identity head, nose placement, hair/ear shape, limb length, hands/"
            "paws, shoes, or head-to-body ratio."
        ),
        (
            "Composition: strict 9:16 tall portrait; date and weekday are the first "
            "and highest content; subtitle immediately below; three to six airy "
            "scenes flowing continuously from top to bottom on the ruled lines; one "
            "action per scene; wide margins; no panel borders."
        ),
        (
            "Identity lock: preserve every listed head shape, nose direction, hair "
            "strokes, eye spacing, mouth position, accessory, solid-black fill "
            "placement, clothing structure, head-to-body ratio, two-line limb "
            "shape, shoe shape, and pet ear/tail shape in every scene."
        ),
        (
            "Upload conversion lock: user photos contribute only broad identity "
            "cues such as hair silhouette, clothing block, accessory, body impression, "
            "pet ears/tail and fur color. They must not contribute photographic skin, "
            "fur, material, lighting, background, or realistic anatomy. The current "
            "atlas and style anchor override the photo whenever they conflict. Before "
            "delivery, compare the new character with the atlas for line weight, facial "
            "grammar, nose-contour break, limb thickness, head-to-body ratio, and "
            "black-white fill placement; regenerate if any item drifts."
        ),
        (
            "Originality and privacy: use only the task graph and user-authorized "
            "identity references. Do not reproduce any published character, "
            "signature font, page, gag, logo, composition, unlisted private detail, "
            "location, brand, or product."
        ),
        (
            "Avoid: photorealism, semi-realism, realistic anatomy, cinematic "
            "lighting, 3D, gradients, glossy surfaces, skin shading, realistic food, "
            "painterly rendering, watercolor, pencil grain, crosshatching, paper "
            "fibers, film grain, noise, speckles, vintage distress, generic identical "
            "noses, closed circular noses, square noses, hard right-angle heads, "
            "single-eye profiles, missing facial features, human noses on animals, human nose bridges on animals, thick realistic legs, hair-thin "
            "broken legs, realistic pet fur, realistic pet eyes, chibi "
            "proportions, pastel storybook art, kawaii sticker art, manga, polished "
            "commercial vector art, thick uniform outlines, perfect curves, dense "
            "backgrounds, missing date, wrong weekday, copied copyrighted characters, "
            "identity drift, photorealistic user uploads, and mixed rendering styles."
        ),
    ]
    return "\n".join(sections)


def main() -> int:
    args = parse_args()
    try:
        characters, relationships = load_character_graph(args.graph)
        header, title, events, summary = normalize_brief(
            load_brief(args.brief), characters
        )
        prompt = build_prompt(
            header, title, events, summary, characters, relationships
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(prompt + "\n", encoding="utf-8")
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
