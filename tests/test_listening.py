import json
import random
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from nihowdy.answers import correct_pinyin
from nihowdy.store import Store


class PinyinAnswerTests(unittest.TestCase):
    def test_tones_numbers_spacing_and_neutral_tones(self):
        for answer in ['WǑ HĒ CHÁ。', 'wo3 he1 cha2', 'wo3he1cha2', 'wǒhēchá']:
            self.assertTrue(correct_pinyin(answer, 'wǒ hē chá'))
        for answer in ['wo he cha', 'wo2 he1 cha2', 'I drink tea.', '']:
            self.assertFalse(correct_pinyin(answer, 'wǒ hē chá'))
        for answer in ['nü3 er2 ma0', 'nv3 er2 ma5', 'nu:3 er2 ma']:
            self.assertTrue(correct_pinyin(answer, 'nǚ ér ma'))
        self.assertFalse(correct_pinyin('nu3 er2 ma', 'nǚ ér ma'))


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.today = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        self.store = Store(Path(self.tmp.name) / 'test.sqlite', random.Random(4), now=lambda: self.today)
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE item_id IN ('我','喝','茶') AND mode='flashcards'")
            with patch('nihowdy.store.sentences.candidates', return_value=[]):
                self.store._phrase_options(db, generate=True)
            self.phrase = next(i for i in self.store._items(db).values() if i['text'] == '我喝茶。')
            # Isolate the mastered source phrase from the rest of the queue.
            db.execute("UPDATE progress SET status='mastered',level=2,mastered_on='2026-11-14',checked_on='2026-11-14' WHERE item_id=? AND mode='phrases'", (self.phrase['id'],))

    def test_audio_only_two_levels_and_independent_mastery(self):
        prompt = self.store.next_prompt('listening')
        self.assertEqual(prompt['levels'], ['Pinyin', 'English'])
        for field in ['text', 'pinyin', 'english', 'item', 'item_id']:
            self.assertNotIn(field, prompt)
        self.assertEqual(self.store.next_prompt('listening')['id'], prompt['id'])
        self.assertEqual(self.store.audio_item(prompt['id'])['id'], self.phrase['id'])
        result = self.store.answer(prompt['id'], {'text': 'wo3 he1 cha2'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)
        self.assertEqual(self.store.answer(prompt['id'], {'text': 'wrong'}), result)
        prompt = self.store.next_prompt('listening')
        self.assertEqual(prompt['level'], 1)
        for field in ['text', 'pinyin', 'english']:
            self.assertNotIn(field, prompt)
        result = self.store.answer(prompt['id'], {'text': 'I drink tea'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['status'], 'mastered')
        self.assertTrue(self.store.next_prompt('listening')['empty'])
        with self.store.db() as db:
            source = dict(db.execute("SELECT * FROM progress WHERE item_id=? AND mode='phrases'", (self.phrase['id'],)).fetchone())
        self.assertEqual(source['status'], 'mastered')
        self.assertEqual(source['attempts'], 0)
        self.assertNotIn(self.phrase['id'], json.dumps(self.store.state()))

    def test_composed_characters_are_graded_as_chinese(self):
        prompt = self.store.next_prompt('listening')
        result = self.store.answer(prompt['id'], {'text': '你喝茶'})
        self.assertFalse(result['correct'])
        prompt = self.store.next_prompt('listening')
        result = self.store.answer(prompt['id'], {'text': '我喝茶'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)

    def test_unmastered_source_cancels_outstanding_prompt(self):
        prompt = self.store.next_prompt('listening')
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='active' WHERE mode='phrases'")
        with self.assertRaisesRegex(ValueError, 'no longer mastered'):
            self.store.answer(prompt['id'], {'text': self.phrase['pinyin']})
        self.assertTrue(self.store.next_prompt('listening')['empty'])

    def test_hint_counts_once_and_three_misses_demote(self):
        prompt = self.store.next_prompt('listening')
        self.store.answer(prompt['id'], {'text': self.phrase['pinyin']})
        for _ in range(3):
            prompt = self.store.next_prompt('listening')
            self.store.info(prompt['id'])
            self.store.info(prompt['id'])
            result = self.store.answer(prompt['id'], {'text': self.phrase['english']})
            self.assertFalse(result['correct'])
        self.assertEqual(result['progress']['attempts'], 4)
        self.assertEqual(result['progress']['level'], 0)

    def test_backup_and_daily_review(self):
        prompt = self.store.next_prompt('listening')
        self.store.answer(prompt['id'], {'text': self.phrase['pinyin']})
        self.store.restore(self.store.backup())
        prompt = self.store.next_prompt('listening')
        self.assertEqual(prompt['level'], 1)
        self.store.answer(prompt['id'], {'text': self.phrase['english']})
        self.store.update_settings({'probability': 1})
        self.today = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
        prompt = self.store.next_prompt('listening')
        self.assertTrue(prompt['review'])
        self.assertEqual(prompt['level'], 1)
        self.assertEqual(self.store.audio_item(prompt['id'])['id'], self.phrase['id'])


if __name__ == '__main__':
    unittest.main()
