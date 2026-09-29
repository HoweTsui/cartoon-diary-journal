import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from diary_style_lock import LIBRARY, load_library, load_extension
from build_diary_prompt import validate_brief, geometry, generation_request

class AppearanceV2Tests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((LIBRARY.parent/'preview-brief.json').read_text())

    def test_approved_master_is_actual_first_attachment(self):
        brief = validate_brief(self.data, LIBRARY.parent, True)
        request = generation_request(brief, 1)
        self.assertEqual(Path(request['referenced_image_paths'][0]).name, 'master-approved-v2.png')
        self.assertNotIn('master-approved-v1.png', request['prompt'])
        self.assertIn('No separate neck', request['prompt'])

    def test_no_separate_neck_cannot_be_overridden(self):
        canonical = geometry({})
        self.assertEqual(canonical['human']['neckWidth'], 0)
        canonical['human']['neckWidth'] = .14
        with self.assertRaises(ValueError): geometry({'geometry':canonical})

    def test_unknown_and_young_ages_cannot_receive_adult_contour(self):
        for age in ('unknown', 'child', 'adolescent'):
            data = copy.deepcopy(self.data)
            data['characters'][0].update(ageGroup=age,chestContour='subtle-clothed')
            with self.subTest(age=age), self.assertRaisesRegex(ValueError,'adult ageGroup'):
                validate_brief(data, LIBRARY.parent, True)
        self.data['characters'][0].update(ageGroup='adult',chestContour='subtle-clothed',bodyType='full')
        validate_brief(self.data, LIBRARY.parent, True)

    def test_historical_layout_images_not_attached_in_preview(self):
        self.data['styleLock']['templateId']='s3-work'
        with self.assertRaisesRegex(ValueError, 'historical template'):
            validate_brief(self.data, LIBRARY.parent, True)

    def test_extension_roles_and_age_stage(self):
        self.assertEqual(len(load_extension()['expressionVocabulary']), 8)
        onboarding = copy.deepcopy(self.data)
        onboarding['kind'] = 'onboarding'
        onboarding['references'][0]['role'] = 'identity-source'
        onboarding['characters'][0].update(ageGroup='adult', ageStage='middle-aged')
        brief = validate_brief(onboarding, LIBRARY.parent, True)
        ids = [r['id'] for r in brief['references'] if r.get('origin') == 'bundled']
        self.assertEqual(ids, ['style-lock-master', 'appearance-variants-v1', 'age-proportions-v1',
                               'age-variety-example-v2', 'human-expression-reference-v6'])
        self.assertEqual(Path(generation_request(brief)['referenced_image_paths'][0]).name, 'master-approved-v2.png')
        self.assertTrue(all(r.get('characterIds') == ['sample-person'] for r in brief['references']
                            if r.get('id') in {'appearance-variants-v1', 'age-proportions-v1',
                                              'age-variety-example-v2', 'human-expression-reference-v6'}))
        invalid = copy.deepcopy(onboarding)
        invalid['characters'][0]['ageGroup'] = 'child'
        with self.assertRaisesRegex(ValueError, 'ageStage requires adult'):
            validate_brief(invalid, LIBRARY.parent, True)

    def test_approved_expression_reference_is_attached_for_human_expression_requests(self):
        expression = copy.deepcopy(self.data)
        expression['kind'] = 'expression'
        preview = validate_brief(expression, LIBRARY.parent, True)
        self.assertIn('human-expression-reference-v6', [r['id'] for r in preview['references'] if r.get('origin') == 'bundled'])
        self.assertNotIn('expression-draft-v2', [r['id'] for r in preview['references'] if r.get('origin') == 'bundled'])
        self.assertIn('age-variety-example-v2', [r['id'] for r in preview['references'] if r.get('origin') == 'bundled'])
        self.assertIn('human-expression-reference-v6', [r['id'] for r in validate_brief(self.data, LIBRARY.parent, True)['references'] if r.get('origin') == 'bundled'])
        self.assertIn('Approved 24-expression vocabulary', generation_request(preview)['prompt'])

    def test_every_human_task_requires_complete_pack_at_request_time(self):
        pack = {'appearance-variants-v1', 'age-proportions-v1', 'age-variety-example-v2',
                'human-expression-reference-v6'}
        for kind in ('diary', 'expression', 'onboarding'):
            data = copy.deepcopy(self.data)
            data['kind'] = kind
            if kind == 'onboarding':
                data['references'][0]['role'] = 'identity-source'
            brief = validate_brief(data, LIBRARY.parent, True)
            if kind == 'diary':
                request = generation_request(brief, 1)
            else:
                request = generation_request(brief)
            with self.subTest(kind=kind):
                pack_paths = {r['path'] for r in brief['references'] if r.get('id') in pack}
                self.assertTrue(pack_paths.issubset(set(request['referenced_image_paths'])) )
                reference = next(r for r in brief['references'] if r.get('id') == 'human-expression-reference-v6')
                self.assertIn('sample-person', reference['characterIds'])

    def test_missing_required_human_reference_blocks_request(self):
        brief = validate_brief(self.data, LIBRARY.parent, True)
        brief['references'] = [r for r in brief['references'] if r.get('id') != 'age-variety-example-v2']
        with self.assertRaisesRegex(ValueError, 'missing mandatory human reference.*age-variety-example-v2'):
            generation_request(brief, 1)

    def test_onboarding_requires_identity_source_coverage_for_each_person(self):
        data = copy.deepcopy(self.data)
        data['kind'] = 'onboarding'
        data['characters'].append({
            'id': 'second-person', 'name': '第二位角色', 'species': 'human',
            'anchors': ['长卷发', '圆框眼镜']})
        data['references'][0].update(role='identity-source', characterIds=['sample-person'])
        brief = validate_brief(data, LIBRARY.parent, True)
        with self.assertRaisesRegex(ValueError, 'no matching identity reference for character: second-person'):
            generation_request(brief)

if __name__ == '__main__': unittest.main()
