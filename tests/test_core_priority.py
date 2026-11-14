import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.store import Store, encode
from nihowdy.vocabulary import VocabularyPolicy
from tests.test_guided import HANZI, GUIDE, ITEMS


class CorePriorityTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/'core.sqlite'
        self.store=self.open_store()
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            for item_id in ('木','一','二'):
                self.store._enroll(db,item_id)

    def open_store(self):
        items=copy.deepcopy(ITEMS)
        for item in items:
            item['collections']=['core'] if item['id'] in ('木','一') else []
        self.catalog=items
        with patch('nihowdy.store.starter_items',return_value=items), \
             patch('nihowdy.store.load_hanzi',return_value=HANZI), \
             patch('nihowdy.store.load_taiwan',return_value={ch:GUIDE for ch in HANZI}), \
             patch('nihowdy.store.VocabularyPolicy',return_value=VocabularyPolicy(counts={})):
            return Store(self.path,random.Random(4))

    def rebalance(self):
        with patch('nihowdy.store.starter_items',return_value=self.catalog):
            return self.store.prioritize_core_bins()

    def choices(self,mode):
        result=[]
        def choose(entries,rng):
            result.extend(key for key,_ in entries)
            return entries[0][0]
        with patch('nihowdy.store.weighted_choice',side_effect=choose):
            self.store.next_prompt(mode)
        return set(result)

    def test_unmastered_core_blocks_noncore_in_each_mode(self):
        for mode in ('flashcards','drawing'):
            self.assertEqual(self.choices(mode),{'木','一'})

    def test_mastery_unlocks_only_its_own_mode_and_reviews_count_as_learned(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review',level=2 WHERE mode='flashcards' AND item_id IN ('木','一')")
        self.assertIn('二',self.choices('flashcards'))
        self.assertEqual(self.choices('drawing'),{'木','一'})

    def test_demotion_reactivates_core_priority_and_cancels_noncore_prompt(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='mastered',checked_on='2099-01-01' WHERE mode='flashcards' AND item_id IN ('木','一')")
        old=self.store.next_prompt('flashcards')
        self.assertEqual(old['item']['id'],'二')
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='active' WHERE mode='flashcards' AND item_id='木'")
        self.assertEqual(self.choices('flashcards'),{'木'})
        with self.assertRaisesRegex(ValueError,'no longer eligible'):
            self.store.answer(old['id'],{'continue':True})

    def test_noncore_backlog_cannot_fill_core_bin_slots(self):
        with self.store.db() as db:
            base=self.store._item(db,'二')
            for index in range(31):
                item=dict(base,id=f'other-{index}')
                db.execute('INSERT INTO items VALUES (?,?)',(item['id'],encode(item)))
                for mode in ('flashcards','drawing'):
                    db.execute('INSERT INTO progress(item_id,mode,level,attempts) VALUES (?,?,2,1)',(item['id'],mode))
        for mode in ('flashcards','drawing'):
            self.assertEqual(self.choices(mode),{'木','一'})

    def test_rebalance_resets_only_displaced_active_progress_and_preserves_history(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2,attempts=3,failures=2,boost=1 WHERE item_id='二'")
            db.execute("UPDATE progress SET level=4,guided_completions=4 WHERE item_id='二' AND mode='drawing'")
            db.execute("UPDATE progress SET level=1,attempts=2 WHERE item_id='木' AND mode='flashcards'")
            self.store._enroll(db,'你')
            db.execute("UPDATE progress SET status='review',level=2 WHERE item_id='你' AND mode='flashcards'")
            session=self.store._session(db)
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('old',?,'二','flashcards',2,'{}')",(session,))
        before=self.store.backup()
        result=self.rebalance()
        self.assertEqual(result,{'flashcards':['二'],'drawing':['二']})
        with self.store.db() as db:
            for row in db.execute("SELECT * FROM progress WHERE item_id='二'"):
                self.assertEqual(row['level'],0 if row['mode']=='flashcards' else 1)
                self.assertEqual(row['attempts'],3)
                self.assertEqual((row['failures'],row['boost'],row['guided_completions']),(0,0,0))
            self.assertEqual(db.execute("SELECT level FROM progress WHERE item_id='木' AND mode='flashcards'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT status FROM progress WHERE item_id='你' AND mode='flashcards'").fetchone()[0],'review')
            self.assertTrue(json.loads(db.execute("SELECT payload FROM prompts WHERE id='old'").fetchone()[0])['cancelled'])
        self.assertEqual(self.store.backup()['tables']['attempts'],before['tables']['attempts'])
        self.store.restore(self.store.backup())
        self.store=self.open_store()
        for mode in ('flashcards','drawing'):
            self.assertTrue(self.choices(mode)<={'木','一'})

    def test_rebalance_restores_unenrolled_core_words(self):
        self.store.delete_entries(['一'])
        self.rebalance()
        self.assertEqual(self.choices('flashcards'),{'木','一'})

    def test_rebalance_does_not_reset_a_mode_that_finished_the_core(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='mastered',checked_on='2099-01-01' WHERE mode='flashcards' AND item_id IN ('木','一')")
            db.execute("UPDATE progress SET level=1,attempts=2 WHERE mode='flashcards' AND item_id='二'")
            db.execute("UPDATE progress SET level=2,attempts=2 WHERE mode='drawing' AND item_id='二'")
        result=self.rebalance()
        self.assertEqual(result['flashcards'],[])
        self.assertEqual(result['drawing'],['二'])
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT level FROM progress WHERE mode='flashcards' AND item_id='二'").fetchone()[0],1)


if __name__=='__main__':
    unittest.main()
