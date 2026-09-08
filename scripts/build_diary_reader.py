#!/usr/bin/env python3
"""Export the bundled reader from a legacy diary-book HTML, without changing it."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

RUNTIME = Path(__file__).resolve().parents[1] / "assets/diary-reader-v3/runtime"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif"}


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class EmbeddedData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.count = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script" and dict(attrs).get("id") == "diary-book-data":
            self.count += 1
            self.active = True

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self.active = False

    def handle_data(self, text):
        if self.active:
            self.parts.append(text)


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def read_manifest(index):
    parser = EmbeddedData()
    parser.feed(index.read_text(encoding="utf-8"))
    if parser.count != 1:
        raise ValueError("Expected exactly one script#diary-book-data")
    data = json.loads("".join(parser.parts))
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("Expected diary-book schemaVersion 1")
    book = data.get("book")
    if not isinstance(book, dict):
        raise ValueError("Missing book object")
    for key in ("id", "title"):
        required_text(book.get(key), f"book.{key}")
    required_text(book.get("coverImageSrc") or book.get("coverSrc"), "book cover")
    for name in ("periods", "entries", "characters", "relationships"):
        data.setdefault(name, [])
        if not isinstance(data[name], list):
            raise ValueError(f"{name} must be a list")
    if not data["entries"]:
        raise ValueError("At least one entry is required")
    ids = {}
    for name in ("periods", "entries", "characters"):
        ids[name] = set()
        for item in data[name]:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid {name} item")
            identity = required_text(item.get("id"), f"{name}.id")
            if identity in ids[name]:
                raise ValueError(f"Duplicate {name} id: {identity}")
            ids[name].add(identity)
    for entry in data["entries"]:
        for key in ("title", "date", "posterSrc"):
            required_text(entry.get(key), f"entry.{key}")
        date.fromisoformat(entry["date"])
        if entry.get("periodId") not in ids["periods"]:
            raise ValueError(f"Unknown period for entry {entry['id']}")
        entry.setdefault("characterIds", [])
        if not isinstance(entry["characterIds"], list) or any(
            not isinstance(x, str) or x not in ids["characters"] for x in entry["characterIds"]
        ):
            raise ValueError(f"Unknown character for entry {entry['id']}")
    return data


def local_asset(root, value):
    required_text(value, "asset path")
    decoded = unquote(value)
    parsed = urlsplit(decoded)
    path = PurePosixPath(decoded)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or path.is_absolute() or ".." in path.parts or "\\" in decoded
            or any(ord(c) < 32 for c in decoded)):
        raise ValueError(f"Unsafe asset path: {value}")
    candidate = (root / path).resolve()
    if not inside(candidate, root):
        raise ValueError(f"Asset escapes source directory: {value}")
    if not candidate.is_file():
        raise ValueError(f"Missing asset: {value}")
    if candidate.suffix.lower() not in IMAGE_TYPES:
        raise ValueError(f"Not an image asset: {value}")
    return candidate, path


def collect_assets(data, root):
    """Rewrite only Src fields, preserving other schema data and original bytes."""
    result = copy.deepcopy(data)
    files = {}

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("Src") and item:
                    source, relative = local_asset(root, item)
                    files[relative.as_posix()] = source
                    value[key] = quote(relative.as_posix(), safe="/")
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(result)
    return result, files


def export_reader(index, output_dir):
    index = Path(index).resolve(strict=True)
    if not index.is_file():
        raise ValueError("Input must be an existing legacy index.html")
    root = index.parent
    output = Path(output_dir).resolve()
    if "task-output" not in output.parts or output.name == "task-output":
        raise ValueError("Output must be a new directory below task-output/")
    if output.exists():
        raise ValueError("Output already exists; choose a new directory")
    if inside(output, root) or inside(root, output):
        raise ValueError("Output must be separate from the source directory")
    data, assets = collect_assets(read_manifest(index), root)
    if not (RUNTIME / "index.html").is_file():
        raise ValueError("Bundled runtime missing; rebuild source first")
    if (RUNTIME / "data").exists():
        raise ValueError("Runtime must not contain fixture data")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stage only after every input reference has passed validation.
    with tempfile.TemporaryDirectory(prefix=".reader-export-", dir=output.parent) as temp:
        stage = Path(temp) / "reader"
        shutil.copytree(RUNTIME, stage)
        for relative, source in assets.items():
            destination = stage / "data" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (stage / "data").mkdir(exist_ok=True)
        (stage / "data/manifest.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # Reserve the final directory exclusively; never merge with an existing export.
        output.mkdir(exist_ok=False)
        try:
            for item in stage.iterdir():
                shutil.move(str(item), output / item.name)
        except Exception:
            shutil.rmtree(output)
            raise
    return {"output": str(output), "entries": len(data["entries"]), "assets": len(assets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index_html", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = export_reader(args.index_html, args.output_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Reader export failed: {exc}\n")
    print(json.dumps(report, ensure_ascii=False))
    print("Serve with: python3 -m http.server 8000 --directory " + repr(report["output"]))


if __name__ == "__main__":
    main()
