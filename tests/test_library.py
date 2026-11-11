import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from nihowdy.content import load_hanzi
from nihowdy.store import Store


class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hanzi=load_hanzi()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        with patch('nihowdy.store.load_hanzi',return_value=self.hanzi):
            self.store=Store(Path(self.tmp.name)/'test.sqlite',random.Random(9))

    def tearDown(self):
        self.tmp.cleanup()

    def master(self,item_id,mode='flashcards'):
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode=?",(item_id,mode))

    def test_delete_removes_decks_and_cancels_outstanding_prompts(self):
        with self.store.db() as db:
            db.execute("DELETE FROM progress WHERE mode='flashcards' AND item_id!='茶'")
        prompt=self.store.next_prompt('flashcards')
        self.assertEqual(prompt['text'],'茶')
        before=self.store.state()['stats']['attempts']
        self.store.delete_entries(['茶'])
        state=self.store.state()
        self.assertFalse(any(i['id']=='茶' for i in state['items']))
        with self.assertRaises(ValueError):self.store.answer(prompt['id'],{'text':'tea'})
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM progress WHERE item_id='茶'").fetchone()[0],0)
        self.assertEqual(self.store.state()['stats']['attempts'],before)

    def test_delete_protects_mastery_and_bulk_is_atomic(self):
        self.master('茶','drawing')
        with self.assertRaises(ValueError):self.store.delete_entries(['水','茶'])
        self.assertFalse(self.store.item('水').get('deleted'))
        self.assertTrue(next(i for i in self.store.state()['items'] if i['id']=='水')['enrolled'])

    def test_undo_restores_exact_unmastered_progress(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=1,failures=2,attempts=5 WHERE item_id='茶' AND mode='flashcards'")
        original=next(i for i in self.store.state()['items'] if i['id']=='茶')['progress']
        self.store.delete_entries(['茶'])
        self.store.restore_entries(['茶'])
        restored=next(i for i in self.store.state()['items'] if i['id']=='茶')['progress']
        self.assertEqual({p['mode']:p for p in original},{p['mode']:p for p in restored})

    def test_deleted_word_remains_eligible_for_generation_and_manual_restore(self):
        self.store.delete_entries(['茶'])
        source={'id':'category:food','kind':'word','topic':'food','english':'food'}
        with self.store.db() as db:
            self.assertIn('茶',[i['text'] for i in self.store._candidate_pool(db,source)])
        result=next(i for i in self.store.search('茶') if i['id']=='茶')
        self.assertTrue(result['deleted'])
        self.store.add({'source':'catalog','id':'茶'})
        self.assertTrue(next(i for i in self.store.state()['items'] if i['id']=='茶')['enrolled'])

    def test_generation_can_reintroduce_deleted_word_for_next_session(self):
        session=self.store.state()['session']
        self.store.delete_entries(['茶'])
        result=self.store.generate_entries({'source':'category','category':'tea','count':1})
        self.assertEqual([i['text'] for i in result['items']],['茶'])
        with self.store.db() as db:
            self.assertTrue(all(p['eligible_after']==session for p in db.execute("SELECT * FROM progress WHERE item_id='茶'")))

    def test_new_mastery_can_automatically_reintroduce_deleted_word(self):
        from nihowdy.vocabulary import VocabularyPolicy
        self.store.delete_entries(['茶'])
        self.store.vocabulary=VocabularyPolicy({'茶':100})
        with self.store.db() as db:
            added=self.store._expand(db,self.store._item(db,'喝'),1)
        self.assertEqual(added,['茶'])
        self.assertTrue(next(i for i in self.store.state()['items'] if i['id']=='茶')['enrolled'])

    def test_deleted_waiting_word_does_not_auto_unlock(self):
        self.assertTrue(next(i for i in self.store.state()['items'] if i['id']=='電腦')['waiting'])
        self.store.delete_entries(['電腦'])
        self.master('電')
        self.master('腦','drawing')
        self.assertFalse(any(i['id']=='電腦' for i in self.store.state()['items']))

    def test_deleted_prerequisite_pauses_phrase_even_at_eighty_percent(self):
        for item_id in ['我','也','要','喝','茶']:
            self.master(item_id)
        self.store.next_prompt('phrases')
        with self.store.db() as db:
            # Deletion here is deliberately unmastered; isolate a legacy phrase
            # with an unknown, deleted object to test the practice filter.
            db.execute("UPDATE progress SET status='active' WHERE item_id='茶'")
        self.store.delete_entries(['茶'])
        self.assertTrue(self.store.next_prompt('phrases')['empty'])
        self.assertTrue(all(i['kind']=='word' for i in self.store.state()['items']))

    def test_deleting_template_does_not_break_readding_its_word(self):
        for item_id in ['我','也','要','喝','茶']:
            self.master(item_id)
        prompt=self.store.next_prompt('phrases')
        with self.store.db() as db:
            phrase=db.execute('SELECT item_id FROM prompts WHERE id=?',(prompt['id'],)).fetchone()[0]
        self.store.delete_entries([phrase])
        self.store.add({'source':'catalog','id':'茶'})
        with self.store.db() as db:
            self.assertTrue(self.store._item(db,phrase,include_deleted=True)['deleted'])

    def test_generation_requires_a_mastered_input_word(self):
        with self.assertRaises(ValueError):self.store.generate_entries({'source':'word','id':'茶'})
        self.master('茶','drawing')
        result=self.store.generate_entries({'source':'word','id':'茶','count':2})
        self.assertEqual(result['added'],2)
        self.assertEqual(len({i['text'] for i in result['items']}),2)
        self.assertTrue(all(self.store.vocabulary.addition_weight(i['text'])>0 for i in result['items']))

    def test_generation_from_category_is_deferred_and_uses_prerequisites(self):
        state=self.store.state()
        session=state['session']
        result=self.store.generate_entries({'source':'category','category':'food','count':2})
        self.assertEqual(result['added'],2)
        with self.store.db() as db:
            for item in result['items']:
                self.assertEqual(self.store._missing_prerequisites(db,item),[])
                progress=list(db.execute('SELECT * FROM progress WHERE item_id=?',(item['id'],)))
                self.assertEqual({p['mode'] for p in progress},{'flashcards','drawing'})
                self.assertTrue(all(p['eligible_after']==session for p in progress))

    def test_custom_category_matches_existing_catalog_and_plural_terms(self):
        result=self.store.generate_entries({'source':'category','category':'coffee','count':1})
        self.assertEqual([i['text'] for i in result['items']],['咖啡'])
        self.assertEqual(self.store._neighbor_terms({'topic':'animals','english':'animals'}),['animal'])

    def test_manual_generation_does_not_consume_first_mastery_expansion(self):
        self.master('茶')
        self.store.generate_entries({'source':'word','id':'茶','count':1})
        with self.store.db() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM expansions WHERE item_id='茶'").fetchone())

    def test_generation_rejects_bad_counts_and_empty_categories(self):
        for count in [0,21,True,1.5,'2']:
            with self.assertRaises(ValueError):self.store.generate_entries({'source':'category','category':'food','count':count})
        with self.assertRaises(ValueError):self.store.generate_entries({'source':'category','category':''})
        result=self.store.generate_entries({'source':'category','category':'unmatchedcategoryxyz','count':2})
        self.assertEqual(result['items'],[])

    def test_deleted_state_survives_backup_and_restore(self):
        self.store.delete_entries(['茶'])
        backup=self.store.backup()
        self.store.restore_entries(['茶'])
        self.store.restore(backup)
        self.assertFalse(any(i['id']=='茶' for i in self.store.state()['items']))


if __name__=='__main__':
    unittest.main()
