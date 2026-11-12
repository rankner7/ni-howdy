import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.content import load_hanzi, starter_items
from nihowdy.phrases import ENGINE_VERSION, phrase_key
from nihowdy.store import Store, encode


class PhraseStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hanzi = load_hanzi()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.sqlite'
        with patch('nihowdy.store.load_hanzi', return_value=self.hanzi):
            self.store = Store(self.path, random.Random(4))

    def tearDown(self):
        self.tmp.cleanup()

    def master(self, *words):
        with self.store.db() as db:
            for word in words:
                # Isolate phrase generation from compound admission/expansion.
                db.execute("INSERT OR IGNORE INTO progress(item_id,mode,level) VALUES (?,'flashcards',2)", (word,))
                db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode='flashcards'", (word,))

    def test_word_examples_are_contextual_and_do_not_change_progress(self):
        before = self.store.backup()
        examples = self.store.word_examples('茶')
        self.assertEqual(len(examples), 3)
        for example in examples:
            self.assertIn('茶', example['text'])
            self.assertTrue(example['pinyin'])
            self.assertTrue(example['english'])
        self.assertEqual(self.store.backup(), before)

    def test_hidden_queue_and_mastered_history_survive_restart_and_backup(self):
        self.master('我', '你', '要', '也', '喝', '水', '茶', '喜歡')
        prompt = self.store.next_prompt('phrases')
        self.assertFalse(prompt.get('empty'))
        with self.store.db() as db:
            records = self.store._phrase_history(db)
            self.assertLessEqual(len(records), 8)
            target = db.execute('SELECT item_id FROM prompts WHERE id=?', (prompt['id'],)).fetchone()[0]
            item = self.store._item(db, target)
            db.execute("UPDATE progress SET level=2,status='mastered',mastered_on='2026-11-11',checked_on='2099-01-01' WHERE item_id=?", (target,))
            db.execute('UPDATE prompts SET finished=1')
            # A punctuation variant with unmastered progress cannot supersede mastery.
            duplicate = dict(item, id=item['id'] + ':old', text=item['text'].rstrip('。') + '！')
            db.execute('INSERT INTO items VALUES (?,?)', (duplicate['id'], encode(duplicate)))
            self.store._enroll(db, duplicate['id'])
        backup = self.store.backup()
        self.store.restore(backup)
        with patch('nihowdy.store.load_hanzi', return_value=self.hanzi):
            self.store = Store(self.path, random.Random(9))
        self.store.next_prompt('phrases')
        with self.store.db() as db:
            history = self.store._phrase_history(db)
            self.assertEqual(history[phrase_key(item['text'])][0]['id'], target)
            self.assertNotIn(duplicate['id'], self.store._phrase_options(db))
            self.assertEqual(db.execute('SELECT status FROM progress WHERE item_id=?', (target,)).fetchone()[0], 'mastered')
        state = self.store.state()
        self.assertTrue(all(i['kind'] == 'word' for i in state['items']))
        self.assertNotIn('phrase:', json.dumps(state, ensure_ascii=False))
        self.assertFalse(any(i['kind'] == 'phrase' for i in self.store.search('want')))
        self.assertFalse(any(i['kind'] == 'phrase' for i in self.store.search(item['text'])))

    def test_mastery_is_separate_and_pauses_after_vocabulary_demotion(self):
        self.master('我', '要', '喝', '茶')
        prompt = self.store.next_prompt('phrases')
        self.assertEqual(prompt['text'], '我要喝茶。')
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='active' WHERE item_id='茶'")
        with self.assertRaises(ValueError):
            self.store.answer(prompt['id'], {'text': 'I want to drink tea.'})
        self.assertTrue(self.store.next_prompt('phrases')['empty'])
        self.master('茶')
        next_prompt = self.store.next_prompt('phrases')
        self.assertNotEqual(next_prompt['id'], prompt['id'])
        self.assertEqual(next_prompt['level'], 0)

    def test_legacy_short_and_nonsensical_templates_are_retained_but_retired(self):
        self.master('我', '也', '要', '喝', '買', '電', '是', '學生')
        with self.store.db() as db:
            short = next(i for i in starter_items() if i['id'] == 'phrase:我是學生。')
            bad = dict(short, id='phrase:我也要買電。', text='我也要買電。',
                       tokens=['我', '也', '要', '買', '電'])
            for item in (short, bad):
                db.execute('INSERT INTO items VALUES (?,?)', (item['id'], encode(item)))
                self.store._enroll(db, item['id'])
        self.store.next_prompt('phrases')
        with self.store.db() as db:
            self.assertIn(short['id'], self.store._items(db))
            self.assertIn(bad['id'], self.store._items(db))
            options = self.store._phrase_options(db)
            self.assertNotIn(short['id'], options)
            self.assertNotIn(bad['id'], options)

    def test_existing_legacy_backlog_does_not_block_diverse_generation(self):
        self.master('我', '你', '也', '要', '喝', '買', '喜歡', '去', '家',
                    '水', '茶', '咖啡', '牛奶', '電腦', '手機', '毛衣', '書')
        with self.store.db() as db:
            for item in starter_items():
                if item['kind'] == 'phrase':
                    item['phrase_engine'] = 'local-v2'
                    db.execute('INSERT INTO items VALUES (?,?)', (item['id'], encode(item)))
                    self.store._enroll(db, item['id'])
            options = self.store._phrase_options(db, generate=True)
            fresh = [i for i in self.store._items(db).values() if i.get('phrase_engine') == ENGINE_VERSION]
            self.assertEqual(len(fresh), 8)
            self.assertGreaterEqual(len(set(options.values())), 3)
            self.assertIn('destinations', options.values())

    def test_beginner_profile_gets_non_action_phrases_and_audio_without_scoring(self):
        self.master('一', '三', '也', '二', '人', '你', '你好', '喜歡', '好', '我',
                    '是', '有', '水', '茶', '蛋', '電腦')
        prompt = self.store.next_prompt('phrases')
        self.assertFalse(prompt.get('empty'))
        before = self.store.state()['stats']['attempts']
        item = self.store.audio_item(prompt['id'])
        self.assertEqual(item['kind'], 'phrase')
        self.assertTrue(item['pinyin'])
        self.assertEqual(self.store.state()['stats']['attempts'], before)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT hint,scored FROM prompts WHERE id=?', (prompt['id'],)).fetchone()[:], (0, 0))
        self.assertFalse(any(i['kind'] == 'phrase' for i in self.store.state()['items']))


if __name__ == '__main__':
    unittest.main()
