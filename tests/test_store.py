import random
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from nihowdy.content import load_hanzi
from nihowdy.store import Store


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hanzi = load_hanzi()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.day = datetime(2026, 11, 9, 17, tzinfo=timezone.utc)
        with patch('nihowdy.store.load_hanzi', return_value=self.hanzi):
            self.store = Store(Path(self.tmp.name)/'test.sqlite', random.Random(8), lambda: self.day)

    def tearDown(self):
        self.tmp.cleanup()

    def only(self, item='電腦', mode='flashcards', level=0):
        with self.store.db() as db:
            db.execute('DELETE FROM progress WHERE item_id != ? OR mode != ?', (item, mode))
            db.execute('UPDATE progress SET level=?', (level,))

    def test_hint_and_resubmission_score_once(self):
        self.only()
        prompt = self.store.next_prompt('flashcards')
        self.store.info(prompt['id'])
        self.store.info(prompt['id'])
        result = self.store.answer(prompt['id'], {'text':'computer'})
        self.assertFalse(result['correct'])
        self.assertTrue(result['answer_correct'])
        self.store.answer(prompt['id'], {'text':'computer'})
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT failures FROM progress').fetchone()[0], 1)

    def test_mastery_expands_once_and_defers(self):
        self.only(level=2)
        p = self.store.next_prompt('flashcards')
        result = self.store.answer(p['id'], {'text':'computer'})
        self.assertEqual(len(result['added']), 2)
        self.assertTrue(self.store.next_prompt('flashcards')['empty'])
        self.store.new_session()
        self.assertFalse(self.store.next_prompt('flashcards').get('empty', False))
        with self.store.db() as db:
            self.store._enroll(db, '電腦')
            self.assertEqual(self.store._expand(db, self.store._item(db,'電腦'), 2), [])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM expansions').fetchone()[0], 1)

    def test_reviews_never_reroll(self):
        self.only(level=2)
        prompt = self.store.next_prompt('flashcards')
        self.store.answer(prompt['id'], {'text':'computer'})
        self.store.update_settings({'probability':0})
        self.day = datetime(2026, 11, 12, 17, tzinfo=timezone.utc)
        self.store.state()
        self.store.state()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM trials').fetchone()[0], 3)
        self.store.update_settings({'probability':1})
        self.store.state()
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT status FROM progress WHERE item_id='電腦'").fetchone()[0], 'mastered')
        self.day = datetime(2026, 11, 13, 17, tzinfo=timezone.utc)
        self.store.state()
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT status FROM progress WHERE item_id='電腦'").fetchone()[0], 'review')

    def test_phrase_union_mastery_and_gate(self):
        self.assertTrue(self.store.next_prompt('phrases')['empty'])
        with self.store.db() as db:
            for word, mode in [('我','flashcards'),('也','drawing'),('要','flashcards'),('喝','drawing')]:
                db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode=?",(word,mode))
        self.assertFalse(self.store.next_prompt('phrases').get('empty', False))

    def test_prompt_recovery_and_audio_only(self):
        self.only(level=2)
        p = self.store.next_prompt('flashcards')
        self.assertNotIn('text',p)
        self.assertNotIn('pinyin',p)
        self.assertNotIn('english',p)
        self.assertEqual(self.store.next_prompt('flashcards')['id'], p['id'])

    def test_drawing_no_ink_fails(self):
        self.only('一','drawing',1)
        prompt = self.store.next_prompt('drawing')
        result = self.store.answer(prompt['id'], {'drawings':[{'strokes':[]}]})
        self.assertFalse(result['correct'])

    def test_restore_roundtrip(self):
        original = self.store.backup()
        self.store.update_settings({'probability':.9})
        self.store.restore(original)
        self.assertEqual(self.store.state()['settings']['probability'], .05)

    def test_new_noun_creates_phrase_with_mastery_gate(self):
        with self.store.db() as db:
            self.store._enroll(db, '毛衣')
            phrase = self.store._item(db, 'phrase:我也要買毛衣。')
            self.assertEqual(phrase['tokens'], ['我','也','要','買','毛衣'])
            self.assertEqual(phrase['english'], 'I also want to buy a sweater.')
        entry = next(i for i in self.store.state()['items'] if i['id']==phrase['id'])
        self.assertEqual(entry['coverage'], 0)

    def test_dictionary_search_keeps_other_senses_available(self):
        with self.store.db() as db:
            first=db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('行','行','háng','hang','[\"line\"]')").lastrowid
            second=db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('行','行','xíng','xing','[\"to go\"]')").lastrowid
        self.store.add({'source':'dictionary','id':first})
        results=self.store.search('行')
        self.assertTrue(any(r['id']==second and r['source']=='dictionary' for r in results))

    def test_related_dictionary_candidates_when_topic_exhausted(self):
        with self.store.db() as db:
            for item in list(self.store._items(db).values()):
                if item['kind']=='word' and item['topic']=='food':
                    self.store._enroll(db,item['id'])
            db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('豆漿','豆浆','dòu jiāng','doujiang','[\"soy milk\"]')")
            result=self.store._expand(db,self.store._item(db,'茶'),1)
            self.assertIn('豆漿',result)
            row=db.execute("SELECT added FROM expansions WHERE item_id='茶'").fetchone()
            import json
            self.assertEqual(len(json.loads(row[0])),1)
            # An unfinished expansion persists instead of falsely claiming two additions.
        self.assertTrue(any(x['item_id']=='茶' and x['remaining']==1 for x in self.store.state()['pending_expansions']))


if __name__ == '__main__':
    unittest.main()
