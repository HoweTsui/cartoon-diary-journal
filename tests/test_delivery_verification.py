import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_diary_delivery import verify, digest, STEPS


class DeliveryVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        Image.new('RGB',(120,160),'white').save(self.root/'poster.png')
        (self.root/'evidence.txt').write_text('Actual call/readback fixture; not approval.')
        self.evidence = {'path':'evidence.txt','sha256':digest(self.root/'evidence.txt')}
        (self.root/'2026-09-21.md').write_text('# 2026-09-21\n\n日记正文\n\n![完整海报](poster.png)')
        self.book = {'entries':[{'id':'today','date':'2026-09-21','posterSrc':'poster.png'}]}
        self.data = {'schemaVersion':1,'date':'2026-09-21','photoCount':0,'poster':'poster.png',
                     'readerManifest':'manifest.json',
                     'steps':[{'id':step,'status':'done','evidence':[self.evidence]} for step in STEPS],
                     'note':{'kind':'local-markdown','tool':'Local vault','document':'2026-09-21.md','poster':'poster.png','photos':[]},
                     'previews':{key:self.evidence for key in ('note','reader','poster')},
                     'contentReview':self.evidence}

    def result(self):
        (self.root/'manifest.json').write_text(json.dumps(self.book))
        (self.root/'run.json').write_text(json.dumps(self.data))
        return verify(self.root/'run.json')

    def test_complete_artifacts_not_claimed_as_model_behavior_proof(self):
        result = self.result()
        self.assertEqual(result['status'],'evidence-complete',result)
        self.assertIn('not independent proof',result['scope'])

    def test_missing_book_stale_poster_and_duplicate_date_are_rejected(self):
        for entries in ([],self.book['entries']*2,[{'date':'2026-09-20','posterSrc':'poster.png'}]):
            self.book['entries'] = entries
            self.assertEqual(self.result()['status'],'blocked')
        Image.new('RGB',(120,160),'black').save(self.root/'old.png')
        self.book['entries'] = [{'date':'2026-09-21','posterSrc':'old.png'}]
        self.assertIn('stale poster',' '.join(self.result()['errors']))

    def test_download_link_does_not_count_as_inline_image(self):
        (self.root/'2026-09-21.md').write_text('[下载海报](poster.png)')
        self.assertIn('embed',' '.join(self.result()['errors']))

    def test_missing_preview_and_changed_evidence_do_not_pass(self):
        self.data['previews'].pop('reader')
        self.assertEqual(self.result()['status'],'pending')
        (self.root/'evidence.txt').write_text('Changed since recorded')
        self.assertEqual(self.result()['status'],'blocked')

    def test_photo_count_and_skipped_step_are_checked(self):
        self.data['photoCount']=1
        self.data['steps'][1]={'id':'photos','status':'not-needed','reason':'skip','evidence':[]}
        result=self.result()
        self.assertEqual(result['status'],'blocked')
        self.assertIn('photo count',' '.join(result['errors']))

    def test_remote_note_requires_live_readback_even_with_local_receipt(self):
        self.data['note']={'kind':'remote','tool':'Notion','url':'https://example.com/note','readback':self.evidence}
        result=self.result()
        self.assertEqual(result['status'],'pending')
        self.assertIn('live tool',' '.join(result['pending']))

    def test_step_records_cannot_be_omitted_or_reordered(self):
        self.data['steps'][0],self.data['steps'][1]=self.data['steps'][1],self.data['steps'][0]
        self.assertEqual(self.result()['status'],'blocked')


if __name__=='__main__':
    unittest.main()
