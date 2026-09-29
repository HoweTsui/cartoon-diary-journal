import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diary_style_lock import LIBRARY, asset, load_library, validate_species_references


class SpeciesGateTests(unittest.TestCase):
    def test_each_pet_requires_its_own_guide_and_scope(self):
        for species in ('cat', 'dog'):
            character = {'id': 'pet', 'species': species}
            guide = next(r for r in load_library()['speciesReferences'] if r['species'] == species)
            ref = dict(id=guide['id'], path=asset(LIBRARY.parent, guide),
                       role='style', origin='bundled', characterIds=['pet'])
            validate_species_references([ref], [character])
            for refs in ([], [dict(ref, characterIds=['other'])], [dict(ref, role='scene')],
                         [dict(ref, path='/wrong.png')]):
                with self.assertRaises(ValueError):
                    validate_species_references(refs, [character])

    def test_missing_catalog_and_corrupt_assets_fail_closed(self):
        for mutation in ('missing', 'corrupt'):
            library = load_library()
            if mutation == 'missing':
                library['speciesReferences'] = []
            else:
                library['speciesReferences'][0]['sha256'] = '0' * 64
            with patch('diary_style_lock.load_library', return_value=library):
                with self.assertRaises(ValueError):
                    validate_species_references([], [{'id': 'cat', 'species': 'cat'}])
