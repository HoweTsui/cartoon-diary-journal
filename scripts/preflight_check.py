#!/usr/bin/env python3
"""Run lightweight release and task-level checks for the diary Skill."""

from __future__ import annotations

import argparse
import ast
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from build_diary_book import load_manifest, normalize_manifest
from build_diary_prompt import (
    GRAPH_DATA_PATTERN,
    build_prompt,
    load_brief,
    load_character_graph,
    validate_brief,
    geometry,
    valid_relative_asset_path,
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
    "references/visual-atoms.md",
    "references/visual-gate.md",
    "references/prompt-template.md",
    "references/qa-checklist.md",
    "references/diary-book-system.md",
    "scripts/build_character_graph.py",
    "scripts/build_diary_book.py",
    "scripts/build_diary_prompt.py",
    "scripts/archive_diary_photos.py",
    "scripts/build_diary_document.py",
    "scripts/diary_images.py",
    "references/diary-document.md",
    "scripts/build_diary_text_layer.py",
    "scripts/check_poster_ink.py",
    "scripts/build_diary_reader.py",
    "references/diary-reader-v3.md",
    "references/geometry.json",
    "assets/diary-reader-v3/source/package.json",
    "assets/diary-reader-v3/source/package-lock.json",
    "assets/diary-reader-v3/runtime/index.html",
    "assets/diary-reader-v3/runtime/THIRD_PARTY_NOTICES.md",
    "assets/diary-reader-v3/runtime/fonts/Yozai-OFL.txt",
    "assets/diary-reader-v3/runtime/fonts/Yozai-Regular.ttf",
    "assets/diary-reader-v3/runtime/fonts/Yozai-Medium.ttf",
    "assets/fonts/yozai/Yozai-Regular.ttf",
    "assets/fonts/yozai/Yozai-Medium.ttf",
    "assets/fonts/yozai/OFL.txt",
    "assets/style-reference/character-graph-demo.html",
    "assets/diary-book/book.css",
    "assets/diary-book/book.js",
    "assets/diary-book/vendor/page-flip.browser.js",
    "assets/diary-book/vendor/STPAGEFLIP-LICENSE",
    "assets/diary-book/demo/character-data.json",
    "assets/diary-book/demo/diary-book-data.json",
    "assets/diary-book/demo/character-graph.html",
    "assets/diary-book/demo/index.html",
    "assets/diary-book/demo/cover-assets/cover-main-3x4.png",
    "assets/diary-book/demo/runtime/book.css",
    "assets/diary-book/demo/runtime/book.js",
    "assets/diary-book/demo/runtime/page-flip.browser.js",
    "assets/diary-book/demo/runtime/NOTICE.md",
    "assets/diary-book/demo/runtime/STPAGEFLIP-LICENSE",
    "assets/templates/diary-book-data.example.json",
    "assets/diary-book/cover-assets/cover-main-3x4.png",
    "assets/style-reference/character-lineup-demo.png",
    "assets/style-reference/face-geometry-closeup.png",
    "assets/style-reference/diary-layout-only.png",
    "assets/style-reference/diary-style-anchor-3x4.png",
    "assets/style-reference/reference-manifest.json",
    "assets/style-reference/approved-human-geometry-v11.png",
    "assets/style-reference/approved-human-expressions-v5.png",
    "assets/style-reference/approved-pet-expressions-v5.png",
    "assets/style-reference/approved-diary-layout-3x4.png",
    "assets/templates/diary-poster-text-layout.json",
)
PLACEHOLDER_NAMES = ("林芽", "江屿", "桃子", "阿岚", "林杏", "灰豆", "actual-person-")
DATE_PATTERN = re.compile(r"\b20\d{2}[./-]\d{1,2}[./-]\d{1,2}\b")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RATIO_TOLERANCE = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight the diary Skill package or task data.")
    parser.add_argument("--graph", type=Path, help="Optional actual task character graph HTML")
    parser.add_argument("--brief", type=Path, help="Schema-v2 authored brief")
    parser.add_argument(
        "--book",
        type=Path,
        help="Optional diary-book manifest beside its output index.html; requires --graph",
    )
    parser.add_argument("--preview", action="store_true")
    return parser.parse_args()


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"FAIL  {message}")


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def svg_dimensions(path: Path) -> tuple[float, float] | None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    view_box = root.get("viewBox", "").replace(",", " ").split()
    if len(view_box) == 4:
        try:
            return float(view_box[2]), float(view_box[3])
        except ValueError:
            return None
    width = root.get("width", "")
    height = root.get("height", "")
    numeric = re.compile(r"^([0-9]+(?:\.[0-9]+)?)(?:px)?$")
    width_match = numeric.fullmatch(width)
    height_match = numeric.fullmatch(height)
    if not width_match or not height_match:
        return None
    return float(width_match.group(1)), float(height_match.group(1))


