"""Rolling vocabulary practice, using synthetic content and a temporary database."""
import copy
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.store import Store
from nihowdy.vocabulary import VocabularyPolicy
from tests.test_guided import GUIDE, HANZI, ITEMS


class RollingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'practice.sqlite'
        self.store = self.open_store()
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            self.store._enroll(db, '木')

    def open_store(self):
        with patch('nihowdy.store.load_hanzi', return_value=HANZI), \
             patch('nihowdy.store.load_taiwan', return_value={ch: GUIDE for ch in HANZI}), \
             patch('nihowdy.store.starter_items', return_value=copy.deepcopy(ITEMS)), \
             patch('nihowdy.store.VocabularyPolicy', return_value=VocabularyPolicy({'一木': 100})):
            return Store(self.path, rng=random.Random(8))

    def progress(self, mode):
        with self.store.db() as db:
            return dict(db.execute('SELECT * FROM progress WHERE item_id=? AND mode=?', ('木', mode)).fetchone())

    def test_introductions_are_free_recoverable_and_once_per_mode(self):
        for mode in ('flashcards', 'drawing'):
            with self.subTest(mode=mode):
                before = self.progress(mode)
                prompt = self.store.next_prompt(mode)
                self.assertTrue(prompt['introduction'])
                self.assertEqual(prompt['item']['text'], '木')
                self.assertIn('characters', prompt['item'])
                self.assertEqual(self.store.next_prompt(mode), prompt)
                self.assertFalse(self.store.info(prompt['id'])['penalty'])
                self.assertEqual(self.progress(mode), before)
                self.store = self.open_store()
                self.assertEqual(self.store.next_prompt(mode), prompt)
                result = self.store.answer(prompt['id'], {'continue': True})
                self.assertEqual(result, {'introduced': True})
                self.assertEqual(self.store.answer(prompt['id'], {'continue': True}), result)
                self.assertEqual(self.progress(mode), before)
                self.store.restore(self.store.backup())
                practice = self.store.next_prompt(mode)
                self.assertFalse(practice.get('introduction', False))
                self.assertNotIn('item', practice)
                with self.store.db() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)

    def test_actual_practice_still_grades_and_penalizes_hints(self):
        intro = self.store.next_prompt('flashcards')
        with self.assertRaisesRegex(ValueError, 'Continue'):
            self.store.answer(intro['id'], {'text': '木'})
        self.store.answer(intro['id'], {'continue': True})
        prompt = self.store.next_prompt('flashcards')
        self.assertTrue(self.store.info(prompt['id'])['penalty'])
        result = self.store.answer(prompt['id'], {'text': '木'})
        self.assertTrue(result['answer_correct'])
        self.assertFalse(result['correct'])
        self.assertEqual(result['progress']['attempts'], 1)
        self.assertEqual(result['progress']['failures'], 1)

    def test_mastery_adds_words_to_same_session_without_interrupting_other_mode(self):
        other = self.store.next_prompt('drawing')
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2,attempts=2 WHERE mode='flashcards'")
        prompt = self.store.next_prompt('flashcards')
        result = self.store.answer(prompt['id'], {'text': '木'})
        self.assertEqual(result['added'], ['一木'])
        next_word = self.store.next_prompt('flashcards')
        self.assertEqual(next_word['session'], prompt['session'])
        self.assertTrue(next_word['introduction'])
        self.assertEqual(next_word['item']['text'], '一木')
        self.assertEqual(self.store.next_prompt('drawing')['id'], other['id'])
        self.assertEqual(self.store.new_session()['session'], prompt['session'])
        self.assertEqual(self.store.next_prompt('drawing')['id'], other['id'])

    def test_legacy_queued_words_and_generated_words_are_immediately_eligible(self):
        with self.store.db() as db:
            db.execute('UPDATE progress SET eligible_after=999')
        self.assertTrue(self.store.next_prompt('flashcards')['introduction'])
        result = self.store.generate_entries({'source': 'category', 'category': 'nature', 'count': 1})
        self.assertEqual([item['text'] for item in result['items']], ['一木'])
        with self.store.db() as db:
            db.execute("UPDATE prompts SET finished=1")
            db.execute("UPDATE progress SET status='mastered',checked_on='2099-01-01' WHERE item_id='木'")
        self.assertEqual(self.store.next_prompt('flashcards')['item']['text'], '一木')

    def test_existing_progress_and_reviews_do_not_get_introduced(self):
        for status, attempts, level in [('active', 1, 0), ('review', 0, 2), ('active', 0, 1)]:
            with self.subTest(status=status, attempts=attempts, level=level):
                with self.store.db() as db:
                    db.execute('DELETE FROM prompts')
                    db.execute('UPDATE progress SET status=?,attempts=?,level=? WHERE mode=?',
                               (status, attempts, level, 'flashcards'))
                self.assertFalse(self.store.next_prompt('flashcards').get('introduction', False))
