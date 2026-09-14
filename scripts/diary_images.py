"""Image normalization and source-relative validation (requires Pillow)."""
try:
    from PIL import Image, ImageChops, ImageOps, ImageStat
except ImportError as exc:
    raise ImportError('Diary image processing requires Pillow: python3 -m pip install Pillow') from exc


def normalized(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGBA')
        background = Image.new('RGBA', image.size, 'white')
        return Image.alpha_composite(background, image).convert('RGB')


def validate_copy(source, destination):
    before, after = normalized(source), normalized(destination)
    if max(after.size) > 2048 or after.width > before.width or after.height > before.height:
        raise ValueError('compressed image was enlarged or exceeds 2048px')
    expected = before.copy()
    expected.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    if after.size != expected.size:
        raise ValueError('compressed image dimensions or orientation changed')
    a, b = expected.resize((64, 64)), after.resize((64, 64))
    error = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
    if error > 18:
        raise ValueError('compressed image differs substantially from source (black/blank/distorted)')
    return {'width': after.width, 'height': after.height, 'meanAbsoluteError': round(error, 3),
            'status': 'passed', 'visualReviewRequired': True}