def image_dimensions(path: Path) -> tuple[float, float] | None:
    if path.suffix.lower() == ".png":
        return png_dimensions(path)
    if path.suffix.lower() == ".svg":
        return svg_dimensions(path)
    return None


def is_ratio(dimensions: tuple[float, float], width: int, height: int, tolerance: float = 0.0) -> bool:
    if dimensions[1] == 0:
        return False
    actual = dimensions[0] / dimensions[1]
    expected = width / height
    return abs(actual - expected) <= tolerance


def classify_poster(path: Path) -> str:
    dimensions = image_dimensions(path)
    if dimensions is None:
        return "unknown"
    if is_ratio(dimensions, 3, 4):
        return "new-3:4"
    if is_ratio(dimensions, 9, 16, RATIO_TOLERANCE):
        return "legacy-9:16"
    return "unsupported"


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def check_package(failures: list[str]) -> None:
    try:
        geometry({})
    except (OSError, ValueError) as exc:
        fail(f"canonical geometry invalid: {exc}", failures)
    for relative in REQUIRED_FILES:
        path = SKILL_ROOT / relative
        if path.is_file():
            print(f"PASS  file {relative}")
        else:
            fail(f"missing required file: {relative}", failures)

    for relative in (
        "assets/diary-book/cover-assets/cover-main-3x4.png",
        "assets/diary-book/demo/cover-assets/cover-main-3x4.png",
        "assets/style-reference/diary-layout-only.png",
        "assets/style-reference/diary-style-anchor-3x4.png",
        "assets/style-reference/approved-diary-layout-3x4.png",
    ):
        path = SKILL_ROOT / relative
        dimensions = image_dimensions(path)
        if dimensions is None or not is_ratio(dimensions, 3, 4):
            fail(f"{relative} must be a readable strict 3:4 asset", failures)
        else:
            print(f"PASS  ratio {relative} ({dimensions[0]}x{dimensions[1]})")

    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "name:" not in skill_text.split("---\n", 2)[1]:
        fail("SKILL.md frontmatter is incomplete", failures)
    for reference in re.findall(r"(?:references|scripts)/[A-Za-z0-9_./-]+\.(?:md|json|py)", skill_text):
        if not (SKILL_ROOT / reference).exists():
            fail(f"SKILL.md points to missing path: {reference}", failures)

    try:
        reference_manifest = json.loads((SKILL_ROOT / "assets/style-reference/reference-manifest.json").read_text(encoding="utf-8"))
        if reference_manifest.get("schemaVersion") != 1 or len(reference_manifest.get("references", [])) < 4:
            raise ValueError("expected four approved references")
        for item in reference_manifest["references"]:
            relative = valid_relative_asset_path(item.get("path"), "reference manifest path")
            if not (SKILL_ROOT / relative).is_file():
                raise ValueError("missing " + relative)
        print("PASS  approved fixed reference pack")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(f"fixed reference pack invalid: {exc}", failures)

    reader_root = SKILL_ROOT / "assets/diary-reader-v3"
    for relative in ("runtime/data", "source/public/data", "source/node_modules"):
        if (reader_root / relative).exists():
            fail(f"reader package must not include local data or dependencies: {relative}", failures)

    css_text = (SKILL_ROOT / "assets" / "diary-book" / "book.css").read_text(encoding="utf-8")
    js_text = (SKILL_ROOT / "assets" / "diary-book" / "book.js").read_text(encoding="utf-8")
    css_guards = (
        "aspect-ratio: 3 / 4",
        "object-fit: contain",
        "--cover-brick",
        ".cover-paper",
        "clip-path: url",
    )
    for guard in css_guards:
        if guard not in css_text:
            fail(f"book.css is missing visual guard: {guard}", failures)
    for guard in ("coverImageSrc", "coverImagePosition", "cover-placeholder", "cover-mask-paper-days-2026"):
        if guard not in js_text:
            fail(f"book.js is missing cover behavior: {guard}", failures)
    if "background-color: var(--ink)" in css_text:
        fail("book.css must not use the ink color as the cover background", failures)
    for font_guard in ('font-family: "Yozai"', 'url("fonts/Yozai-Regular.ttf")'):
        if font_guard not in css_text:
            fail(f"book.css is missing bundled Yozai guard: {font_guard}", failures)
    graph_text = (SKILL_ROOT / "assets/style-reference/character-graph-demo.html").read_text(encoding="utf-8")
    if 'font-family: "Yozai"' not in graph_text or 'url("fonts/Yozai-Regular.ttf")' not in graph_text:
        fail("character graph template must use bundled Yozai", failures)
    public_demo_css = SKILL_ROOT / "assets" / "diary-book" / "demo" / "runtime" / "book.css"
    if public_demo_css.is_file() and "aspect-ratio: 3 / 4" not in public_demo_css.read_text(encoding="utf-8"):
        fail("public Demo runtime CSS is stale and lacks the 3:4 page ratio", failures)
    for relative in (
        "assets/diary-book/book.css",
        "assets/diary-book/book.js",
        "assets/diary-book/demo/index.html",
        "assets/diary-book/demo/runtime/book.css",
        "assets/diary-book/demo/runtime/book.js",
    ):
        text = (SKILL_ROOT / relative).read_text(encoding="utf-8")
        if re.search(r"https?://(?!www\.w3\.org/2000/svg)", text):
            fail(f"{relative} must not reference remote resources", failures)
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
        if atlas_path is not None and not path_is_within(atlas_path, path.parent):
            fail(f"graph atlas must resolve beside HTML: {atlas_path}", failures)
        elif atlas_path is not None and not atlas_path.is_file():
            fail(f"graph atlas is missing beside HTML: {atlas_path}", failures)
        avatar_sources = [node.get("avatarSrc") for node in data.get("nodes", [])]
        present_avatars = []
        for index, source in enumerate(avatar_sources):
            if source is None:
                continue
            try:
                present_avatars.append(
                    valid_relative_asset_path(source, f"graph node {index + 1}.avatarSrc")
                )
            except ValueError as exc:
                fail(str(exc), failures)
        if present_avatars and len(present_avatars) != len(avatar_sources):
            fail("graph avatarSrc must be provided for every node when independent avatars are used", failures)
        if len(set(present_avatars)) != len(present_avatars):
            fail("graph avatarSrc paths must be unique per character", failures)
        if not present_avatars:
            print("WARN  graph uses atlas avatar fallback; migrate nodes to independent 1:1 avatarSrc files")
        for source in present_avatars:
            avatar_path = path.parent / source
            if not path_is_within(avatar_path, path.parent):
                fail(f"graph independent avatar must resolve beside HTML: {avatar_path}", failures)
                continue
            if not avatar_path.is_file():
                fail(f"graph independent avatar is missing beside HTML: {avatar_path}", failures)
                continue
            dimensions = image_dimensions(avatar_path)
            if dimensions is None:
                fail(f"graph independent avatar must be a readable PNG or SVG: {avatar_path}", failures)
            elif dimensions[0] != dimensions[1]:
                fail(
                    f"graph independent avatar must be square (1:1): {avatar_path} "
                    f"is {dimensions[0]}x{dimensions[1]}",
                    failures,
                )
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


