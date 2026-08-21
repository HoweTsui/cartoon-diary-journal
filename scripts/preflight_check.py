#!/usr/bin/env python3
"""Run lightweight release and task-level checks for the diary Skill."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

from build_diary_prompt import (
    GRAPH_DATA_PATTERN,
    build_prompt,
    load_brief,
    load_character_graph,
    normalize_brief,
)


SKILL_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "VERSION",
    "CHANGELOG.md",
    "agents/openai.yaml",
    "references/character-library.md",
    "references/style-system.md",
    "references/prompt-template.md",
    "references/qa-checklist.md",
    "scripts/build_character_graph.py",
    "scripts/build_diary_prompt.py",
)
PLACEHOLDER_NAMES = ("林芽", "江屿", "桃子", "阿岚", "林杏", "灰豆", "actual-person-")
DATE_PATTERN = re.compile(r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight the diary Skill package or task data.")
    parser.add_argument("--graph", type=Path, help="Optional actual task character graph HTML")
    parser.add_argument("--brief", type=Path, help="Optional diary brief; requires --graph")
    return parser.parse_args()


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"FAIL  {message}")


def check_package(failures: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = SKILL_ROOT / relative
        if path.is_file():
            print(f"PASS  file {relative}")
        else:
            fail(f"missing required file: {relative}", failures)

    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "name:" not in skill_text.split("---\n", 2)[1]:
        fail("SKILL.md frontmatter is incomplete", failures)
    for reference in re.findall(r"`((?:references|scripts)/[^`]+)`", skill_text):
        if not (SKILL_ROOT / reference).exists():
            fail(f"SKILL.md points to missing path: {reference}", failures)

    for path in (SKILL_ROOT / "scripts").glob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            fail(f"Python syntax error in {path.name}: {exc}", failures)
        else:
            print(f"PASS  syntax {path.relative_to(SKILL_ROOT)}")

    for path in (SKILL_ROOT / "assets" / "templates").glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"invalid JSON template {path.name}: {exc}", failures)
        else:
            print(f"PASS  json {path.relative_to(SKILL_ROOT)}")

    for private_path in (
        SKILL_ROOT / "assets" / "character-library" / "character-graph.html",
        SKILL_ROOT / "assets" / "character-library" / "character-lineup.png",
        SKILL_ROOT / "assets" / "templates" / "character-data-aha-ayan-naicheese.json",
    ):
        if private_path.exists():
            print(
                f"WARN  local-only asset exists and is gitignored: "
                f"{private_path.relative_to(SKILL_ROOT)}"
            )


def check_graph(path: Path, failures: list[str]) -> None:
    try:
        characters, relationships = load_character_graph(path)
        html = path.read_text(encoding="utf-8")
        match = GRAPH_DATA_PATTERN.search(html)
        data = json.loads(match.group(1)) if match else {}
        atlas_src = data.get("atlas", {}).get("src")
        atlas_path = path.parent / atlas_src if isinstance(atlas_src, str) else None
        if atlas_path is not None and not atlas_path.is_file():
            fail(f"graph atlas is missing beside HTML: {atlas_path}", failures)
        if DATE_PATTERN.search(html):
            fail("graph contains date-like text; the global graph must not contain dates", failures)
        for placeholder in PLACEHOLDER_NAMES:
            if placeholder in html:
                fail(f"graph still contains placeholder text: {placeholder}", failures)
        print(
            f"PASS  graph actual data ({len(characters)} characters, "
            f"{len(relationships)} relationships)"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(f"graph check failed: {exc}", failures)


def check_brief(graph_path: Path, brief_path: Path, failures: list[str]) -> None:
    try:
        characters, relationships = load_character_graph(graph_path)
        header, title, events, summary = normalize_brief(load_brief(brief_path), characters)
        prompt = build_prompt(header, title, events, summary, characters, relationships)
        if not prompt.strip() or header not in prompt:
            raise ValueError("generated prompt is empty or missing its exact date header")
        print(f"PASS  brief matched ({len(events)} scenes, header {header})")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(f"brief check failed: {exc}", failures)


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    check_package(failures)
    if args.brief and not args.graph:
        fail("--brief requires --graph so characters cannot be resolved from a stale default", failures)
    if args.graph:
        check_graph(args.graph, failures)
    if args.brief and args.graph:
        check_brief(args.graph, args.brief, failures)
    if failures:
        print(f"\n{len(failures)} preflight check(s) failed.")
        return 2
    print("\nPreflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
