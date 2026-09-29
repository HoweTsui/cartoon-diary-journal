"""Behavioral checks for deterministic isolated-scene assembly."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_diary_template import (build_scenes, compose, content_box,
                                  extract_rows, paper, scene_boxes, diary_header)
from build_diary_text_layer import text_lines, FONT_DIR, render_png
from PIL import ImageFont


def cutout(size=(100, 100), bounds=(15, 10, 75, 50)):
    image = Image.new('RGBA', size, (255, 255, 255, 0))
    ImageDraw.Draw(image).ellipse(bounds, fill='white', outline='black', width=3)
    return image


class StrictCompositionTests(unittest.TestCase):
    def test_visible_fit_ignores_only_transparent_padding_and_keeps_source(self):
        scene = cutout((600, 400), (220, 150, 360, 240))
        before = scene.tobytes()
        old, _, _ = compose([scene], scene_boxes(4)[:1], strict=True)
        new, _, _ = compose([scene], scene_boxes(4)[:1], strict=True, fit_visible=True)
        old_ink = ImageChops.difference(old.convert('RGB'), paper().convert('RGB')).getbbox()
        new_ink = ImageChops.difference(new.convert('RGB'), paper().convert('RGB')).getbbox()
        self.assertGreater(new_ink[3]-new_ink[1], 2*(old_ink[3]-old_ink[1]))
        self.assertEqual(scene.tobytes(), before)
        self.assertLessEqual(new_ink[2], 876)
        self.assertGreaterEqual(new_ink[0], 72)

    def test_opaque_rgb_and_rgba_are_rejected_without_mutation(self):
        for mode in ('RGB', 'RGBA'):
            scene = Image.new(mode, (100, 100), 'white')
            ImageDraw.Draw(scene).ellipse((20, 20, 70, 70), fill='black')
            before = scene.tobytes()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'opaque rectangle'):
                compose([scene], scene_boxes(1), strict=True)
            self.assertEqual(scene.tobytes(), before)

    def test_opaque_panel_with_transparent_padding_is_rejected(self):
        scene = Image.new('RGBA', (100, 100))
        ImageDraw.Draw(scene).rectangle((10, 10, 90, 90), fill='white', outline='black')
        with self.assertRaisesRegex(ValueError, 'opaque rectangle'):
            compose([scene], scene_boxes(1), strict=True)

    def test_all_four_edges_require_clear_margin_including_white_paint(self):
        for point in ((0, 50), (99, 50), (50, 0), (50, 99), (2, 50)):
            scene = cutout()
            scene.putpixel(point, (255, 255, 255, 255))
            with self.subTest(point=point), self.assertRaisesRegex(ValueError, 'edge'):
                compose([scene], scene_boxes(1), strict=True)

    def test_empty_and_alpha_haze_are_rejected(self):
        for scene, error in ((Image.new('RGBA', (100, 100)), 'empty'),
                             (Image.new('RGBA', (100, 100), (0, 0, 0, 1)), 'transparency')):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                compose([scene], scene_boxes(1), strict=True)

    def test_single_alpha_level_fringe_is_measured_but_never_removed(self):
        scene = cutout()
        scene.putpixel((0, 0), (255, 255, 255, 1))
        before = scene.tobytes()
        compose([scene], scene_boxes(1), strict=True)
        self.assertEqual(scene.tobytes(), before)
        scene.putpixel((0, 0), (255, 255, 255, 2))
        with self.assertRaisesRegex(ValueError, 'edge'):
            compose([scene], scene_boxes(1), strict=True)

    def test_alpha_white_interiors_and_entire_source_are_preserved(self):
        scene = cutout()
        scene.putpixel((30, 60), (20, 20, 20, 128))
        before = scene.tobytes()
        # Exact 1:1 placement makes preservation checks independent of resampling.
        box = [120 / 1200, 400 / 1600, 100 / 1200, 100 / 1600]
        output, centers, placed = compose([scene], [box], strict=True)
        self.assertEqual(placed, [[120, 400, 100, 100]])
        expected = paper()
        expected.alpha_composite(scene, (120, 400))
        self.assertEqual(output.tobytes(), expected.tobytes())
        self.assertEqual(scene.tobytes(), before)
        self.assertEqual(output.getpixel((165, 430)), (255, 255, 255, 255))
        self.assertEqual(output.getpixel((122, 402)), paper().getpixel((122, 402)))
        ink = content_box(scene)
        self.assertEqual(centers, [(400 + (ink[1] + ink[3]) / 2) / 1600])
        self.assertNotEqual(centers, [(400 + 50) / 1600])

    def test_uniform_scale_safe_zones_and_centers_for_five_scenes(self):
        scene = cutout((400, 100), (25, 10, 170, 70))
        boxes = scene_boxes(5)
        output, centers, placed = compose([scene] * 5, boxes, strict=True)
        expected = paper()
        for center, (left, top, width, height), (x, y, w, h) in zip(centers, placed, boxes):
            # A single scale with at most half-pixel rounding in each dimension.
            scale = min(width / scene.width, height / scene.height)
            self.assertLessEqual(abs(width - scene.width * scale), 2)
            self.assertAlmostEqual(width / height, 4, delta=.04)
            self.assertGreaterEqual(left, x * 1200 - 1e-8)
            self.assertGreaterEqual(top, y * 1600 - 1e-8)
            self.assertLessEqual(left + width, (x + w) * 1200 + 1e-8)
            self.assertLessEqual(top + height, (y + h) * 1600 + 1e-8)
            resized = scene.resize((width, height), Image.Resampling.LANCZOS)
            expected.alpha_composite(resized, (left, top))
            ink = content_box(resized)
            self.assertAlmostEqual(center, (top + (ink[1] + ink[3]) / 2) / 1600)
        self.assertEqual(output.tobytes(), expected.tobytes())
        changed = ImageChops.difference(output.convert('RGB'), paper().convert('RGB')).getbbox()
        self.assertGreaterEqual(changed[0], 72)
        self.assertGreaterEqual(changed[1], 272)
        self.assertLessEqual(changed[2], 876)
        self.assertLessEqual(changed[3], 1520)

    def test_reserved_overlap_and_subpixel_boxes_are_rejected(self):
        for boxes in ([[.7, .2, .2, .2]], [[.1, .1, .2, .2]],
                      [[.1, .2, .3, .5], [.1, .4, .3, .2]],
                      [[.1, .2, .00001, .2]], [[.1, float('nan'), .2, .2]]):
            with self.subTest(boxes=boxes), self.assertRaises(ValueError):
                compose([cutout()] * len(boxes), boxes, strict=True)

    def test_legacy_compose_still_accepts_opaque_scenes(self):
        output, centers, placed = compose([Image.new('RGB', (400, 100), 'black')], scene_boxes(1))
        self.assertEqual(output.size, (1200, 1600))
        self.assertAlmostEqual(placed[0][2] / placed[0][3], 4, delta=.04)
        self.assertEqual(centers, [(placed[0][1] + placed[0][3] / 2) / 1600])


class SceneBuildTests(unittest.TestCase):
    def test_large_captions_fit_five_scenes_without_painting_over_illustrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'paper.png'
            Image.new('RGB',(1200,1600),'white').save(source)
            captions=['今天和小狗慢慢散步','坐下看看手里的书页','小猫门口抬头看我','停下闻一闻','坐下翻几页']
            brief={'header':'2026.09.21 周一','title':'走走再歇歇','events':[{'caption':c} for c in captions]}
            output=root/'poster.png'
            render_png(brief,source,output,[.24,.39,.54,.69,.84])
            with Image.open(output) as image:
                ink=ImageChops.difference(image,Image.new('RGB',image.size,'white'))
                bounds=ink.crop((0,250,1200,1600)).getbbox()
                self.assertGreaterEqual(bounds[0],912)
                self.assertLessEqual(bounds[2],1128)
            with self.assertRaisesRegex(ValueError,'safe zone'):
                render_png(brief,source,root/'overlap.png',[.24,.241,.54,.69,.84])
            self.assertFalse((root/'overlap.png').exists())

    def test_caption_wrap_preserves_text_and_avoids_orphan_character(self):
        draw = ImageDraw.Draw(Image.new('RGB', (1200, 1600)))
        font = ImageFont.truetype(str(FONT_DIR / 'Yozai-Regular.ttf'), 28)
        text = '小猫门口抬头看我'
        lines = text_lines(draw, text, font, 216)
        self.assertEqual(''.join(lines), text)
        self.assertTrue(all(len(line) > 1 for line in lines))
        self.assertTrue(all(draw.textbbox((0, 0), line, font=font)[2] <= 216 for line in lines))

    def test_no_implicit_demo_date(self):
        self.assertEqual(diary_header({'date': '2026-09-21'}), '2026.09.21 周一')
        self.assertEqual(diary_header({'header': '2026.09.22 周二'}), '2026.09.22 周二')
        for config in ({}, {'date': 'yesterday'}, {'date': None}):
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, 'explicit diary'):
                diary_header(config)

    def test_counts_unknown_counts_and_mismatches_fail_before_output(self):
        for count in (0, 6, True, None, '3', 2.5):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'count'):
                scene_boxes(count)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result'
            for config in ({'title': '一天', 'captions': []},
                           {'title': '一天', 'captions': ['工作日常'], 'sceneCount': 'unknown'},
                           {'title': '一天', 'captions': ['工作日常'], 'sceneCount': 2},
                           {'title': '一天', 'captions': ['工作日常', '晚间散步']}):
                with self.subTest(config=config), self.assertRaises(ValueError):
                    build_scenes([cutout()], config, output)
                self.assertFalse(output.exists())

    def test_config_and_brief_builders_export_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'scene.png'
            cutout().save(source)
            original = source.read_bytes()
            for key, value in (('captions', ['工作日常']), ('events', [{'caption': '工作日常'}])):
                config = {'header': '2026.09.22 周二', 'title': '平凡一天', key: value}
                before = json.dumps(config)
                output = root / key
                self.assertEqual(build_scenes([source], config, output), output)
                record = json.loads((output / 'config.json').read_text())
                self.assertTrue(record['strictScenes'])
                self.assertEqual(record['sourceRects'], [[0, 0, 100, 100]])
                self.assertEqual(len(record['sceneCenters']), 1)
                for name in ('poster.png', 'illustration.png'):
                    with Image.open(output / name) as image:
                        self.assertEqual(image.size, (1200, 1600))
                with self.assertRaisesRegex(ValueError, 'output exists'):
                    build_scenes([source], config, output)
                self.assertEqual(json.dumps(config), before)
            self.assertEqual(source.read_bytes(), original)

    def test_sheet_requires_explicit_boundaries_and_checks_gutters(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'sheet.png'
            sheet = Image.new('RGB', (100, 200), 'white')
            draw = ImageDraw.Draw(sheet)
            draw.ellipse((20, 10, 80, 50), fill='black')
            draw.ellipse((20, 100, 80, 160), fill='black')
            sheet.save(source)
            with self.assertRaisesRegex(ValueError, 'rowBoundaries required'):
                extract_rows(source, 2)
            scenes, _ = extract_rows(source, 2, [0, .4, 1])
            self.assertEqual(len(scenes), 2)
            self.assertEqual(scenes[0].getchannel('A').getextrema(), (255, 255))
            with self.assertRaisesRegex(ValueError, 'split edge'):
                extract_rows(source, 2, [0, .15, 1])
            with self.assertRaisesRegex(ValueError, 'transparency'):
                extract_rows(source, 2, [0, .4, 1], strict=True)
            for boundaries in ([], [0, float('nan'), 1], [0, .5, .5], [0, True, 1], [0, .001, 1]):
                with self.subTest(boundaries=boundaries), self.assertRaises(ValueError):
                    extract_rows(source, 2, boundaries)

    def test_cli_strict_defaults_exclusive_inputs_and_legacy_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, config_path = root / 'scene.png', root / 'config.json'
            cutout().save(source)
            config_path.write_text(json.dumps({'date': '2026-09-22', 'title': '平凡一天', 'captions': ['工作日常']}))
            command = [sys.executable, '-B', str(ROOT / 'scripts/build_diary_template.py'),
                       '--config', str(config_path), '--output-dir', str(root / 'result')]

            def run(*args):
                return subprocess.run(command + list(args), capture_output=True, text=True)

            self.assertEqual(run('--scenes', str(source)).returncode, 0)
            self.assertEqual(run('--scenes', str(source), '--source', str(source)).returncode, 2)
            self.assertEqual(run('--scenes', str(source), '--legacy-sheet').returncode, 2)
            # A fresh destination lets the strict image validation run.
            command[-1] = str(root / 'opaque-result')
            cutout().convert('RGB').save(source)
            for flag in ('--scenes', '--source'):
                result = run(flag, str(source))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('opaque rectangle', result.stderr)
                self.assertFalse((root / 'opaque-result').exists())
            result = run('--source', str(source), '--legacy-sheet')
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
