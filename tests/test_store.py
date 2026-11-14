import random
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from nihowdy.content import load_hanzi
from nihowdy.store import Store


class StoreTests(unittest.TestCase):
    def next_prompt(self, mode):
        prompt = self.store.next_prompt(mode)
        while prompt.get('introduction'):
            self.store.answer(prompt['id'], {'continue': True})
            prompt = self.store.next_prompt(mode)
        return prompt

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
            # These tests isolate progression after a word has already entered a deck.
            # New compound admission is exercised separately below.
            db.execute('INSERT OR IGNORE INTO progress(item_id,mode,level) VALUES (?,?,?)',(item,mode,level))
            db.execute('UPDATE progress SET level=?', (level,))

    def test_hint_and_resubmission_score_once(self):
        self.only()
        prompt = self.next_prompt('flashcards')
        self.store.info(prompt['id'])
        self.store.info(prompt['id'])
        result = self.store.answer(prompt['id'], {'text':'computer'})
        self.assertFalse(result['correct'])
        self.assertTrue(result['answer_correct'])
        self.store.answer(prompt['id'], {'text':'computer'})
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT failures FROM progress').fetchone()[0], 1)

    def test_mastery_expands_once_and_joins_rolling_shuffle(self):
        self.only(level=2)
        p = self.next_prompt('flashcards')
        result = self.store.answer(p['id'], {'text':'computer'})
        self.assertEqual(len(result['added']), 2)
        self.assertFalse(self.next_prompt('flashcards').get('empty', False))
        with self.store.db() as db:
            self.store._enroll(db, '電腦')
            self.assertEqual(self.store._expand(db, self.store._item(db,'電腦'), 2), [])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM expansions').fetchone()[0], 1)

    def test_reviews_never_reroll(self):
        self.only(level=2)
        prompt = self.next_prompt('flashcards')
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
        self.assertTrue(self.next_prompt('phrases')['empty'])
        with self.store.db() as db:
            for word, mode in [('我','flashcards'),('也','drawing'),('要','flashcards'),('喝','drawing')]:
                db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode=?",(word,mode))
        self.assertTrue(self.next_prompt('phrases')['empty'])
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE item_id='茶' AND mode='drawing'")
        self.assertFalse(self.next_prompt('phrases').get('empty', False))

    def test_prompt_recovery_and_characters_only(self):
        self.only(level=2)
        p = self.next_prompt('flashcards')
        self.assertEqual(p['text'], '電腦')
        self.assertNotIn('pinyin',p)
        self.assertNotIn('english',p)
        self.assertEqual(self.next_prompt('flashcards')['id'], p['id'])

    def test_hard_flashcards_reject_other_homophone_meanings(self):
        self.only(level=2)
        with self.store.db() as db:
            other = dict(self.store._item(db, '電腦'), id='homophone', text='同音', answers=['unrelated meaning'])
            db.execute('INSERT INTO items VALUES (?,?)', (other['id'], json.dumps(other)))
        prompt = self.next_prompt('flashcards')
        result = self.store.answer(prompt['id'], {'text': 'unrelated meaning'})
        self.assertFalse(result['correct'])

    def test_drawing_no_ink_fails(self):
        self.only('一','drawing',2)
        prompt = self.next_prompt('drawing')
        result = self.store.answer(prompt['id'], {'drawings':[{'strokes':[]}]})
        self.assertFalse(result['correct'])

    def test_restore_roundtrip(self):
        original = self.store.backup()
        self.store.update_settings({'probability':.9})
        self.store.restore(original)
        self.assertEqual(self.store.state()['settings']['probability'], .05)

    def test_mastery_history_survives_backup_and_demotes_after_review(self):
        self.only(level=2)
        self.store.update_settings({'probability': 1})
        prompt = self.next_prompt('flashcards')
        self.store.answer(prompt['id'], {'text': 'computer'})
        before = self.store.state()['mastery_history']
        self.assertEqual(before[-1], {'date': '2026-11-09', 'mastered': 1})
        backup = self.store.backup()
        self.store.restore(backup)
        self.assertEqual(self.store.state()['mastery_history'], before)
        self.day = datetime(2026, 11, 10, 17, tzinfo=timezone.utc)
        with self.store.db() as db:
            db.execute("DELETE FROM progress WHERE item_id!='電腦'")
        self.assertEqual(self.store.state()['stats']['mastered'], 1)
        for _ in range(3):
            prompt = self.next_prompt('flashcards')
            self.store.answer(prompt['id'], {'text': 'incorrect'})
        state = self.store.state()
        self.assertEqual(state['mastery_history'][-1], {'date': '2026-11-10', 'mastered': 0})
        self.assertEqual(state['stats']['mastered'], 0)

    def test_enrolling_a_noun_does_not_pregenerate_phrases(self):
        with self.store.db() as db:
            before = db.execute("SELECT COUNT(*) FROM items WHERE json_extract(data,'$.kind')='phrase'").fetchone()[0]
            self.store._enroll(db, '毛衣')
            after = db.execute("SELECT COUNT(*) FROM items WHERE json_extract(data,'$.kind')='phrase'").fetchone()[0]
            self.assertEqual(before, after)

    def test_dictionary_search_keeps_other_senses_available(self):
        with self.store.db() as db:
            first=db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('行','行','háng','hang','[\"line\"]')").lastrowid
            second=db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('行','行','xíng','xing','[\"to go\"]')").lastrowid
        self.store.add({'source':'dictionary','id':first})
        results=self.store.search('行')
        self.assertTrue(any(r['id']==second and r['source']=='dictionary' for r in results))

    def test_interrupted_dictionary_import_rolls_back_and_can_retry(self):
        with self.store.db() as db:
            db.execute("INSERT INTO dictionary(traditional,pinyin) VALUES ('舊','jiù')")
            db.execute("INSERT INTO settings VALUES ('dictionary_version','1')")
        row=('我','我','wǒ','wo','["I"]')
        def interrupt(message):
            if 'Indexed' in message:
                raise KeyboardInterrupt
        with patch('nihowdy.store.dictionary_rows',return_value=iter([row]*5001)):
            with self.assertRaises(KeyboardInterrupt):
                self.store.import_dictionary(progress=interrupt)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT traditional FROM dictionary').fetchone()[0],'舊')
            self.assertEqual(db.execute("SELECT value FROM settings WHERE key='dictionary_version'").fetchone()[0],'1')
        messages=[]
        with patch('nihowdy.store.dictionary_rows',return_value=iter([row])):
            self.store.import_dictionary(progress=messages.append)
        self.assertTrue(any('Indexed 1 entries' in m for m in messages))
        with patch('nihowdy.store.dictionary_rows') as source:
            self.store.import_dictionary(progress=messages.append)
            source.assert_not_called()
        self.assertTrue(any('existing dictionary index' in m for m in messages))

    def test_related_dictionary_candidates_when_topic_exhausted(self):
        with self.store.db() as db:
            for item in list(self.store._items(db).values()):
                if item['kind']=='word' and item['topic']=='food':
                    self.store._enroll(db,item['id'])
            db.execute("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES ('豆漿','豆浆','dòu jiāng','doujiang','[\"soy milk\"]')")
            for text,pinyin in [('豆','dòu'),('漿','jiāng')]:
                entry=dict(self.store._item(db,'茶'),id=text,text=text,pinyin=pinyin,english=text,answers=[text])
                db.execute('INSERT INTO items VALUES (?,?)',(text,json.dumps(entry,ensure_ascii=False)))
                db.execute("INSERT INTO progress(item_id,mode,level,status) VALUES (?,'flashcards',2,'review')",(text,))
            result=self.store._expand(db,self.store._item(db,'茶'),1)
            self.assertIn('豆漿',result)
            row=db.execute("SELECT added FROM expansions WHERE item_id='茶'").fetchone()
            self.assertEqual(len(json.loads(row[0])),1)
            # An unfinished expansion persists instead of falsely claiming two additions.
        self.assertTrue(any(x['item_id']=='茶' and x['remaining']==1 for x in self.store.state()['pending_expansions']))


if __name__ == '__main__':
    unittest.main()
