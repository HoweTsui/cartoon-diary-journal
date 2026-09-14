#!/usr/bin/env python3
"""Check black-ink coverage in a non-interlaced 8-bit RGB/RGBA PNG poster."""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path


PNG = b"\x89PNG\r\n\x1a\n"


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    # PNG specifies a, then b, then c priority for equal distances.
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    raw = path.read_bytes()
    if not raw.startswith(PNG):
        raise ValueError("poster check only accepts PNG")
    pos, chunks, width, height, color_type, bit_depth, interlace = 8, [], None, None, None, None, None
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        value = raw[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", value)
        elif kind == b"IDAT":
            chunks.append(value)
        elif kind == b"IEND":
            break
    if not width or not height or bit_depth != 8 or color_type not in {2, 6} or interlace:
        raise ValueError("PNG must be 8-bit non-interlaced RGB or RGBA")
    bpp = 3 if color_type == 2 else 4
    rows, data, offset, previous = [], zlib.decompress(b"".join(chunks)), 0, bytearray(width * bpp)
    for _ in range(height):
        filter_type, encoded = data[offset], bytearray(data[offset + 1:offset + 1 + width * bpp])
        offset += 1 + width * bpp
        for i, value in enumerate(encoded):
            left = encoded[i - bpp] if i >= bpp else 0
            up = previous[i]
            up_left = previous[i - bpp] if i >= bpp else 0
            if filter_type == 1:
                encoded[i] = (value + left) & 255
            elif filter_type == 2:
                encoded[i] = (value + up) & 255
            elif filter_type == 3:
                encoded[i] = (value + ((left + up) // 2)) & 255
            elif filter_type == 4:
                encoded[i] = (value + paeth(left, up, up_left)) & 255
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter")
        rows.append(encoded)
        previous = encoded
    pixels = []
    for row in rows:
        for x in range(0, len(row), bpp):
            r, g, b = row[x], row[x + 1], row[x + 2]
            alpha = row[x + 3] if bpp == 4 else 255
            # Composite transparency on the required white page before classification.
            pixels.append(tuple((channel * alpha + 255 * (255 - alpha)) // 255 for channel in (r, g, b)) + (255,))
    return width, height, pixels


def inspect(path: Path, target: float, maximum: float) -> dict:
    width, height, pixels = decode_png(path)
    black = sum(1 for r, g, b, _ in pixels if max(r, g, b) <= 70)
    # Ignore antialiased black edge pixels. Count only decorative saturated pixels; cyan is allowed only as rules.
    saturated_other = sum(
        1
        for r, g, b, _ in pixels
        # Near-white compression noise and dark antialiased ink still render as white/black,
        # not decorative color. Inspect only visibly midtone saturated pixels.
        if 90 < max(r, g, b) < 230
        and max(r, g, b) - min(r, g, b) > 28
        and not (b >= r + 12 and g >= r + 12)
    )
    ratio = black / len(pixels)
    return {"width": width, "height": height, "blackRatio": ratio, "target": target, "maximum": maximum, "nonCyanColorRatio": saturated_other / len(pixels)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("poster", type=Path)
    parser.add_argument("--target", type=float, default=.20)
    parser.add_argument("--maximum", type=float, default=.30)
    args = parser.parse_args()
    try:
        report = inspect(args.poster, args.target, args.maximum)
    except (OSError, ValueError, zlib.error) as exc:
        print("Ink check failed: " + str(exc), file=sys.stderr)
        return 2
    print("blackRatio={blackRatio:.2%}; target<={target:.0%}; hardLimit<={maximum:.0%}; nonCyanColorRatio={nonCyanColorRatio:.2%}".format(**report))
    if report["blackRatio"] > args.maximum:
        print("FAIL black ink exceeds the hard limit", file=sys.stderr)
        return 2
    if report["nonCyanColorRatio"] > .002:
        print("FAIL decorative color outside black/white/cyan rule lines", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
