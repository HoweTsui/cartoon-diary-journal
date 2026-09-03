#!/usr/bin/env python3
"""Build a rich, deterministic diary-image prompt from a lightweight brief.

The public Skill keeps the workflow simple: ``date`` + ``text`` is enough for a
single-event page. Richer event/inventory fields and source images remain
optional, but when present they are bound to the scene so visible facts survive
the style translation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
SKILL_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_GEOMETRY_ATLAS = SKILL_ROOT / "assets" / "style-reference" / "character-lineup-demo.png"
PUBLIC_FACE_GEOMETRY = SKILL_ROOT / "assets" / "style-reference" / "face-geometry-closeup.png"
PUBLIC_LAYOUT_ANCHOR = SKILL_ROOT / "assets" / "style-reference" / "diary-layout-only.png"
GRAPH_DATA_PATTERN = re.compile(
    r'<script\s+id="graph-data"\s+type="application/json">\s*'
    r"(.*?)"
    r"\s*</script>",
    re.DOTALL,
)
DATE_PATTERN = re.compile(r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b")
PLACEHOLDER_MARKERS = ("actual-person-", "实际人物", "实际关系", "占位")
MAX_EVENTS = 12
MAX_SCENE_TEXT = 180
EYE_STATES = {
    "neutral_dot": "中性：两枚等大的正圆黑点",
    "closed_arc": "闭眼：一或两条简短弧线，保留原头脸几何",
    "half_lid": "半睑：短弧压在小圆点上，不画眉毛",
    "wide_round": "惊讶：放大的圆形眼原子，仍为圆形且两眼成对",
    "crossed": "眩晕：极简叉形眼原子，仅在明确失神/撞击语义时使用",
}
EMOTION_HINTS = (
    (("大笑", "哈哈", "开心", "完成", "成功", "喜欢"), ("happy/completion", "medium")),
    (("吃", "午饭", "晚饭", "饺子", "鸡", "喝", "没胃口", "勉强"), ("eating", "mild")),
    (("迟到", "晚了", "等待", "等车", "错过", "慌", "来不及", "请假", "八点半"), ("waiting/late", "medium")),
    (("生气", "气", "愤怒", "恼火"), ("anger", "strong")),
    (("惊", "突然", "意外", "吓", "天气", "云", "天空", "拍下", "拍照"), ("surprise", "medium")),
    (("困", "睡", "熬夜", "疲惫"), ("sleepy", "mild")),
    (("哭", "委屈", "难过", "眼泪"), ("sad/cry", "medium")),
    (("猫", "狗", "宠物", "抱", "摸", "喜欢"), ("pet/love", "medium")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a stable cartoon diary prompt from JSON."
    )
    parser.add_argument("brief", type=Path, help="Path to the diary brief JSON")
    parser.add_argument("--output", type=Path, help="Optional output file")
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


def resolve_character(reference: object, characters: dict[str, dict]) -> str:
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("character references must be non-empty strings")
    value = reference.strip()
    if value in characters:
        return value
    exact_name = [cid for cid, node in characters.items() if node.get("name", "").strip() == value]
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


def _string_list(value: object, label: str, maximum_items: int = 8, maximum_text: int = 80) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ValueError(f"{label} must be a list with at most {maximum_items} items")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > maximum_text:
            raise ValueError(f"{label}[{index}] must be a non-empty short string")
        result.append(item.strip())
    return result


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _compact_caption(value: str, index: int) -> str:
    compact = re.sub(r"[\s，。！？、,.!?；;：:]", "", value)
    if 4 <= len(compact) <= 10:
        return compact
    if len(compact) > 10:
        return compact[:10]
    return f"第{index}件小事"


def _derive_title(data: dict, fallback_scene: str = "") -> str:
    value = data.get("title")
    if value:
        return optional_text(value, "title", 12)
    text = data.get("text") or fallback_scene
    if isinstance(text, str):
        compact = re.sub(r"[\s，。！？、,.!?；;：:]", "", text.strip())
        if compact:
            return compact[:12]
    return "今天的小故事"


def _infer_emotion(text: str) -> tuple[str, str]:
    for words, result in EMOTION_HINTS:
        if any(word in text for word in words):
            return result
    return "calm/observing", "mild"


def _default_eye_state(emotion: str) -> str:
    if emotion in {"sleepy", "sad/cry", "pet/love"}:
        return "closed_arc"
    if emotion == "surprise":
        return "wide_round"
    if emotion in {"anger", "waiting/late"}:
        return "half_lid"
    return "neutral_dot"


def _normalize_inventory(event: dict, scene: str) -> dict:
    raw = event.get("inventory") or {}
    if not isinstance(raw, dict):
        raise ValueError("event inventory must be an object")
    subjects = _string_list(raw.get("subjects", event.get("subjects")), "inventory.subjects")
    props = _string_list(raw.get("props", event.get("props")), "inventory.props")
    relations = _string_list(raw.get("relations", event.get("relations")), "inventory.relations")
    must_keep = _string_list(raw.get("must_keep", event.get("must_keep")), "inventory.must_keep", maximum_items=10)
    flexible = _string_list(raw.get("flexible", event.get("flexible")), "inventory.flexible", maximum_items=10)
    if not must_keep:
        must_keep = ["本场出场角色与核心动作", scene]
    if not flexible:
        flexible = ["次要道具与背景可按语义简化", "精确摆位可在左/右/前/后相对区域内微调"]
    return {
        "subjects": subjects,
        "props": props,
        "relations": relations,
        "must_keep": must_keep,
        "flexible": flexible,
    }


def normalize_brief(data: dict, characters: dict[str, dict]) -> tuple[str, str, list[dict], str]:
    raw_date = data.get("date")
    if raw_date == "today":
        date = dt.date.today()
    else:
        if not isinstance(raw_date, str) or not raw_date.strip():
            raise ValueError("date must be YYYY-MM-DD or today")
        try:
            date = dt.date.fromisoformat(raw_date.strip())
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD and be a real date") from exc

    raw_events = data.get("events")
    text = data.get("text", "")
    if text and (not isinstance(text, str) or len(text.strip()) > 500):
        raise ValueError("text must be at most 500 characters")
    text = text.strip() if isinstance(text, str) else ""
    top_characters = data.get("characters", [])
    if top_characters and not isinstance(top_characters, list):
        raise ValueError("characters must be a list when provided")

    lightweight = raw_events is None or raw_events == []
    if lightweight:
        if not text:
            raise ValueError("provide text, or provide at least one explicit event")
        raw_events = [{"scene": text, "characters": top_characters}]
    if not isinstance(raw_events, list) or not 1 <= len(raw_events) <= MAX_EVENTS:
        raise ValueError(f"events must be a list containing 1 to {MAX_EVENTS} items")

    first_scene = raw_events[0].get("scene", "") if isinstance(raw_events[0], dict) else ""
    title = _derive_title(data, first_scene)
    normalized: list[dict] = []
    for index, raw_event in enumerate(raw_events, start=1):
        if not isinstance(raw_event, dict):
            raise ValueError(f"event {index} must be an object")
        scene = require_text(raw_event, "scene", MAX_SCENE_TEXT)
        raw_caption = raw_event.get("caption")
        caption = _compact_caption(raw_caption.strip(), index) if isinstance(raw_caption, str) and raw_caption.strip() else _compact_caption(scene, index)
        if not 4 <= len(caption) <= 10:
            raise ValueError(f"event {index} caption must contain 4 to 10 characters")
        bubble = raw_event.get("bubble", "")
        bubble = optional_text(bubble, f"event {index} bubble", 6) if bubble else ""
        raw_ids = raw_event.get("characters", top_characters if lightweight and index == 1 else [])
        if raw_ids is None:
            raw_ids = []
        if not isinstance(raw_ids, list):
            raise ValueError(f"event {index} characters must be a list when provided")
        resolved_ids = _dedupe([resolve_character(item, characters) for item in raw_ids])

        source_images = raw_event.get(
            "images",
            raw_event.get("sourceImages", data.get("images", data.get("sourceImages", []))),
        )
        source_images = _string_list(source_images, f"event {index} images", maximum_items=6, maximum_text=240)
        for image_index, source in enumerate(source_images):
            valid_relative_asset_path(source, f"event {index} images[{image_index}]")
            source_path = SKILL_ROOT / Path(source.replace("\\", "/"))
            if not source_path.is_file():
                raise ValueError(
                    f"event {index} source image is missing: {source_path}"
                )

        expression, intensity = _infer_emotion(" ".join([scene, caption, bubble]))
        expression = optional_text(raw_event.get("emotion"), f"event {index} emotion", 40, expression)
        intensity = optional_text(raw_event.get("intensity"), f"event {index} intensity", 10, intensity)
        if intensity not in {"mild", "medium", "strong"}:
            raise ValueError(f"event {index} intensity must be mild, medium, or strong")
        eye_state = optional_text(raw_event.get("eye_state"), f"event {index} eye_state", 30, _default_eye_state(expression))
        if eye_state not in EYE_STATES:
            raise ValueError(f"event {index} eye_state must be one of: {', '.join(EYE_STATES)}")
        zone = raw_event.get("zone")
        if zone is not None and (not isinstance(zone, int) or not 1 <= zone <= 4):
            raise ValueError(f"event {index} zone must be an integer from 1 to 4")

        normalized.append(
            {
                "scene": scene,
                "caption": caption,
                "bubble": bubble,
                "characters": resolved_ids,
                "secondary_action": optional_text(
                    raw_event.get("secondary_action", raw_event.get("secondaryAction")),
                    f"event {index} secondary_action",
                    100,
                ),
                "relation": optional_text(raw_event.get("relation"), f"event {index} relation", 120),
                "emotion": expression,
                "intensity": intensity,
                "eye_state": eye_state,
                "inventory": _normalize_inventory(raw_event, scene),
                "source_images": source_images,
                "zone": zone or ((index - 1) % 4) + 1,
            }
        )

    if sum(bool(event["bubble"]) for event in normalized) > 3:
        raise ValueError("a diary page may contain at most three dialogue bubbles")
    summary = optional_text(data.get("summary"), "summary", 24) if data.get("summary") else ""
    header = f"{date:%Y.%m.%d} {WEEKDAYS[date.weekday()]}"
    return header, title, normalized, summary


def _prompt_anchor_text(node: dict) -> str:
    """Keep legacy graph prose from contradicting the current face blueprint."""
    anchors = "；".join(item.strip() for item in node["anchors"])
    anchors = re.sub(r"35\s*[-–]\s*45\s*(?:度|degrees)", "25–35°", anchors)
    anchors = anchors.replace("长断口", "空白断口")
    return anchors


def character_description(node: dict) -> str:
    return f"{node['name']}：{_prompt_anchor_text(node)}"


def scene_character_card(character_id: str, node: dict) -> str:
    anchors = _prompt_anchor_text(node)
    avatar = node.get("avatarSrc") or "atlas crop fallback"
    return (
        f"[{character_id} | {node['name']} | avatar={avatar} | atlas col={node['col']}, row={node['row']}] "
        "CANONICAL HEAD/FACE OVERRIDE (highest priority; copy the approved Image 2/3 geometry, not a generic cartoon): near-round or softly organic head with the approved width/height, never elongated; exactly two equal-diameter solid circular dot eyes placed slightly high with a clear white margin around the outer eye; one short horizontal, sideways, upper-open, unfilled human half-ellipse nose directly below the eyes; one small low mouth clearly separated from the nose; a short hairline-to-forward-eye outer arc followed by a clean blank break of about 1.5 eye-dot heights to the nose root; no eyebrow, forehead, bridge or inner-ear line. "
        f"IDENTITY ANCHORS (secondary; preserve hair, clothing, accessories and other identity cues, but ignore any conflicting face or angle wording): {anchors}; CURRENT geometry override: exactly 25-35 degrees slightly-forward half-side, not frontal and not a true side profile; preserve this identity card independently; half-side left/right 25-35 degrees; visible accessories, especially eyeglass frames, bridge and temples, use the same 5-6px black stroke as the face and clothing with no local thickening or hairline stroke; "
        "nose must remain separately drawn and visibly present; ear interiors stay blank with no inner-ear decoration; "
        "no regular-width cartoon limbs: uniform hairline-thin arm/thigh/calf or animal limb shafts at the 1/32 target, hands/paws only slightly larger; "
        "keep the head, hands and feet/shoes at the confirmed canonical size while shortening the torso and all body segments below the head to about 90% of the previous card proportion; "
        "any legacy angle wording in an anchor never overrides the 25-35 degree half-side direction lock; final face check: do not lengthen the head, enlarge the eyes, turn the nose downward, merge nose and mouth, or hide the forehead/eyes under oversized hair"
    )


def _inventory_line(inventory: dict) -> str:
    def show(items: list[str]) -> str:
        return "、".join(items) if items else "无额外清单"

    return (
        f"must_keep=[{show(inventory['must_keep'])}]; "
        f"subjects=[{show(inventory['subjects'])}]; props=[{show(inventory['props'])}]; "
        f"relations=[{show(inventory['relations'])}]; flexible=[{show(inventory['flexible'])}]"
    )


def _source_image_line(sources: list[str]) -> str:
    if not sources:
        return "source_images=[none supplied; use only written facts and do not invent a recognizable object]"
    joined = ", ".join(sources)
    return (
        f"source_images=[{joined}]; each listed image must be supplied to ImageGen for this scene "
        "after the four fixed style references and treated as a content-fact reference, not a style reference"
    )


def build_prompt(
    header: str,
    title: str,
    events: list[dict],
    summary: str,
    characters: dict[str, dict],
    relationships: list[dict],
) -> str:
    for asset, label in (
        (PUBLIC_GEOMETRY_ATLAS, "public geometry atlas"),
        (PUBLIC_FACE_GEOMETRY, "public face-geometry closeup"),
        (PUBLIC_LAYOUT_ANCHOR, "public layout-only anchor"),
    ):
        if not asset.is_file():
            raise ValueError(f"required {label} is missing: {asset}")

    used_ids: list[str] = []
    event_lines: list[str] = []
    scene_card_lines: list[str] = []
    for index, event in enumerate(events, start=1):
        for character_id in event["characters"]:
            if character_id not in used_ids:
                used_ids.append(character_id)
        names = "、".join(characters[item]["name"] for item in event["characters"]) or "按本场文字/图片事实处理的角色"
        secondary = event["secondary_action"] or "无；不要凭空添加第二个故事"
        relation = event["relation"] or "按可见相对关系表达，不用像素坐标"
        bubble = f'；bubble="{event["bubble"]}"' if event["bubble"] else ""
        event_lines.append(
            f"Zone {event['zone']} ({'main' if index <= 4 else 'grouped'}; source event {index}): "
            f"subjects={names}; scene={event['scene']}; secondary_action={secondary}; relation={relation}; "
            f"{_source_image_line(event['source_images'])}; {_inventory_line(event['inventory'])}; "
            f"event-driven expression={event['emotion']} "
            f"intensity={event['intensity']}; eye_atom={event['eye_state']}; "
            f'mandatory 4-10 character caption="{event["caption"]}" in the fixed right-side caption lane{bubble}'
        )
        if event["characters"]:
            cards = " || ".join(
                scene_character_card(character_id, characters[character_id])
                for character_id in event["characters"]
            )
        else:
            cards = "No named graph character supplied; do not invent identity facts or a recognizable face."
        scene_card_lines.append(
            f"Scene {index} cards (apply EACH independently): {cards}; one instance per character in a scene "
            "unless the source explicitly requires sequence/video/mirror; no clone fillers."
        )

    identity_lines = [f"- {character_description(characters[item])}" for item in used_ids]
    used_set = set(used_ids)
    relationship_lines = [
        f"- {characters[relation['source']]['name']} —{relation['label']}→ {characters[relation['target']]['name']}"
        for relation in relationships
        if relation["source"] in used_set and relation["target"] in used_set
    ]
    summary_line = f'Bottom closing line (verbatim): "{summary}"' if summary else "No closing line supplied; do not invent one."

    sections = [
        "Use case: illustration-story. Asset type: one original vertical Chinese diary-journal page, rendered as one complete 3:4 poster, never a comic grid or a multi-page continuation.",
        (
            "REQUIRED image inputs, in order: Image 1 is this task's actual identity atlas and is identity-only; when a node lists avatarSrc, load that independent 1:1 upper-body avatar beside the atlas and use it as the direct identity crop. "
            "Image 2 is assets/style-reference/character-lineup-demo.png and is the confirmed public GEOMETRY reference only (head, eyes, nose, body, limbs, shorts hems). "
            "Image 3 is assets/style-reference/face-geometry-closeup.png and is the enlarged facial and animal-nose gate only (eye atoms, face-contour break, human open half-ellipse nose, species nose). "
            "Image 4 is assets/style-reference/diary-layout-only.png and is layout-only (ruled paper, header, vertical rhythm, whitespace, centered date/title and fixed typography). Image 4 intentionally contains no character identity. "
            "Never inherit Image 2 or Image 3's identity, never redraw an input atlas as a lineup or scene, and stop if any required image is absent. User photos are temporary identity cues and must be converted into this same original atlas style."
        ),
        (
            "SOURCE-FACT INPUT GATE: after the four fixed references, append each event's listed source_images to the ImageGen input for that event. "
            "Read each source image as a scene-fact reference: compare visible subject/animal count, object count and shape, main action, facial/body reaction, foreground-midground-background layering, and left/right/front/back/near/far relations. "
            "Preserve those facts in must_keep even when the drawing stays simple; flexible details may only simplify secondary props or exact placement without changing meaning. Do not let a style reference overwrite a source image's content."
        ),
        (
            "CANONICAL HEAD/FACE BLUEPRINT — HIGHEST PRIORITY, BEFORE SCENE, PHOTO, EXPRESSION OR BODY RULES: copy the confirmed character-lineup-demo.png and face-geometry-closeup.png head geometry as a stable construction template. "
            "Use a near-round or softly organic identity head with the approved width/height; never an elongated oval, tall adult head, generic anime face or oversized hair mass. Place exactly two equal-diameter solid circular dot eyes slightly high in the head, with the outside eye clearly separated from the head outline by white space. "
            "Under the eyes draw exactly one short, horizontal, sideways human nose: an unfilled half-ellipse open along its upper edge, lightly projecting in the facing direction. Keep it short and separate from a small low mouth. Never make the nose a long bridge, downward U/C, closed O, black blob, nostril dot, animal nose or missing feature. "
            "From the hairline/fringe end to just above the forward eye draw only a short outer arc; after that arc leave a clean empty break of about 1.5 eye-dot heights down to the nose root. No eyebrow, forehead, bridge, extra contour or ear-interior mark may enter this blank channel. This blueprint overrides raw graph-anchor wording, user-photo anatomy, pose, expression and body-scale instructions. "
            "PRIMARY DRAWING GATE — BONE-THIN RULED-DIARY LOCK: preserve the written and visible content facts before translating them into style. "
            "Use smooth pure-white paper with 14-18 evenly spaced very pale cyan notebook rules. People, animals, props, furniture, architecture, visible accessories (including eyeglass frames, bridge and temples), ground marks and background/environment strokes all use the same stable medium-thick pure-black ink; background environment and visible accessories must never introduce a different line-weight tier. "
            "Every visible human and animal must be a clear 25-35 degree slightly-forward half-side view, facing unmistakably left or right. Do not use a frontal face, a near-frontal portrait, a straight-at-camera face, a standard 90-degree正侧面/full profile, or one-eye side profile. The nose, cheek, ear, shoulder and torso overlap must communicate the same direction. "
            "Human heads keep the approved atlas width/height and identity silhouette; do not enlarge or elongate them. A human has exactly one separate, clearly visible sideways unfilled upper-open half-ellipse nose; the nose is mandatory and may not be omitted, hidden, merged into the outline, replaced by the mouth or covered by an expression/prop. Never use a downturned U/C shape, black button, nostril dot, closed O or animal nose. An animal has exactly one clearly visible species-correct solid-black nose only. "
            "On every human, draw a short curved outer-head contour from the hairline/fringe end to just above the forward eye, then leave a completely empty break of about 1.5 eye-dot heights down to the nose root. No eyebrow, forehead line, nose bridge or head-outline segment may cross this blank channel. ear interiors must remain plain white: use only the outer ear silhouette, with no inner-ear curve, ear-fold mark, hatching, shading or decorative line."
        ),
        (
            "FINAL FACE CHECK BEFORE RENDERING: the head must still look like the confirmed atlas rather than a generic long cartoon head. The face must retain a separate, clearly visible and unfilled human nose: one short sideways, upper-open half-ellipse with no black fill or nostril dot. If the pose would hide the nose, adjust the pose within the approved half-side angle instead of dropping it. The mouth stays low and visibly separate. "
            "Use the approved atlas's canonical eye-dot diameter exactly; this is the canonical eye-dot diameter baseline for neutral identity. "
            "FIRST-PASS ANTI-FRONT LOCK: every character is 25-35 degree half-side, never frontal, never a true side profile and never standard 90-degree正侧面."
        ),
        (
            "P0 geometry lock — HALF-SIDE DIRECTION LOCK: the approved presentation is only the previously confirmed 25-35 degree偏正半侧面, not正面 and not正侧面. Keep both same-size eyes visible, the outer eye separated from the outline, the nose projecting sideways in the facing direction, one rear ear visible, and the cheek/jaw contour softly overlapping the neck. "
            "Do not rotate the head to a profile, flatten the face into an icon, or leave a frontal head on a turned body. This direction lock applies independently to every new character, supporting character and pet in every scene."
        ),
        (
            "FIRST-PASS UNIFORM ULTRA-THIN LIMB LOCK: first-pass target is the same 1/32 head-width ultra-thin double-line shaft for upper arms, forearms, thighs, calves and animal limb shafts excluding hands/paws. "
            "The previous 1/28 head-width ultra-thin form is now only a maximum ceiling; the same 1/24 target remains only an absolute maximum ceiling, while 1/22 of head width is a failure ceiling, never a drawing target; the outer shaft width no more than 1/24 of head width is still a hard upper bound. Arm and leg shafts must be equally thin, with a visible white channel and no local thickening caused by perspective, clothing, running, sitting or eating. "
            "Keep the head, hands and feet/shoes at the confirmed canonical size. The body proportion about 90% of the previous character-card proportion: shorten the torso, shoulder-to-hip span and every body segment below the head by approximately 10% overall; do not stretch the head, shrink the hands/feet, or restore adult proportions. Hands/paws can be slightly larger only at the terminal end. Shorts/trousers may be wider as cloth blocks, but every cuff must visibly narrow to the same ultra-thin calf and include a white separation. Torso stays narrow, no more than about 55% of head width; head remains at least 30% of standing height."
        ),
        (
            "CONTROLLED EXPRESSION ATOMS: expression reference images define a finite visual vocabulary, not permission to invent arbitrary facial geometry. Choose only the relevant supplied atom — neutral_dot, closed_arc, half_lid, wide_round, or crossed — and keep it simple, clean, and semantically justified. "
            "Neutral identity uses two equal solid circular dots. A scene may use an approved expression-derived eye atom, but head shape, nose, eye placement, face-contour break, identity silhouette, limb geometry and half-side direction remain locked. Never turn an eye into an oval, almond, irregular blob, reflective realistic eye or oversized single eye. "
            "Vary emotion first through low mouth shape, black mouth-hole/teeth, hand gesture, body reaction and at most two temporary exterior marks. Event strength is mild for ordinary facts, medium for explicit surprise/happiness, and strong only for explicit anger, laughter, crying or impact."
        ),
        f'Exact top header (verbatim, horizontal-center, fixed date size): "{header}"',
        f'Exact title (verbatim, directly below and horizontal-center, fixed title size 1.25-1.35x date): "{title}"',
        (
            "Typography lock: use one consistent original handwritten Chinese display-lettering description across the whole page. Date, title, scene-caption and bubble sizes are fixed and shared across pages; never shrink text to make room. "
            "Title is <=12 characters, every mandatory caption is 4-10 characters, every optional bubble is <=6 characters, and there is no extra text, gibberish, logo or signature font. ImageGen remains the text renderer: reproduce the exact quoted strings, and any wrong, missing or additional text means whole-page regeneration."
        ),
        summary_line,
        (
            f"Composition: one complete 3:4 poster only, with a default of 4 open narrative zones for {len(events)} source events. A single event becomes one larger hero scene with 1-3 real related details and generous clean whitespace; do not invent filler scenes or duplicate people. "
            "Many source events stay represented in the internal scene inventory and are grouped by meaning into four zones without a comic grid, tiny figures, squeezed captions, another page, or deletion of must_keep facts. Each source event has one main action plus at most one secondary action. "
            "Use semantic left/right/front/back/near/far relationships instead of pixel coordinates. The image body uses about 70-75% width and the fixed right-side caption lane about 20-25%; keep captions out of drawings and dialogue. Leave at least one full notebook-rule height, preferably 1.5, between neighboring scene bounds."
        ),
        (
            "PER-SCENE CHARACTER-CARD LOCK — before composing each scene, apply every visible character's own card independently. Never use the protagonist's head, face, nose, hair, clothing, body, limbs, shoes, paws, ears or tail as a default for another character. "
            "Each card is an identity input, not a suggestion: preserve its atlas cell, 1:1 avatarSrc when present, head silhouette, hair/ear outline, eye spacing and approved atom baseline, nose direction/type, mouth position, clothing/accessory blocks, visible accessory line weight (including eyeglass frames, bridge and temples), head-to-body ratio, equal ultra-thin arm/leg shafts and shoe/paw structure. If one visible character fails its own card, regenerate the whole page."
        ),
        *scene_card_lines,
        "Story scene inventory (explicit facts and supplied images override auto extraction; must_keep is hard, flexible is semantic-only):",
        *event_lines,
        "Canonical identity anchors — preserve these across every repeated appearance; choose pose/expression around them, never redraw a generic substitute:",
        *(identity_lines or ["- No named identity supplied; preserve only visible/textual facts and ask only if identity changes the story."]),
        "Graph relationships to preserve when relevant; do not add unregistered people or pets:",
        *(relationship_lines or ["- No registered relationship required for this page."]),
        (
            "Atlas gate: inspect this task's actual identity atlas and independent avatars before rendering. If any person or pet is near-front-facing, standard side profile, missing the contour break, using the wrong nose, showing unequal/irregular eyes, or having thick arm/leg shafts, rebuild the atlas first. Never propagate a failed atlas into a diary page."
        ),
        (
            "P0 visual gate: render only when all conditions are simultaneously true — (1) every visible human/animal is the confirmed 25-35 degree half-side, never front-facing, never a true side profile and never正侧面, with both eyes/one rear ear visible and the outer eye clear of the outline; (2) every human has the short outer arc plus the clean blank break of about 1.5 eye-dot heights; (3) every human has one separate clearly visible unfilled sideways nose and every animal one clearly visible species-correct solid nose; ear interiors are blank with no decorative inner lines; (4) arms, legs and animal limb shafts use the same 1/32 target and never exceed the 1/24 ceiling, hands/paws alone slightly larger, head/hands/feet canonical size retained, body below the head about 90% of the previous proportion, and trouser separation preserved; visible accessories including eyeglass frames, bridge and temples use the same 5-6px black stroke with no local thickening or hairline stroke; (5) each repeated character matches its own card; (6) must_keep facts, subject count, action and semantic positions are present; (7) centered header/title, fixed typography, right-side caption lane, event-driven expression and exact text are readable. "
            "Background detail is flexible only when it does not change meaning. Run at most two automatic correction rounds for non-key prop/layout drift; regenerate the whole page for identity, half-side direction, geometry, key fact, limb thickness, expression atom or text failure, then ask one friendly specific question if needed."
        ),
        (
            "STYLE LOCK: original minimalist black-ink diary cartoon on smooth pure-white paper, with reduced detail and a stable slightly wobbly medium-thick line. Use the same 5-6px black stroke for people, animals, props, furniture, architecture, visible accessories (including eyeglass frames, bridge and temples) and background/environment strokes; pale cyan notebook rules are the only exception. "
            "Keep head silhouettes varied but identity-specific (round-ish, pear, soft wedge or rounded trapezoid), two clean circular eye atoms, one low mouth, one clearly visible nose, narrow torsos, 1/32-target ultra-thin parallel limbs with white channels, body-below-head proportion at 90% of the previous card, clear shorts/trouser hems and unchanged oversized flat shoes. "
            "Pets remain flat species silhouettes with complete ears, eyes, mouth, tail and correct single visible nose; ear interiors stay blank and cats have no whisker lines. Use only a few black fills for hair, clothing or mouths. No gray modeling, gradient, lighting, realistic material, paper fibers, noise, speckles, detailed fur, eye highlights or decorative color."
        ),
        (
            "IDENTITY LOCK: preserve every listed head shape, nose direction and opening, separate visible nose, face-contour break, eye spacing and baseline diameter, hair strokes, outer ear shape with blank interior, mouth position, accessory line weight (including eyeglass frames, bridge and temples), black-fill placement, clothing structure, head-to-body ratio, equal 1/32-thin arm/leg tubes, unchanged head/hands/feet canonical size, body-below-head proportion at about 90% of the previous card, shoe/paw shape and animal ear/tail shape in every scene. Expression changes may change the approved eye atom and mouth/body reaction only; they may not change identity geometry."
        ),
        (
            "UPLOAD CONVERSION LOCK: user photos contribute only broad identity cues such as hair silhouette, clothing block, accessory, body impression, pet ears/tail and broad fur color. They must not contribute photographic skin, fur strands, material, lighting, background, realistic anatomy or camera perspective. The approved geometry atlas and face reference override a photo whenever they conflict. Compare each generated character against the atlas before delivery and regenerate if line weight (including eyeglass frames, bridge and temples), half-side direction, nose grammar, contour break, limb thickness, head-to-body ratio or black-white fill placement drifts."
        ),
        (
            "REPAIR POLICY: non-key prop or placement drift may be corrected automatically at most twice. A P0 identity, side-direction, eye atom, nose, face break, limb, key action, count, caption or text failure requires whole-page regeneration rather than local patching. After two failed attempts, ask only one short, friendly, specific clarification; do not make the user complete a long form."
        ),
        "Originality/privacy: use supplied references only for abstract structure, layout or authorized identity. Do not copy a published character, page, logo, signature font, private detail, photographic background, brand or unlisted location.",
        (
            "Avoid: frontal or near-frontal portraits, true side profiles, standard 90-degree正侧面/full profiles, one-eye profiles, straight-at-camera face, elongated/tall heads, generic adult or anime faces, oversized hair hiding the forehead or eyes, missing contour breaks, long forehead/brow lines, missing/hidden human noses, long or downward noses, nose merged with mouth, downturned U/C human noses, solid-black human noses, animal noses on humans, human open noses on animals, inner-ear decoration lines, arbitrary eye shapes, oversized or unequal eyes, thick arm/leg/animal shafts, unequal limb widths, broad or stretched torsos, adult body proportions, shrinking the canonical hands/feet, missing trouser separation, mixed line weights, thick or hairline eyeglass frames/bridge/temples, technical background lines, realism, shading, texture, noise, dense meaningless backgrounds, off-center headers, inconsistent typography, captions outside the right-side lane, repetitive neutral expressions, duplicate clone fillers, copied copyrighted characters, logos, remote assets or signature fonts."
        ),
    ]
    return "\n".join(sections)


def main() -> int:
    args = parse_args()
    try:
        characters, relationships = load_character_graph(args.graph)
        header, title, events, summary = normalize_brief(load_brief(args.brief), characters)
        prompt = build_prompt(header, title, events, summary, characters, relationships)
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
