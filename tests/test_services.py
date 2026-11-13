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
        self.assertEqual(self.store.state()['pending_count'],1)

    def test_validated_phrase_preserves_coverage_gate(self):
        service=ContentService(self.store)
        pending=self.store.add({'text':'I also want to drink tea.'})
        result={'valid':True,'text':'我也要喝茶。','english':'I also want to drink tea.',
                'tokens':['我','也','要','喝','茶'],'explanation':'Subject + also + want + action.'}
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE mode='flashcards' AND item_id IN ('我','也','要','喝')")
        with patch.object(service,'generate',return_value=result):
            with self.assertRaisesRegex(ValueError,'more than 80%'):service.validate_pending(pending['id'])
            self.assertEqual(self.store.state()['pending_count'],1)
            with self.store.db() as db:
                db.execute("UPDATE progress SET status='review' WHERE item_id='茶' AND mode='drawing'")
            self.assertTrue(service.validate_pending(pending['id'])['added'])
        self.assertEqual(self.store.state()['pending_count'],0)
        self.assertFalse(any(i['kind']=='phrase' for i in self.store.state()['items']))

    def test_short_custom_phrase_is_accepted_when_all_known(self):
        service=ContentService(self.store)
        pending=self.store.add({'text':'I want tea.'})
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE mode='flashcards'")
        with patch.object(service,'generate',return_value={'valid':True,'text':'我要茶。','english':'I want tea.','tokens':['我','要','茶']}):
            self.assertTrue(service.validate_pending(pending['id'])['added'])
        self.assertEqual(self.store.state()['pending_count'],0)

    def test_custom_punctuation_variant_does_not_reset_mastery(self):
        service=ContentService(self.store)
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE mode='flashcards' AND item_id IN ('我','要','喝','茶')")
        result={'valid':True,'text':'我要喝茶。','english':'I want to drink tea.',
                'tokens':['我','要','喝','茶'],'explanation':'Subject + want + action + object.'}
        pending=self.store.add({'text':'I want to drink tea.'})
        with patch.object(service,'generate',return_value=result):
            self.assertTrue(service.validate_pending(pending['id'])['added'])
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='mastered',level=2 WHERE item_id='phrase:我要喝茶。'")
        pending=self.store.add({'text':'I want to drink tea!'})
        with patch.object(service,'generate',return_value=dict(result,text='我要喝茶！')):
            self.assertFalse(service.validate_pending(pending['id'])['added'])
        with self.store.db() as db:
            self.assertEqual(len(self.store._phrase_history(db)),1)
            self.assertEqual(db.execute("SELECT status FROM progress WHERE item_id='phrase:我要喝茶。'").fetchone()[0],'mastered')

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
