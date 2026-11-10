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


if __name__ == '__main__':
    unittest.main()
