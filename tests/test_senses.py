import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.senses import automatic_sense, with_usage_note
from nihowdy.store import Store, encode
from nihowdy.vocabulary import VocabularyPolicy


def word(text, pinyin, english, **extra):
    return dict(id=text, text=text, pinyin=pinyin, english=english, answers=[english],
                kind='word', topic='food', characters=[], sources=[], **extra)


class SensePolicyTests(unittest.TestCase):
    def test_primary_sense_and_annotated_senses(self):
        self.assertEqual(automatic_sense('實', 'shí', ['solid', 'real', 'fruit']), 'solid')
        self.assertEqual(automatic_sense('水果', 'shuǐ guǒ', ['fruit']), 'fruit')
        self.assertIsNone(automatic_sense('實', 'shí', ['fruit', 'solid']))
        self.assertIsNone(automatic_sense('測', 'cè', ['(literary) to measure', 'fruit']))
        self.assertIsNone(automatic_sense('測', 'cè', []))

    def test_usage_notes_are_reading_specific_and_do_not_change_answers(self):
        for text, reading in [('水果','shuǐ guǒ'), ('果實','guǒ shí'), ('實','shí')]:
            original=word(text,reading,'fruit')
            annotated=with_usage_note(original)
            self.assertIn('usage_note',annotated)
            self.assertEqual(annotated['answers'],['fruit'])
            self.assertEqual(len(annotated['sources']),1)
            self.assertEqual(with_usage_note(annotated),annotated)
            self.assertNotIn('usage_note',original)
        self.assertNotIn('usage_note',with_usage_note(word('實','shì','fruit')))


class SenseStoreTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'test.sqlite'
        self.legacy=word('實','shí','fruit',related_to=['category:food'])
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE items(id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('INSERT INTO items VALUES (?,?)',('實',encode(self.legacy)))
        self.store=self.open_store()

    def open_store(self):
        with patch('nihowdy.store.load_hanzi',return_value={}), \
             patch('nihowdy.store.VocabularyPolicy',return_value=VocabularyPolicy(counts={})):
            return Store(self.path)

    def test_startup_repairs_existing_automatic_card(self):
        item=self.store.item('實')
        self.assertEqual(item['id'],'實')
        self.assertEqual(item['answers'],['solid','real','substantial'])
        self.assertIn('usage_note',item)
        self.assertEqual(self.open_store().item('實'),item)

    def test_repair_preserves_progress_and_retires_old_prompt_without_miss(self):
        with self.store.db() as db:
            db.execute('UPDATE items SET data=? WHERE id=?',(encode(self.legacy),'實'))
            db.execute("INSERT INTO progress(item_id,mode,level,attempts,failures) VALUES ('實','flashcards',1,4,1)")
            session=self.store._session(db)
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('old',?,'實','flashcards',1,'{}')",(session,))
            original=dict(db.execute('SELECT * FROM progress').fetchone())
        store=self.open_store()
        with store.db() as db:
            self.assertEqual(dict(db.execute('SELECT * FROM progress').fetchone()),original)
            prompt=db.execute("SELECT * FROM prompts WHERE id='old'").fetchone()
            self.assertEqual(prompt['finished'],1)
            self.assertTrue(json.loads(prompt['payload'])['cancelled'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)

    def test_explicit_manual_sense_retained_but_not_automatically_suggested(self):
        manual=word('實','shí','fruit')
        with self.store.db() as db:
            db.execute('UPDATE items SET data=? WHERE id=?',(encode(manual),'實'))
        store=self.open_store()
        self.assertEqual(store.item('實')['answers'],['fruit'])
        store.hanzi={'實':{}}
        store.vocabulary=VocabularyPolicy({'實':100000})
        with store.db() as db:
            self.assertEqual(store._candidate_pool(db,dict(id='food',topic='food',english='fruit')),[])

    def test_backup_restore_reapplies_correction(self):
        backup=self.store.backup()
        backup['tables']['items'][0]['data']=encode(self.legacy)
        self.store.restore(backup)
        self.assertNotIn('fruit',self.store.item('實')['answers'])

    def test_dictionary_generation_does_not_mine_secondary_senses(self):
        self.store.hanzi={c:{} for c in '實果水樹'}
        self.store.vocabulary=VocabularyPolicy({'實':100000,'果':100,'水果':1000,'樹':10000})
        with self.store.db() as db:
            db.execute('DELETE FROM items')
            for form, reading, meanings in [('實','shí',['solid','real','fruit']),
                                            ('樹','shù',['tree','fruit']),
                                            ('果','guǒ',['fruit','result']),
                                            ('水果','shuǐ guǒ',['fruit'])]:
                db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                           (form,reading,encode(meanings)))
            entries=self.store._dictionary_neighbors(db,dict(id='food',topic='food',english='fruit'),set())
        self.assertEqual({i['text'] for i in entries},{'果','水果'})
        self.assertIn('usage_note',next(i for i in entries if i['text']=='水果'))

    def test_manual_dictionary_addition_includes_usage_context(self):
        self.store.hanzi={c:{} for c in '果實'}
        with self.store.db() as db:
            row=dict(traditional='果實',pinyin='guǒ shí')
            item=self.store._dictionary_item(db,row,'fruit')
        self.assertEqual(item['answers'],['fruit'])
        self.assertIn('usage_note',item)
