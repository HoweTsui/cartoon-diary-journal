#!/usr/bin/env python3
"""Build a private, offline page-flip diary book from posters and a character graph."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from urllib.parse import unquote
from pathlib import Path

from build_diary_prompt import load_character_graph, valid_relative_asset_path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = SKILL_ROOT / "assets" / "diary-book"
RUNTIME_FILES = (
    (RUNTIME_ROOT / "book.css", "runtime/book.css"),
    (RUNTIME_ROOT / "book.js", "runtime/book.js"),
    (RUNTIME_ROOT / "NOTICE.md", "runtime/NOTICE.md"),
    (RUNTIME_ROOT / "vendor" / "page-flip.browser.js", "runtime/page-flip.browser.js"),
    (RUNTIME_ROOT / "vendor" / "STPAGEFLIP-LICENSE", "runtime/STPAGEFLIP-LICENSE"),
)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
COVER_THEMES = {
    "brick": "brick",
    "terracotta": "terracotta",
    "forest": "forest",
    "blue": "blue",
}
COVER_POSITION_PATTERN = re.compile(
    r"^(?:0|[1-9]\d?|100)%\s+(?:0|[1-9]\d?|100)%$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local StPageFlip diary book from a manifest and actual graph."
    )
    parser.add_argument("manifest", type=Path, help="Private diary-book JSON manifest")
    parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Actual character-graph.html placed beside the output index.html",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output index.html path for the generated offline diary book",
    )
    parser.add_argument(
        "--public-demo",
        action="store_true",
        help="Allow only the tracked fictional demo directory as an output location",
    )
    return parser.parse_args()


def require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    return result


def optional_text(value: object, label: str, maximum: int, default: str = "") -> str:
    if value is None or value == "":
        return default
    return require_text(value, label, maximum)


def cover_position(value: object, label: str) -> str:
    if value is None or value == "":
        return "50% 50%"
    result = require_text(value, label, 20)
    if not COVER_POSITION_PATTERN.fullmatch(result):
        raise ValueError(f"{label} must use two percentage values between 0% and 100%")
    return result


def cover_theme(value: object, label: str) -> str:
    if value is None or value == "":
        return "brick"
    result = require_text(value, label, 20).lower()
    if result not in COVER_THEMES:
        raise ValueError(f"{label} must be one of: {', '.join(sorted(COVER_THEMES))}")
    return COVER_THEMES[result]


def require_id(value: object, label: str) -> str:
    result = require_text(value, label, 64)
    if not ID_PATTERN.fullmatch(result):
        raise ValueError(f"{label} must use letters, digits, dot, underscore, or hyphen")
    return result


def require_date(value: object, label: str) -> dt.date:
    text = require_text(value, label, 10)
    try:
        return dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def require_string_list(value: object, label: str, maximum_items: int, maximum_text: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ValueError(f"{label} must be a list with at most {maximum_items} items")
    return [require_text(item, f"{label}[{index}]", maximum_text) for index, item in enumerate(value)]


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"book manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid book JSON at line {exc.lineno}: {exc.msg}") from exc
    return require_object(data, "book manifest root")


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_safe_relative_asset(value: object, label: str) -> str:
    source = valid_relative_asset_path(value, label)
    decoded = unquote(source).replace("\\", "/")
    if (
        "\x00" in decoded
        or decoded.startswith("/")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", decoded)
        or any(part == ".." for part in decoded.split("/"))
    ):
        raise ValueError(f"{label} must be a relative local asset path")
    return source


def require_asset(
    value: object,
    label: str,
    output_dir: Path,
    *,
    optional: bool = False,
) -> str | None:
    if value is None and optional:
        return None
    source = require_safe_relative_asset(value, label)
    path = output_dir / source
    if not path_is_within(path, output_dir):
        raise ValueError(f"{label} must resolve inside the output directory")
    if not path.is_file():
        raise ValueError(f"{label} is missing beside output: {path}")
    return source


def validate_output_location(output: Path, public_demo: bool) -> None:
    task_output = SKILL_ROOT / "task-output"
    public_demo_root = SKILL_ROOT / "assets" / "diary-book" / "demo"
    if public_demo:
        if not path_is_within(output, public_demo_root):
            raise ValueError(
                "--public-demo output must stay inside assets/diary-book/demo"
            )
        return
    if not path_is_within(output, task_output):
        raise ValueError(
            "private diary-book output must stay under task-output/; "
            "use --public-demo only for the tracked fictional demo"
        )


def normalize_manifest(data: dict, graph_path: Path, output_path: Path) -> dict:
    schema_version = data.get("schemaVersion")
    if schema_version != 1:
        raise ValueError("schemaVersion must equal 1")

    output_dir = output_path.parent.resolve()
    book = require_object(data.get("book"), "book")
    graph_href = require_safe_relative_asset(book.get("graphHref"), "book.graphHref")
    expected_graph = (output_dir / graph_href).resolve()
    if not path_is_within(expected_graph, output_dir):
        raise ValueError("book.graphHref must resolve inside the output directory")
    if graph_path.resolve() != expected_graph:
        raise ValueError(
            "book.graphHref must point to the --graph file beside the output index.html"
        )
    book_id = require_id(book.get("id"), "book.id")
    book_title = require_text(book.get("title"), "book.title", 80)
    book_subtitle = (
        require_text(book.get("subtitle", ""), "book.subtitle", 160)
        if book.get("subtitle", "")
        else ""
    )
    normalized_book = {
        "id": book_id,
        "title": book_title,
        "subtitle": book_subtitle,
        "coverSrc": require_asset(
            book.get("coverSrc"), "book.coverSrc", output_dir, optional=True
        ),
        "graphHref": graph_href,
        "coverImageSrc": require_asset(
            book.get("coverImageSrc"), "book.coverImageSrc", output_dir, optional=True
        ),
        "coverImageAlt": optional_text(
            book.get("coverImageAlt"),
            "book.coverImageAlt",
            160,
            f"{book_title}封面主视觉",
        ),
        "coverImagePosition": cover_position(
            book.get("coverImagePosition"), "book.coverImagePosition"
        ),
        "coverEyebrow": optional_text(
            book.get("coverEyebrow"), "book.coverEyebrow", 80, "OFFLINE DIARY"
        ),
        "coverTitle": optional_text(
            book.get("coverTitle"), "book.coverTitle", 80, book_title
        ),
        "coverSubtitle": optional_text(
            book.get("coverSubtitle"), "book.coverSubtitle", 160, book_subtitle
        ),
        "coverTheme": cover_theme(book.get("coverTheme"), "book.coverTheme"),
    }

    raw_periods = data.get("periods")
    if not isinstance(raw_periods, list) or not raw_periods:
        raise ValueError("periods must contain at least one period")
    periods: list[dict] = []
    period_by_id: dict[str, dict] = {}
    for index, raw in enumerate(raw_periods):
        period = require_object(raw, f"periods[{index}]")
        period_id = require_id(period.get("id"), f"periods[{index}].id")
        if period_id in period_by_id:
            raise ValueError(f"duplicate period id: {period_id}")
        start_date = require_date(period.get("startDate"), f"periods[{index}].startDate")
        end_date = require_date(period.get("endDate"), f"periods[{index}].endDate")
        if start_date > end_date:
            raise ValueError(f"periods[{index}] startDate must not be after endDate")
        normalized = {
            "id": period_id,
            "title": require_text(period.get("title"), f"periods[{index}].title", 80),
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "summary": require_text(
                period.get("summary", ""), f"periods[{index}].summary", 180
            )
            if period.get("summary", "")
            else "",
            "coverSrc": require_asset(
                period.get("coverSrc"), f"periods[{index}].coverSrc", output_dir, optional=True
            ),
        }
        periods.append(normalized)
        period_by_id[period_id] = normalized

    for previous, current in zip(periods, periods[1:]):
        previous_start = dt.date.fromisoformat(previous["startDate"])
        previous_end = dt.date.fromisoformat(previous["endDate"])
        current_start = dt.date.fromisoformat(current["startDate"])
        if current_start < previous_start:
            raise ValueError("periods must be listed in chronological order")
        if current_start <= previous_end:
            raise ValueError(
                f"periods {previous['id']} and {current['id']} overlap; periods must be chronological"
            )

    characters, relationships = load_character_graph(graph_path)
    missing_avatars = [
        character.get("name", character_id)
        for character_id, character in characters.items()
        if not isinstance(character.get("avatarSrc"), str) or not character["avatarSrc"].strip()
    ]
    if missing_avatars:
        raise ValueError(
            "diary-book mode requires a unique 1:1 avatarSrc for every graph character: "
            + ", ".join(missing_avatars)
        )
    for character in characters.values():
        avatar_path = graph_path.parent / character["avatarSrc"]
        if not path_is_within(avatar_path, output_dir):
            raise ValueError(
                "graph avatarSrc must resolve inside the output directory: "
                + character.get("name", character.get("id", "unknown"))
            )

    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("entries must contain at least one diary entry")
    entries: list[dict] = []
    entry_ids: set[str] = set()
    entry_dates: set[dt.date] = set()
    for index, raw in enumerate(raw_entries):
        entry = require_object(raw, f"entries[{index}]")
        entry_id = require_id(entry.get("id"), f"entries[{index}].id")
        if entry_id in entry_ids:
            raise ValueError(f"duplicate entry id: {entry_id}")
        entry_ids.add(entry_id)
        date = require_date(entry.get("date"), f"entries[{index}].date")
        if date in entry_dates:
            raise ValueError(f"duplicate entry date: {date.isoformat()}")
        entry_dates.add(date)
        period_id = require_id(entry.get("periodId"), f"entries[{index}].periodId")
        period = period_by_id.get(period_id)
        if not period:
            raise ValueError(f"entries[{index}] references unknown period: {period_id}")
        if not (
            dt.date.fromisoformat(period["startDate"])
            <= date
            <= dt.date.fromisoformat(period["endDate"])
        ):
            raise ValueError(
                f"entries[{index}].date is outside period {period_id}'s date range"
            )
        character_ids = require_string_list(
            entry.get("characterIds", []), f"entries[{index}].characterIds", 20, 64
        )
        if len(set(character_ids)) != len(character_ids):
            raise ValueError(f"entries[{index}].characterIds contains duplicates")
        unknown_characters = [item for item in character_ids if item not in characters]
        if unknown_characters:
            raise ValueError(
                f"entries[{index}] references unknown graph character(s): "
                + ", ".join(unknown_characters)
            )
        entries.append(
            {
                "id": entry_id,
                "date": date.isoformat(),
                "periodId": period_id,
                "title": require_text(entry.get("title"), f"entries[{index}].title", 100),
                "posterSrc": require_asset(
                    entry.get("posterSrc"), f"entries[{index}].posterSrc", output_dir
                ),
                "summary": require_text(
                    entry.get("summary"), f"entries[{index}].summary", 220
                ),
                "characterIds": character_ids,
                "tags": require_string_list(entry.get("tags", []), f"entries[{index}].tags", 16, 30),
            }
        )
    entries.sort(key=lambda entry: (entry["date"], entry["id"]))

    ordered_characters = [characters[character_id] for character_id in sorted(characters)]
    return {
        "schemaVersion": 1,
        "book": normalized_book,
        "periods": periods,
        "entries": entries,
        "characters": ordered_characters,
        "relationships": relationships,
    }


def render_html(book_data: dict) -> str:
    serialized = json.dumps(book_data, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"color-scheme\" content=\"light\">
  <title>{html.escape(book_data['book']['title'], quote=True)}｜日记本</title>
  <link rel=\"stylesheet\" href=\"runtime/book.css\">
</head>
<body>
  <main class=\"book-shell\" aria-label=\"可翻页日记本\">
    <header class=\"book-toolbar\">
      <div class=\"book-identity\">
        <p class=\"book-kicker\">离线日记本</p>
        <h1 id=\"book-title\"></h1>
      </div>
      <nav class=\"book-nav\" aria-label=\"日记本导航\">
        <button class=\"nav-button is-active\" type=\"button\" data-panel=\"reader\">翻页阅读</button>
        <button class=\"nav-button\" type=\"button\" data-panel=\"timeline\">时间索引</button>
        <button class=\"nav-button\" type=\"button\" data-panel=\"characters\">人物介绍</button>
      </nav>
    </header>

    <section class=\"book-workspace\">
      <aside class=\"side-panel timeline-panel\" id=\"timeline-panel\" hidden>
        <div class=\"panel-heading\">
          <p class=\"book-kicker\">快速定位</p>
          <h2>时间索引</h2>
        </div>
        <label class=\"search-field\">
          <span class=\"sr-only\">搜索日记</span>
          <input id=\"entry-search\" type=\"search\" placeholder=\"搜索日期、标题、标签或人物\" autocomplete=\"off\">
        </label>
        <div id=\"timeline-results\" class=\"timeline-results\"></div>
      </aside>

      <section class=\"reader-panel\" id=\"reader-panel\">
        <div class=\"book-stage\" id=\"book-stage\">
          <div id=\"book-pages\" aria-live=\"polite\"></div>
        </div>
        <div class=\"reader-controls\" aria-label=\"翻页控制\">
          <button id=\"previous-page\" class=\"control-button\" type=\"button\">上一页</button>
          <p id=\"page-status\" class=\"page-status\"></p>
          <button id=\"next-page\" class=\"control-button\" type=\"button\">下一页</button>
        </div>
      </section>

      <aside class=\"side-panel characters-panel\" id=\"characters-panel\" hidden>
        <div class=\"panel-heading\">
          <p class=\"book-kicker\">全局角色</p>
          <h2>人物介绍</h2>
        </div>
        <div id=\"character-results\" class=\"character-results\"></div>
      </aside>
    </section>
  </main>

  <script id=\"diary-book-data\" type=\"application/json\">{serialized}</script>
  <script src=\"runtime/page-flip.browser.js\"></script>
  <script src=\"runtime/book.js\"></script>
</body>
</html>
"""


def copy_runtime(output_dir: Path) -> None:
    for source, destination in RUNTIME_FILES:
        if not source.is_file():
            raise ValueError(f"missing diary-book runtime asset: {source}")
        target = output_dir / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
        output = args.output.resolve()
        graph = args.graph.resolve()
        validate_output_location(output, args.public_demo)
        book_data = normalize_manifest(manifest, graph, output)
        output.parent.mkdir(parents=True, exist_ok=True)
        copy_runtime(output.parent)
        output.write_text(render_html(book_data), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"built {output} with {len(book_data['periods'])} periods, "
        f"{len(book_data['entries'])} entries, and {len(book_data['characters'])} characters"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
