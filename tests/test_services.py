import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nihowdy.content import load_hanzi, plain_pinyin, tone_pinyin
from nihowdy.services import ContentService, Proofreader
from nihowdy.store import Store


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hanzi=load_hanzi()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        with patch('nihowdy.store.load_hanzi',return_value=self.hanzi):
            self.store=Store(Path(self.tmp.name)/'test.sqlite')

    def tearDown(self):
        self.tmp.cleanup()

    def test_explanation_caches_and_rejects_invented_sources(self):
        service=ContentService(self.store)
        result={'explanation':'電 means electricity; 腦 means brain.',
                'source_urls':['https://github.com/skishore/makemeahanzi']}
        with patch.object(service,'generate',return_value=result) as generate:
            service.explain('電腦')
            service.explain('電腦')
            self.assertEqual(generate.call_count,1)
        with patch.object(service,'generate',return_value=dict(result,source_urls=['https://invented.example'])):
            with self.assertRaises(ValueError):service.explain('茶')
        self.assertNotIn('generation',self.store.item('茶'))

    def test_invalid_phrase_stays_pending(self):
        service=ContentService(self.store)
        pending=self.store.add({'text':'I would like tea.'})
        with patch.object(service,'generate',return_value={'valid':True,'text':'我要茶。','english':'I want tea.','tokens':['not-a-known-word']}):
            with self.assertRaises(ValueError):service.validate_pending(pending['id'])
        self.assertEqual(len(self.store.state()['pending']),1)

    def test_validated_phrase_preserves_coverage_gate(self):
        service=ContentService(self.store)
        pending=self.store.add({'text':'I want tea.'})
        with patch.object(service,'generate',return_value={'valid':True,'text':'我要茶。','english':'I want tea.','tokens':['我','要','茶'],'explanation':'Subject + want + object.'}):
            service.validate_pending(pending['id'])
        entry=next(i for i in self.store.state()['items'] if i['id']=='phrase:我要茶。')
        self.assertEqual(entry['coverage'],0)
        self.assertTrue(self.store.next_prompt('phrases')['empty'])

    def test_basic_feedback_does_not_change_grading(self):
        checker=Proofreader(self.store)
        feedback=checker.check('He want tea',phrase=True)
        self.assertTrue(any('agreement' in m for m in feedback['messages']))
        self.assertTrue(any('punctuation' in m for m in feedback['messages']))

    def test_pinyin_conversions(self):
        self.assertEqual(plain_pinyin('lǜ sè'),'lvse')
        self.assertEqual(plain_pinyin('lu:4 se4'),'lvse')
        self.assertEqual(tone_pinyin('dian4 nao3'),'diàn nǎo')


if __name__=='__main__':
    unittest.main()
