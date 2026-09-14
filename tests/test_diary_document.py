import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from PIL import Image
except ImportError:
    raise unittest.SkipTest('diary image tests require Pillow')
from archive_diary_photos import archive
from diary_images import validate_copy
from build_diary_document import build


class DiaryDocumentTests(unittest.TestCase):
    def test_order_dark_transparency_orientation_and_document_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = []
            for i, (size, color) in enumerate([((2500, 1000), 'red'), ((800, 1200), 'green'),
                                               ((400, 300), (3, 3, 3)), ((200, 300), 'blue'), ((300, 200), 'white')]):
                p = root / f'{i}.png'
                im = Image.new('RGB', size, color)
                if i == 3:
                    exif = im.getexif(); exif[274] = 6
                    im.save(p, exif=exif)
                elif i == 4:
                    Image.new('RGBA', size, (0, 0, 0, 0)).save(p)
                else:
                    im.save(p)
                sources.append(p)
            manifest = archive('2026-09-14', 'test', sources, root / 'archive')
            self.assertEqual([p['order'] for p in manifest['photos']], list(range(1, 6)))
            self.assertEqual(manifest['photos'][3]['validation']['width'], 300)
            with Image.open(root / 'archive' / manifest['photos'][4]['compressedPath']) as white:
                self.assertGreater(white.getpixel((0, 0))[0], 250)
            poster = root / 'poster.png'; Image.new('RGB', (1200, 1600), 'white').save(poster)
            data = dict(date='2026-09-14', sourceText='没去跑步。\n并没有开心起来。', body='没去跑步。\n并没有开心起来。',
                        title='下雨的一天', events=[{'caption': '并未开心起来'}], poster='poster.png', photoArchive='archive/archive-manifest.json')
            inp = root / 'input.json'; inp.write_text(json.dumps(data))
            out = root / 'notes'; out.mkdir()
            doc = out / '2026-09-14.md'; doc.write_text('用户已有内容\n')
            build(inp, out); build(inp, out)
            text = doc.read_text()
            self.assertTrue(text.startswith('用户已有内容'))
            self.assertEqual(text.count('## 日记海报'), 1)
            self.assertIn('![', text)
            stored = json.loads((out / 'attachments/2026-09-14/source.json').read_text())
            self.assertEqual(stored['sourceText'], data['sourceText'])
            with Image.open(out / 'attachments/2026-09-14/2026-09-14-照片宫格.jpg') as gallery:
                self.assertEqual(gallery.size, (1864, 1248))

    def test_black_output_rejected_but_dark_original_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.png', Path(tmp) / 'b.png'
            Image.new('RGB', (100, 100), 'white').save(a)
            Image.new('RGB', (100, 100), 'black').save(b)
            with self.assertRaises(ValueError): validate_copy(a, b)
            validate_copy(b, b)


if __name__ == '__main__':
    unittest.main()
