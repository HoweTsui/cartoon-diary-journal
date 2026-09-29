"""Structural contracts only: no image scoring or automatic style review."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diary_style_lock import LIBRARY, asset, attach, load_library, select_template
from build_diary_prompt import validate_brief, build_prompt
from build_diary_template import compose, extract_rows, scene_boxes, paper


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.library = {'templates': [
            {'id': 'solo3', 'sceneCount': 3, 'composition': 'solo', 'generic': True, 'tags': ['work']},
            {'id': 'pet3', 'sceneCount': 3, 'composition': 'pets', 'tags': ['cat']},
            {'id': 'solo2', 'sceneCount': 2, 'composition': 'solo', 'generic': True, 'tags': ['work']} ]}

    def test_count_before_tags(self):
        self.assertEqual(select_template(self.library, 2, 'pets', ['cat'])['id'], 'solo2')

    def test_composition_before_tags(self):
        self.assertEqual(select_template(self.library, 3, 'pets', ['work'])['id'], 'pet3')

    def test_explicit_wrong_count_rejected(self):
        with self.assertRaises(ValueError):
            select_template(self.library, 2, 'solo', template_id='solo3')

    def test_no_same_count_does_not_change_events(self):
        before = copy.deepcopy(self.library)
        with self.assertRaises(ValueError):
            select_template(self.library, 5, 'solo')
        self.assertEqual(before, self.library)


class CompositionTests(unittest.TestCase):
    def test_white_interior_and_alpha_are_preserved(self):
        scene = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
        from PIL import ImageDraw
        ImageDraw.Draw(scene).rectangle((25, 25, 75, 75), fill='white', outline='black', width=3)
        result, centers, bounds = compose([scene], scene_boxes(1))
        left, top, w, h = bounds[0]
        self.assertEqual(result.getpixel((left+w//2, top+h//2)), (255,255,255,255))
        self.assertEqual(result.getpixel((left+2, top+2)), paper().getpixel((left+2, top+2)))
        self.assertAlmostEqual(centers[0], (top+h/2)/1600)

    def test_safe_zones_unmodified_and_aspect_preserved(self):
        scene = Image.new('RGBA', (400, 100), 'black')
        output, _, bounds = compose([scene] * 5, scene_boxes(5))
        for x,y,w,h in bounds:
            self.assertLessEqual(x+w, 1200*.73+1)
            self.assertAlmostEqual(w/h, 4, delta=.04)
        self.assertEqual(output.crop((912,0,1200,1600)).tobytes(), paper().crop((912,0,1200,1600)).tobytes())
        self.assertEqual(output.crop((0,0,1200,240)).tobytes(), paper().crop((0,0,1200,240)).tobytes())

    def test_overlap_and_reserved_zone_blocked(self):
        scene = Image.new('RGBA', (10,10), 'black')
        for boxes in ([[.7,.2,.2,.2]], [[.1,.1,.2,.2]], [[.1,.2,.3,.5],[.1,.4,.3,.2]]):
            with self.assertRaises(ValueError):
                compose([scene]*len(boxes), boxes)

    def test_split_cannot_cut_ink(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'sheet.png'
            Image.new('RGB',(100,100),'black').save(source)
            with self.assertRaisesRegex(ValueError,'split edge'):
                extract_rows(source,2)
            Image.new('RGB',(100,100),'white').save(source)
            with self.assertRaisesRegex(ValueError,'empty'):
                extract_rows(source,1)


class PackagedLibraryTests(unittest.TestCase):
    def test_all_twelve_assets_exist_and_match_hashes(self):
        library = load_library()
        self.assertEqual(sorted(t['sceneCount'] for t in library['templates']), [1,1,2,2,3,3,3,3,4,4,5,5])
        asset(LIBRARY.parent, library['master'])
        asset(LIBRARY.parent, library['expressionReference'])
        for template in library['templates']:
            for key in ['illustration', 'poster', 'config']:
                asset(LIBRARY.parent, template[key])
            with Image.open(LIBRARY.parent/template['poster']['path']) as image:
                self.assertEqual(image.size, (1200,1600))

    def test_preview_replaces_old_pack_preserves_source(self):
        data = json.loads((LIBRARY.parent/'preview-brief.json').read_text())
        original = copy.deepcopy(data)
        brief = validate_brief(data, LIBRARY.parent, True)
        self.assertEqual(data, original)
        self.assertEqual(brief['sourceText'], original['sourceText'])
        refs = [r for r in brief['references'] if r.get('origin')=='bundled']
        self.assertEqual([r['id'] for r in refs], [
            'style-lock-master', 'appearance-variants-v1', 'age-proportions-v1',
            'age-variety-example-v2', 'human-expression-reference-v6'])
        self.assertNotIn(original['sourceText'], build_prompt(brief))

    def test_confirmed_identity_does_not_approve_explicit_draft_template(self):
        data = json.loads((LIBRARY.parent/'preview-brief.json').read_text())
        data['identity'].update(status='confirmed', approvedVersion=data['identity']['version'], approvedBy='user', styleVersion='style-lock-v2')
        data['references'][0]['role']='identity-approved'
        data['styleLock']['templateId']='s3-work'
        with self.assertRaisesRegex(ValueError, 'template is not user-approved'):
            validate_brief(data, LIBRARY.parent, False)

    def test_missing_or_tampered_asset_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = {'path':'missing.png', 'sha256':'0'*64}
            with self.assertRaisesRegex(ValueError,'missing'):
                asset(root,item)
            (root/'missing.png').write_bytes(b'not an image')
            with self.assertRaisesRegex(ValueError,'checksum'):
                asset(root,item)


if __name__ == '__main__':
    unittest.main()
