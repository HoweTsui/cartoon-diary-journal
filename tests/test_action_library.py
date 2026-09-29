"""Asset integrity and approval boundaries, not aesthetic scoring."""
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from build_action_trial import LIBRARY, load_action, build


class ActionLibraryTests(unittest.TestCase):
    def test_draft_preview_never_claims_global_approval(self):
        for mixed in (False, True):
            data = json.loads(LIBRARY.read_text())
            if not mixed:
                data.update(status='draft', approvedBy=None)
            data['actions'][0].update(status='draft', approvedBy=None)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                catalog = root / 'catalog.json'
                catalog.write_text(json.dumps(data))
                with patch('build_action_trial.LIBRARY', catalog):
                    output = build(root / 'preview')
                page = (output / 'index.html').read_text()
                self.assertIn('待确认动作预览', page)
                self.assertNotIn('六个动作均已确认', page)
                self.assertNotIn('用户已确认这六个结果', page)
                record = json.loads((output / 'reuse-record.json').read_text())
                self.assertEqual(record['status'], 'draft')
                self.assertIsNone(record['approvedBy'])

    def test_archived_generation_inputs_are_available_in_a_clone(self):
        root = LIBRARY.parents[3]
        records = json.loads((LIBRARY.parent / 'actions-v1/generation-requests.json').read_text())
        for request in records['requests']:
            for path in request['attachedReferences']:
                self.assertFalse(Path(path).is_absolute())
                self.assertFalse(path.startswith('task-output/'))
                self.assertTrue((root / path).is_file(), path)

    def test_updated_demos_preserve_alpha_without_claiming_new_approval(self):
        catalog=json.loads(LIBRARY.read_text())
        self.assertEqual(catalog['status'],'draft')
        self.assertIsNone(catalog['approvedBy'])
        self.assertEqual(len(catalog['actions']),6)
        self.assertEqual(len({item['id'] for item in catalog['actions']}),6)
        for item in catalog['actions']:
            if item['species'] == 'human':
                self.assertEqual(item['status'],'draft')
                with self.assertRaisesRegex(ValueError, 'draft'):
                    load_action(item['id'])
            image,entry=load_action(item['id'],preview=True)
            self.assertEqual(image.mode,'RGBA')
            low,high=image.getchannel('A').getextrema()
            self.assertEqual(low,0)
            # Generated alpha can peak at 254; retain it, never hard-quantize it.
            self.assertGreaterEqual(high,250)
            with Image.open(LIBRARY.parent/entry['source']['path']) as source:
                expected=source.convert('RGBA')
                if 'sourceRect' in entry:
                    expected=expected.crop(entry['sourceRect'])
                self.assertEqual(image.tobytes(),expected.tobytes())
            self.assertGreater(min(image.size),100)
            self.assertEqual(entry['facing'],'reference-side-right')

    def test_draft_catalog_cannot_load_for_production(self):
        data=json.loads(LIBRARY.read_text())
        data['status']='draft'
        data['approvedBy']=None
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', dir=LIBRARY.parent, delete=False) as handle:
            library=Path(handle.name)
            json.dump(data,handle)
        try:
            with self.assertRaisesRegex(ValueError,'draft'):
                load_action(data['actions'][0]['id'],library_path=library)
        finally:
            library.unlink(missing_ok=True)

    def test_unknown_action_does_not_fall_back(self):
        with self.assertRaisesRegex(ValueError,'missing'):
            load_action('cat-jump-right',preview=True)

    def test_tampered_image_and_missing_reference_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            image=root/'sprite.png'
            Image.new('RGBA',(10,10),'white').save(image)
            reference={'path':'sprite.png','sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
            data={'status':'approved','approvedBy':'user',
                  'actions':[{'id':'test','status':'approved','approvedBy':'user','image':dict(reference)}],
                  'requiredReferences':[dict(reference)]}
            library=root/'library.json'
            library.write_text(json.dumps(data))
            load_action('test',library_path=library)
            data['actions'][0]['image']['sha256']='0'*64
            library.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'checksum'):
                load_action('test',library_path=library)
            data['actions'][0]['image']=dict(reference)
            data['requiredReferences'][0]['path']='absent.png'
            library.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'missing'):
                load_action('test',library_path=library)


if __name__=='__main__':
    unittest.main()
