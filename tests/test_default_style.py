"""Regression: normal diary requests must use the approved master without an opt-in."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_diary_prompt import SKILL_ROOT, build_prompt, validate_brief, generation_request
from diary_style_lock import LIBRARY, attach, load_library


class DefaultStyleTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((LIBRARY.parent/'preview-brief.json').read_text())
        self.data.pop('styleLock')

    def test_no_opt_in_uses_approved_master_and_mandatory_human_pack(self):
        before=copy.deepcopy(self.data)
        value=validate_brief(self.data,LIBRARY.parent,True)
        self.assertEqual(self.data,before)
        self.assertEqual(value['styleLock']['version'],'style-lock-v2')
        self.assertEqual([r['id'] for r in value['references'] if r.get('origin')=='bundled'],[
            'style-lock-master', 'appearance-variants-v1', 'age-proportions-v1',
            'age-variety-example-v2', 'human-expression-reference-v6'])
        self.assertNotIn('templateId',value['styleLock'])

    def test_approved_master_works_without_promoting_templates(self):
        self.data['identity'].update(status='confirmed',approvedBy='user',approvedVersion=self.data['identity']['version'],styleVersion='style-lock-v2')
        self.data['references'][0]['role']='identity-approved'
        value=validate_brief(self.data,LIBRARY.parent,False)
        self.assertEqual(value['role'],'production')
        self.assertEqual(load_library()['status'],'draft')
        self.assertTrue(all(t['status']=='draft' for t in load_library()['templates']))

    def test_old_identity_cannot_claim_current_style_in_production(self):
        self.data['identity'].update(status='confirmed',approvedBy='user',approvedVersion=self.data['identity']['version'])
        self.data['references'][0]['role']='identity-approved'
        with self.assertRaisesRegex(ValueError,'styleVersion'):
            validate_brief(self.data,LIBRARY.parent,False)

    def test_default_cannot_be_disabled_or_replaced_with_old_pack(self):
        for request in (None,False,{'version':'old'}):
            self.data['styleLock']=request
            with self.assertRaises(ValueError):
                validate_brief(self.data,LIBRARY.parent,True)

    def test_missing_tampered_or_unapproved_master_blocks_even_preview(self):
        for mutation, message in (({'path':'missing.png'},'missing'),({'sha256':'0'*64},'checksum'),({'status':'draft'},'user-approved')):
            lib=load_library()
            lib['master'].update(mutation)
            with patch('diary_style_lock.load_library',return_value=lib):
                with self.assertRaisesRegex(ValueError,message):
                    validate_brief(self.data,LIBRARY.parent,True)

    def test_scene_request_has_master_and_only_one_event(self):
        brief=validate_brief(self.data,LIBRARY.parent,True)
        before=copy.deepcopy(brief)
        request=generation_request(brief,2)
        self.assertEqual(brief,before)
        self.assertEqual(Path(request['referenced_image_paths'][0]).name,'master-approved-v2.png')
        self.assertIn(brief['events'][1]['scene'],request['prompt'])
        self.assertNotIn(brief['events'][0]['scene'],request['prompt'])
        self.assertNotIn(brief['events'][2]['scene'],request['prompt'])
        self.assertNotIn(brief['sourceText'],request['prompt'])
        for invalid in (None,0,4,True):
            with self.assertRaises(ValueError):
                generation_request(brief,invalid)

    def test_removed_master_cannot_be_sent_as_prepared_request(self):
        brief=validate_brief(self.data,LIBRARY.parent,True)
        brief['references']=brief['references'][1:]
        with self.assertRaisesRegex(ValueError,'first attachment'):
            generation_request(brief,1)


class ScopedRequestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.data = json.loads((LIBRARY.parent / 'preview-brief.json').read_text())
        self.data.pop('styleLock')
        self.data['characters'] = [
            {'id': 'person', 'name': '示例人物', 'species': 'human', 'anchors': ['短发', '白衣']},
            {'id': 'cat', 'name': '示例猫咪', 'species': 'cat', 'anchors': ['白猫', '圆耳']}]
        self.data['protagonistId'] = 'person'
        self.data['events'] = self.data['events'][:2]
        self.data['events'][0].update(characters=['person'], scene='人物在窗边读书', referenceIds=['window'])
        self.data['events'][1].update(characters=['cat'], scene='猫咪在庭院休息', referenceIds=['garden'])
        self.data['references'] = [
            {'id': 'lineup', 'path': 'shared.png', 'role': 'identity-draft'},
            {'path': 'person.png', 'role': 'identity-draft', 'characterIds': ['person']},
            {'path': 'cat.png', 'role': 'identity-draft', 'characterIds': ['cat']},
            {'id': 'window', 'path': 'window.png', 'role': 'scene'},
            {'id': 'garden', 'path': 'garden.png', 'role': 'scene'}]
        # Distinct real PNG files: catches accidental attachment reuse/dedup.
        for index, ref in enumerate(self.data['references']):
            image = Image.new('RGB', (48, 48), 'white')
            ImageDraw.Draw(image).ellipse((3 + index * 4, 8, 20 + index * 4, 30), fill='black')
            image.save(self.base / ref['path'])

    def validate(self, data=None):
        return validate_brief(self.data if data is None else data, self.base, True)

    def test_exact_scene_attachments_and_scoped_identity_cards(self):
        self.assertEqual(len({(self.base / r['path']).read_bytes() for r in self.data['references']}), 5)
        before = copy.deepcopy(self.data)
        brief = self.validate()
        validated_before = copy.deepcopy(brief)
        human_pack = [r['path'] for r in brief['references'] if r.get('id') in {
            'appearance-variants-v1', 'age-proportions-v1', 'age-variety-example-v2',
            'human-expression-reference-v6'}]
        for number, person, background, excluded in (
                (1, 'person.png', 'window.png', ['cat.png', 'garden.png']),
                (2, 'cat.png', 'garden.png', ['person.png', 'window.png'])):
            with self.subTest(scene=number):
                request = generation_request(brief, number)
                expected = [brief['references'][0]['path']]
                if number == 2:
                    expected.append(str(LIBRARY.parent/'actions-v1/reference-inputs/cat-sitting-right.png'))
                if number == 1:
                    expected.extend(human_pack)
                expected.extend([str(self.base / 'shared.png'), str(self.base / person), str(self.base / background)])
                self.assertEqual(request['referenced_image_paths'], expected)
                for path in excluded:
                    self.assertNotIn(str(self.base / path), request['prompt'])
                self.assertIn(brief['events'][number - 1]['scene'], request['prompt'])
                self.assertNotIn(brief['events'][2 - number]['scene'], request['prompt'])
                self.assertNotIn('The template shows', request['prompt'])
                self.assertNotIn('Generate separate isolated scenes', request['prompt'])
        self.assertEqual(self.data, before)
        self.assertEqual(brief, validated_before)

    def test_legacy_shared_lineup_requires_no_character_or_event_mapping(self):
        self.data['references'] = [self.data['references'][0]]
        self.data['references'][0].pop('id')
        for event in self.data['events']:
            event.pop('referenceIds')
        brief = self.validate()
        human_pack = [r['path'] for r in brief['references'] if r.get('id') in {
            'appearance-variants-v1', 'age-proportions-v1', 'age-variety-example-v2',
            'human-expression-reference-v6'}]
        for scene in (1, 2):
            request = generation_request(brief, scene)
            expected = [brief['references'][0]['path']]
            if scene == 1:
                expected.extend(human_pack)
            else:
                expected.append(str(LIBRARY.parent/'actions-v1/reference-inputs/cat-sitting-right.png'))
            expected.append(str(self.base / 'shared.png'))
            self.assertEqual(request['referenced_image_paths'], expected)

    def test_invalid_or_missing_scene_mapping_fails_explicitly(self):
        cases = []
        data = copy.deepcopy(self.data)
        data['references'][3].pop('id')
        cases.append((data, 'scene reference requires id'))
        data = copy.deepcopy(self.data)
        data['events'][0].pop('referenceIds')
        cases.append((data, 'unmapped: window'))
        for ids in (['unknown'], ['lineup'], ['window', 'window'], 'window', [None]):
            data = copy.deepcopy(self.data)
            data['events'][0]['referenceIds'] = ids
            cases.append((data, 'referenceIds'))
        data = copy.deepcopy(self.data)
        data['references'][4]['id'] = 'window'
        cases.append((data, 'duplicate reference.id'))
        data = copy.deepcopy(self.data)
        data['references'][4]['path'] = 'window.png'
        cases.append((data, 'conflicting mapping'))
        for data, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.validate(data)

    def test_scene_without_background_is_explicitly_empty_not_all_backgrounds(self):
        self.data['events'][0]['referenceIds'] = []
        self.data['events'][1]['referenceIds'] = ['window', 'garden']
        request = generation_request(self.validate(), 1)
        self.assertEqual([Path(p).name for p in request['referenced_image_paths']],
                         ['master-approved-v2.png', 'appearance-variants.png', 'age-proportions.png',
                          'appearance-unified-v3.png', 'human-expression-reference-v6.png',
                          'shared.png', 'person.png'])

    def test_scene_reference_can_be_explicitly_reused_across_events(self):
        self.data['references'] = [r for r in self.data['references'] if r.get('id') != 'garden']
        self.data['events'][1]['referenceIds'] = ['window']
        brief = self.validate()
        for number in (1, 2):
            request = generation_request(brief, number)
            self.assertEqual(request['referenced_image_paths'][-1], str(self.base / 'window.png'))

    def test_identity_scope_validation_and_missing_visible_character_card(self):
        for ids in ([], ['unknown'], ['person', 'person'], 'person', [None]):
            data = copy.deepcopy(self.data)
            data['references'][1]['characterIds'] = ids
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, 'characterIds'):
                self.validate(data)
        data = copy.deepcopy(self.data)
        data['references'][3]['characterIds'] = ['person']
        with self.assertRaisesRegex(ValueError, 'identity references only'):
            self.validate(data)
        self.data['references'] = [r for r in self.data['references'] if r['path'] not in {'shared.png', 'cat.png'}]
        brief = self.validate()
        generation_request(brief, 1)
        with self.assertRaisesRegex(ValueError, 'no matching identity reference.*cat'):
            generation_request(brief, 2)

    def test_production_requires_approved_card_for_each_visible_character(self):
        self.data['identity'].update(status='confirmed', approvedBy='user',
                                     approvedVersion=self.data['identity']['version'], styleVersion='style-lock-v2')
        self.data['references'][1]['role'] = 'identity-approved'
        brief = validate_brief(self.data, self.base, False)
        generation_request(brief, 1)
        with self.assertRaisesRegex(ValueError, 'no matching identity reference.*cat'):
            generation_request(brief, 2)

    def test_request_rechecks_mapping_instead_of_silently_feeding_unmapped_images(self):
        brief = self.validate()
        brief['events'][0].pop('referenceIds')
        with self.assertRaisesRegex(ValueError, 'unmapped: window'):
            generation_request(brief, 1)

    def test_old_identity_geometry_is_corrected_in_onboarding_and_diary_preview(self):
        self.data['identity'].update(status='confirmed', approvedBy='user',
                                     approvedVersion=self.data['identity']['version'])
        self.data['references'] = [self.data['references'][0]]
        self.data['references'][0]['role'] = 'identity-approved'
        for event in self.data['events']:
            event.pop('referenceIds')
        for kind in ('diary', 'onboarding'):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.data)
                data['kind'] = kind
                if kind == 'onboarding':
                    data['references'][0]['role'] = 'identity-source'
                brief = self.validate(data)
                request = generation_request(brief, 1 if kind == 'diary' else None)
                self.assertIn('Preserve hairstyle, clothing and accessories from identity references', request['prompt'])
                self.assertIn('from the current master and canonical geometry, correcting conflicting old-card geometry', request['prompt'])
                self.assertNotIn('Preserve identity, nose, upper contour gap and proportions', request['prompt'])
                self.assertNotIn('styleVersion', data['identity'])

    def test_cli_prompt_file_and_stdout_equal_single_scene_request_exactly(self):
        brief_path = self.base / 'brief.json'
        brief_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        request_path, prompt_path = self.base / 'request.json', self.base / 'prompt.txt'
        command = [sys.executable, '-B', str(SKILL_ROOT / 'scripts/build_diary_prompt.py'),
                   str(brief_path), '--preview', '--scene', '2', '--request-output', str(request_path)]
        result = subprocess.run(command + ['--output', str(prompt_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        request = json.loads(request_path.read_text(encoding='utf-8'))
        self.assertEqual(prompt_path.read_text(encoding='utf-8'), request['prompt'])
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, request['prompt'])
        self.assertIn(self.data['events'][1]['scene'], result.stdout)
        self.assertNotIn(self.data['events'][0]['scene'], result.stdout)

    def test_legacy_multi_event_prompt_is_marked_as_planning_only(self):
        prompt = build_prompt(self.validate())
        self.assertIn('Planning overview only: do not render these events together', prompt)
        self.assertNotIn('Create one complete 3:4 diary poster', prompt)


if __name__=='__main__':
    unittest.main()
