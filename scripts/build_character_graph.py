#!/usr/bin/env python3
"""Build a task-specific character graph by replacing the template data block."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = (
    SKILL_ROOT / "assets" / "character-library" / "character-graph.html"
)
GRAPH_DATA_PATTERN = re.compile(
    r'(<script\s+id="graph-data"\s+type="application/json">\s*)'
    r"(.*?)"
    r"(\s*</script>)",
    re.DOTALL,
)
ALLOWED_TYPES = {"friend", "partner", "family", "work", "care"}
PLACEHOLDER_MARKERS = ("actual-person-", "实际人物", "实际关系", "占位")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace every placeholder person and relationship in the graph."
    )
    parser.add_argument("data", type=Path, help="Task-specific graph data JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output HTML path")
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Graph HTML template; defaults to the Skill asset",
    )
    return parser.parse_args()


def require_text(value: object, path: str, maximum: int = 120) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{path} must be at most {maximum} characters")
    return result


def require_string_list(value: object, path: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"{path} must contain at least {minimum} items")
    return [require_text(item, f"{path}[{index}]") for index, item in enumerate(value)]


def load_data(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"data file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("graph data root must be an object")
    return data


def normalize_data(data: dict) -> dict:
    atlas = data.get("atlas")
    if not isinstance(atlas, dict):
        raise ValueError("atlas must be an object")
    atlas_src = require_text(atlas.get("src"), "atlas.src")
    if "://" in atlas_src or atlas_src.startswith(("/", "..")):
        raise ValueError("atlas.src must be a relative local asset path")
    cols = atlas.get("cols")
    rows = atlas.get("rows")
    if not isinstance(cols, int) or cols < 1 or not isinstance(rows, int) or rows < 1:
        raise ValueError("atlas.cols and atlas.rows must be positive integers")

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("nodes must contain at least one actual character")
    nodes: list[dict] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise ValueError(f"nodes[{index}] must be an object")
        node_id = require_text(raw.get("id"), f"nodes[{index}].id", 64)
        if node_id in ids:
            raise ValueError(f"duplicate node id: {node_id}")
        ids.add(node_id)
        raw_text = json.dumps(raw, ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            if marker in raw_text:
                raise ValueError(
                    f"nodes[{index}] still contains placeholder text: {marker}"
                )
        col = raw.get("col")
        row = raw.get("row")
        if not isinstance(col, int) or not 0 <= col < cols:
            raise ValueError(f"nodes[{index}].col is outside the atlas")
        if not isinstance(row, int) or not 0 <= row < rows:
            raise ValueError(f"nodes[{index}].row is outside the atlas")
        x = raw.get("x", 0)
        y = raw.get("y", 0)
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"nodes[{index}] x and y must be numbers")
        node = {
            "id": node_id,
            "name": require_text(raw.get("name"), f"nodes[{index}].name", 20),
            "role": require_text(raw.get("role"), f"nodes[{index}].role", 80),
            "col": col,
            "row": row,
            "x": x,
            "y": y,
            "anchors": require_string_list(
                raw.get("anchors"), f"nodes[{index}].anchors", minimum=4
            ),
            "notes": require_string_list(raw.get("notes", []), f"nodes[{index}].notes"),
        }
        for optional_key in ("kind", "species"):
            if optional_key in raw:
                node[optional_key] = require_text(
                    raw[optional_key], f"nodes[{index}].{optional_key}", 32
                )
        if "avatarFocusX" in raw:
            focus_x = raw["avatarFocusX"]
            if not isinstance(focus_x, (int, float)) or not 0 <= focus_x <= 1:
                raise ValueError(
                    f"nodes[{index}].avatarFocusX must be a number between 0 and 1"
                )
            node["avatarFocusX"] = focus_x
        nodes.append(node)

    raw_edges = data.get("edges")
    if not isinstance(raw_edges, list):
        raise ValueError("edges must be a list")
    edges: list[dict] = []
    pairs: set[frozenset[str]] = set()
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise ValueError(f"edges[{index}] must be an object")
        source = require_text(raw.get("source"), f"edges[{index}].source", 64)
        target = require_text(raw.get("target"), f"edges[{index}].target", 64)
        if source not in ids or target not in ids:
            raise ValueError(f"edges[{index}] references an unknown character")
        if source == target:
            raise ValueError(f"edges[{index}] cannot connect a character to itself")
        pair = frozenset((source, target))
        if pair in pairs:
            raise ValueError(f"edges[{index}] duplicates an existing relationship")
        pairs.add(pair)
        relation_type = require_text(raw.get("type"), f"edges[{index}].type", 20)
        if relation_type not in ALLOWED_TYPES:
            raise ValueError(
                f"edges[{index}].type must be one of: {', '.join(sorted(ALLOWED_TYPES))}"
            )
        curve = raw.get("curve", ((index % 5) - 2) * 12)
        if not isinstance(curve, (int, float)):
            raise ValueError(f"edges[{index}].curve must be a number")
        edges.append(
            {
                "source": source,
                "target": target,
                "label": require_text(raw.get("label"), f"edges[{index}].label", 12),
                "type": relation_type,
                "curve": curve,
            }
        )
        for marker in PLACEHOLDER_MARKERS:
            if marker in json.dumps(raw, ensure_ascii=False):
                raise ValueError(
                    f"edges[{index}] still contains placeholder text: {marker}"
                )

    return {
        "status": "actual",
        "atlas": {"src": atlas_src, "cols": cols, "rows": rows},
        "nodes": nodes,
        "edges": edges,
    }


def render_graph(template: str, data: dict) -> str:
    serialized = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    result, replacements = GRAPH_DATA_PATTERN.subn(
        lambda match: match.group(1) + serialized + match.group(3), template, count=1
    )
    if replacements != 1:
        raise ValueError("template must contain exactly one graph-data block")
    embedded = GRAPH_DATA_PATTERN.search(result)
    if not embedded or json.loads(embedded.group(2)) != data:
        raise ValueError("output graph data does not exactly match the task data")
    return result


def main() -> int:
    args = parse_args()
    try:
        data = normalize_data(load_data(args.data))
        template = args.template.read_text(encoding="utf-8")
        result = render_graph(template, data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"built {args.output} with {len(data['nodes'])} people and "
        f"{len(data['edges'])} relationships"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
