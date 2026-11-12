import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.content import (DICTIONARY_VERSION, LEGACY_AND_GLOSS,
                             dictionary_readings, dictionary_rows)
from nihowdy.store import Store, encode
from nihowdy.vocabulary import VocabularyPolicy


class DictionaryReadingTests(unittest.TestCase):
    def test_and_has_both_readings_and_plain_meanings(self):
        rows = dict(dictionary_readings('和', 'he2', LEGACY_AND_GLOSS + '/(math.) sum/to make peace'))
        self.assertEqual(list(rows), ['he2', 'han4'])
        self.assertEqual(rows['he2'][:3], ['and', 'together with', 'with'])
        self.assertIn('(math.) sum', rows['he2'])
        self.assertEqual(rows['han4'], ['and', 'together with', 'with'])

    def test_inline_regional_note_does_not_change_other_senses(self):
        rows = dict(dictionary_readings('測', 'ce4', 'first (Taiwan pr. [ze2])/second'))
        self.assertEqual(rows, {'ze2': ['first'], 'ce4': ['second']})

    def test_standalone_regional_note_still_applies_to_entry(self):
        rows = dict(dictionary_readings('和', 'huo2', 'to mix/Taiwan pr. [huo4]/CL:個|个[ge4]'))
        self.assertEqual(rows, {'huo4': ['to mix']})
        self.assertEqual(dict(dictionary_readings('和', 'He2', 'surname He')), {})

    def test_bundled_and_entry_and_other_readings(self):
        rows = [(reading, json.loads(meanings)) for text, _, reading, _, meanings in dictionary_rows()
                if text == '和']
        self.assertIn(('hàn', ['and', 'together with', 'with']), rows)
        he = next(meanings for reading, meanings in rows if reading == 'hé')
        self.assertEqual(he[0], 'and')
        self.assertIn('(math.) sum', he)
        self.assertIn('hè', [reading for reading, _ in rows])
        self.assertTrue(all('Taiwan pr.' not in sense for _, meanings in rows for sense in meanings))


class DictionaryAndStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'test.sqlite'
        self.legacy = dict(id='和:legacy', kind='word', text='和', pinyin='hàn',
                           english=LEGACY_AND_GLOSS, answers=[LEGACY_AND_GLOSS],
                           chinese_answers=['和'], topic='custom', characters=[], sources=[])
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE items(id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('INSERT INTO items VALUES (?,?)', (self.legacy['id'], encode(self.legacy)))
        self.store = self.open_store()

    def open_store(self):
        with patch('nihowdy.store.load_hanzi', return_value={'和': {}}), \
             patch('nihowdy.store.load_taiwan', return_value={}), \
             patch('nihowdy.store.VocabularyPolicy', return_value=VocabularyPolicy(counts={})):
            return Store(self.path)

    def dictionary(self):
        rows = [('和', '和', 'hé', 'he', encode(['and', 'with', '(math.) sum'])),
                ('和', '和', 'hàn', 'han', encode(['and', 'with']))]
        with patch('nihowdy.store.dictionary_rows', return_value=iter(rows)):
            self.store.import_dictionary()

    def test_existing_card_is_repaired_and_accepts_and(self):
        item = self.store.item(self.legacy['id'])
        self.assertEqual((item['pinyin'], item['english'], item['answers']), ('hé', 'and', ['and']))
        self.assertIn('hàn', item['usage_note'])
        with self.store.db() as db:
            self.store._enroll(db, item['id'])
            session = self.store._session(db)
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('answer',?,?,'flashcards',0,'{}')",
                       (session, item['id']))
        self.assertTrue(self.store.answer('answer', {'text': 'and'})['correct'])
        self.assertEqual(self.open_store().item(item['id']), item)

    def test_repair_preserves_progress_and_cancels_old_pronunciation_prompt(self):
        with self.store.db() as db:
            db.execute('UPDATE items SET data=?', (encode(self.legacy),))
            db.execute("INSERT INTO progress(item_id,mode,level,attempts,failures) VALUES (?,'flashcards',1,7,1)",
                       (self.legacy['id'],))
            session = self.store._session(db)
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('old',?,?,'flashcards',1,'{}')",
                       (session, self.legacy['id']))
            before = dict(db.execute('SELECT * FROM progress').fetchone())
        store = self.open_store()
        with store.db() as db:
            self.assertEqual(dict(db.execute('SELECT * FROM progress').fetchone()), before)
            prompt = db.execute("SELECT * FROM prompts WHERE id='old'").fetchone()
            self.assertTrue(json.loads(prompt['payload'])['cancelled'])
            self.assertEqual(prompt['finished'], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)

    def test_explicit_han_and_unrelated_he_senses_are_preserved(self):
        for pinyin, sense in [('hàn', 'and'), ('hé', '(math.) sum'), ('hè', 'to chime in')]:
            with self.subTest(pinyin=pinyin, sense=sense):
                original = dict(self.legacy, pinyin=pinyin, english=sense, answers=[sense])
                with self.store.db() as db:
                    db.execute('UPDATE items SET data=?', (encode(original),))
                store = self.open_store()
                item = store.item(original['id'])
                self.assertEqual((item['pinyin'], item['english']), (pinyin, sense))
                self.assertIn(sense, item['answers'])
                with store.db() as db:
                    saved = json.loads(db.execute('SELECT data FROM items WHERE id=?', (original['id'],)).fetchone()[0])
                self.assertEqual(saved, original)

    def test_index_upgrade_and_search_show_readings_and_preserve_other_senses(self):
        with self.store.db() as db:
            db.execute("INSERT INTO dictionary(traditional,pinyin,meanings) VALUES ('和','hàn',?)", (encode([LEGACY_AND_GLOSS]),))
            db.execute("INSERT INTO settings VALUES ('dictionary_version','2')")
        self.dictionary()
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT value FROM settings WHERE key='dictionary_version'").fetchone()[0], DICTIONARY_VERSION)
        results = self.store.search('和')
        self.assertTrue(any(r['pinyin'] == 'hé' and r['english'] == 'and' for r in results))
        self.assertTrue(any(r['pinyin'] == 'hàn' and r['english'] == 'and' for r in results))
        self.assertTrue(any('(math.) sum' in r.get('meanings', []) and r['pinyin'] == 'hé' for r in results))
        he_results = self.store.search('hé')
        self.assertTrue(any(r['pinyin'] == 'hé' for r in he_results))
        self.assertFalse(any(r['pinyin'] == 'hàn' for r in he_results))

    def test_new_and_card_has_plain_answer_and_explicit_han_remains_available(self):
        with self.store.db() as db:
            db.execute('DELETE FROM items')
        self.dictionary()
        results = [r for r in self.store.search('and') if r['source'] == 'dictionary']
        self.assertEqual(results[0]['pinyin'], 'hé')
        he = self.store.add({'source': 'dictionary', 'id': results[0]['id'], 'meaning': 'and'})['item']
        han_row = next(r for r in results if r['pinyin'] == 'hàn')
        han = self.store.add({'source': 'dictionary', 'id': han_row['id'], 'meaning': 'and'})['item']
        self.assertEqual((he['english'], he['answers']), ('and', ['and']))
        self.assertEqual((han['pinyin'], han['answers']), ('hàn', ['and']))
        self.assertIn('hàn', han_row['usage_note'])

    def test_exact_english_matches_rank_above_substring_noise(self):
        with self.store.db() as db:
            db.execute('DELETE FROM items')
        self.dictionary()
        # Put distractors first in ID order after index generation.
        with self.store.db() as db:
            db.execute('UPDATE dictionary SET id=id+100')
            for index in range(40):
                db.execute('INSERT INTO dictionary(id,traditional,pinyin,meanings) VALUES (?,?,?,?)',
                           (index + 1, str(index), 'test', encode(['candy'])))
        result = self.store.search('and')[0]
        self.assertEqual((result['text'], result['pinyin'], result['english']), ('和', 'hé', 'and'))

    def test_restore_legacy_backup_reapplies_repair(self):
        backup = self.store.backup()
        backup['tables']['items'][0]['data'] = encode(self.legacy)
        self.store.restore(backup)
        self.assertEqual(self.store.item(self.legacy['id'])['answers'], ['and'])

    def test_adding_from_old_index_reuses_repaired_card(self):
        with self.store.db() as db:
            dictionary_id = db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                                      ('和', 'hàn', encode([LEGACY_AND_GLOSS]))).lastrowid
        result = self.store.add({'source': 'dictionary', 'id': dictionary_id})
        self.assertEqual(result['item']['id'], self.legacy['id'])
        self.assertEqual(result['item']['answers'], ['and'])
