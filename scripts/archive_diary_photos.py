#!/usr/bin/env python3
"""Archive originals and create privacy-scoped 2048px JPEG reference copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import datetime
from diary_images import normalized, validate_copy
from PIL import Image
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
    image = normalized(source)
    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    for quality in (85, 95):
        image.save(destination, 'JPEG', quality=quality, subsampling=0, optimize=True)
        try:
            validate_copy(source, destination)
            return f'Pillow-JPEG-{quality}'
        except ValueError:
            if quality == 95:
                raise


def archive(date: str, character_id: str, photos: list[Path], output: Path) -> dict:
    if datetime.date.fromisoformat(date).isoformat() != date:
        raise ValueError('date must be YYYY-MM-DD')
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
        for index, source in enumerate(photos, 1):
            original = unique_path(original_dir, source.stem, source.suffix.lower())
            shutil.copy2(source, original)
            compressed = reference_dir / f'{date}-照片-{index:03d}.jpg'
            tool = compress(original, compressed)
            records.append({
                "order": index,
                "validation": validate_copy(original, compressed),
                "originalPath": original.relative_to(output).as_posix(),
                "compressedPath": compressed.relative_to(output).as_posix(),
                "originalSha256": sha256(original),
                "compressedSha256": sha256(compressed),
                "originalBytes": original.stat().st_size,
                "compressedBytes": compressed.stat().st_size,
                "maxEdge": MAX_EDGE,
                "jpegQuality": int(tool.rsplit('-', 1)[-1]),
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