def check_brief(graph_path, brief_path, failures, preview=False):
    try:
        brief = validate_brief(load_brief(brief_path), brief_path.parent, preview, graph_path)
        if not build_prompt(brief).strip():
            raise ValueError("empty prompt")
        print(f"PASS  structured brief ({brief['kind']}, {brief['role']})")
    except (OSError, ValueError) as exc:
        fail(f"brief check failed: {exc}", failures)


def check_book(
    graph_path: Path,
    book_path: Path,
    failures: list[str],
    *,
    require_new_poster: bool = False,
) -> None:
    try:
        book_data = normalize_manifest(
            load_manifest(book_path), graph_path, book_path.parent / "index.html"
        )
        cover_image = book_data["book"].get("coverImageSrc")
        if cover_image:
            cover_path = book_path.parent / cover_image
            dimensions = image_dimensions(cover_path)
            if dimensions is None or not is_ratio(dimensions, 3, 4):
                fail(
                    f"coverImageSrc must be a strict 3:4 image: {cover_path}",
                    failures,
                )
        poster_kinds: set[str] = set()
        for entry in book_data["entries"]:
            poster_path = book_path.parent / entry["posterSrc"]
            kind = classify_poster(poster_path)
            poster_kinds.add(kind)
            if kind == "unknown":
                fail(f"poster must be a readable PNG or SVG: {poster_path}", failures)
            elif kind == "unsupported":
                fail(
                    f"poster must be strict 3:4 or legacy 9:16: {poster_path}",
                    failures,
                )
        if require_new_poster and "new-3:4" not in poster_kinds:
            fail("public Demo must contain at least one strict 3:4 diary poster", failures)
        print(
            f"PASS  diary book ({len(book_data['periods'])} periods, "
            f"{len(book_data['entries'])} entries, {len(book_data['characters'])} characters; "
            f"poster types: {', '.join(sorted(poster_kinds))})"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(f"diary-book check failed: {exc}", failures)


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    check_package(failures)
    if args.book and not args.graph:
        fail("--book requires --graph so characters and avatars cannot be resolved from a stale default", failures)
    if args.graph:
        check_graph(args.graph, failures)
    if args.brief:
        check_brief(args.graph, args.brief, failures, args.preview)
    if args.book and args.graph:
        check_book(args.graph, args.book, failures)
    check_book(
        SKILL_ROOT / "assets" / "diary-book" / "demo" / "character-graph.html",
        SKILL_ROOT / "assets" / "diary-book" / "demo" / "diary-book-data.json",
        failures,
        require_new_poster=True,
    )
    if failures:
        print(f"\n{len(failures)} preflight check(s) failed.")
        return 2
    print("\nPreflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
