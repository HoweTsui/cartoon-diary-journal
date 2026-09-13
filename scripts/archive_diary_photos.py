#!/usr/bin/env python3
"""Archive originals and create privacy-scoped 2048px JPEG reference copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


MAX_EDGE = 2048
JPEG_QUALITY = "85"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    number = 2
    while candidate.exists():
        candidate = folder / f"{stem}-{number}{suffix}"
        number += 1
    return candidate


def compress(source: Path, destination: Path) -> str:
    if shutil.which("sips"):
        subprocess.run(
            ["sips", "-Z", str(MAX_EDGE), "-s", "format", "jpeg", "-s", "formatOptions", JPEG_QUALITY, str(source), "--out", str(destination)],
            check=True, capture_output=True, text=True,
        )
        return "sips"
    if shutil.which("magick"):
        subprocess.run(
            ["magick", str(source), "-resize", f"{MAX_EDGE}x{MAX_EDGE}>", "-quality", JPEG_QUALITY, str(destination)],
            check=True, capture_output=True, text=True,
        )
        return "ImageMagick"
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Photo compression needs macOS sips, ImageMagick, or Pillow") from exc
    with Image.open(source) as image:
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        image.convert("RGB").save(destination, "JPEG", quality=int(JPEG_QUALITY), optimize=True)
    return "Pillow"


def archive(date: str, character_id: str, photos: list[Path], output: Path) -> dict:
    if output.exists():
        raise ValueError("archive output directory already exists; do not overwrite a photo archive")
    if not photos:
        raise ValueError("at least one photo is required")
    for source in photos:
        if not source.is_file():
            raise ValueError("photo is missing: " + str(source))
    original_dir, reference_dir = output / "original", output / "reference"
    original_dir.mkdir(parents=True)
    reference_dir.mkdir()
    records = []
    try:
        for source in photos:
            original = unique_path(original_dir, source.stem, source.suffix.lower())
            shutil.copy2(source, original)
            compressed = unique_path(reference_dir, source.stem, ".jpg")
            tool = compress(original, compressed)
            records.append({
                "originalPath": original.relative_to(output).as_posix(),
                "compressedPath": compressed.relative_to(output).as_posix(),
                "originalSha256": sha256(original),
                "compressedSha256": sha256(compressed),
                "originalBytes": original.stat().st_size,
                "compressedBytes": compressed.stat().st_size,
                "maxEdge": MAX_EDGE,
                "jpegQuality": int(JPEG_QUALITY),
                "compressor": tool,
            })
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    manifest = {
        "schemaVersion": 1,
        "date": date,
        "characterId": character_id,
        "photos": records,
    }
    (output / "archive-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--date", required=True, help="Diary date in YYYY-MM-DD")
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = archive(args.date, args.character_id, args.photos, args.output_dir)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print("Photo archive failed: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
