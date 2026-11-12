import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.answers import with_word_answers
from nihowdy.store import Store, encode
from nihowdy.vocabulary import VocabularyPolicy


class WordAnswerTests(unittest.TestCase):
    def test_noun_glosses_accept_bare_answers(self):
        for gloss, bare in [('an exit', 'exit'), ('an entrance', 'entrance'),
                            ('a computer', 'computer'), ('an apple', 'apple')]:
            with self.subTest(gloss=gloss):
                item = dict(kind='word', english=gloss, answers=[gloss])
                self.assertEqual(with_word_answers(item)['answers'], [gloss, bare])

    def test_articles_and_number_are_not_removed_from_other_expressions(self):
        for gloss in ['a little', 'a few', 'the exit', 'two exits', 'to export', 'to speak']:
            with self.subTest(gloss=gloss):
                item = dict(kind='word', answers=[gloss])
                self.assertEqual(with_word_answers(item), item)
        from nihowdy.learning import correct_answer
        answers = with_word_answers(dict(kind='word', answers=['an exit']))['answers']
        for wrong in ['the exit', 'a exit', 'exits', 'export', 'exit.', 'exit door']:
            with self.subTest(wrong=wrong):
                self.assertFalse(correct_answer(wrong, answers))

    def test_sound_explanations_are_optional_and_original_gloss_is_preserved(self):
        for gloss, plain in [('moo (sound made by cow)', 'moo'),
                             ('whinny (sound made by a horse)', 'whinny'),
                             ('roaring (sound made by animals)', 'roaring')]:
            with self.subTest(gloss=gloss):
                original = dict(kind='word', english=gloss, answers=[gloss, 'custom answer'])
                item = with_word_answers(original)
                self.assertEqual(item['english'], gloss)
                self.assertEqual(item['answers'], [gloss, 'custom answer', plain])
                self.assertEqual(with_word_answers(item), item)
                self.assertEqual(original['answers'], [gloss, 'custom answer'])

    def test_other_parenthetical_information_does_not_create_aliases(self):
        for gloss in ['(not) have', 'go (board game)', 'a (sound made by cow) b',
                      '(onom.) (sound made by a camera shutter)', 'moo (not a cow sound)']:
            with self.subTest(gloss=gloss):
                item = dict(kind='word', answers=[gloss])
                self.assertEqual(with_word_answers(item), item)
        phrase = dict(kind='phrase', answers=['moo (sound made by cow)'])
        self.assertEqual(with_word_answers(phrase), phrase)


class WordAnswerStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'test.sqlite'
        self.gloss = 'moo (sound made by cow)'
        self.item = dict(id='moo', kind='word', text='哞', pinyin='mōu', english=self.gloss,
                         answers=[self.gloss], chinese_answers=['哞'], topic='custom', sources=[])
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE items(id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('INSERT INTO items VALUES (?,?)', ('moo', encode(self.item)))
        self.store = self.open_store()
        with self.store.db() as db:
            self.store._enroll(db, 'moo')

    def open_store(self):
        with patch('nihowdy.store.load_hanzi', return_value={'哞': {}}), \
             patch('nihowdy.store.load_taiwan', return_value={}), \
             patch('nihowdy.store.VocabularyPolicy', return_value=VocabularyPolicy(counts={})):
            return Store(self.path)

    def prompt(self, level=0):
        with self.store.db() as db:
            session = self.store._session(db)
            db.execute("UPDATE progress SET level=? WHERE item_id='moo' AND mode='flashcards'", (level,))
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('test',?,'moo','flashcards',?,'{}')",
                       (session, level))
        return 'test'

    def test_saved_card_accepts_moo_and_advances(self):
        result = self.store.answer(self.prompt(), {'text': 'moo'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)
        self.assertEqual(result['progress']['attempts'], 1)
        self.assertEqual(self.store.answer('test', {'text': 'wrong'}), result)

    def test_audio_only_card_accepts_case_and_surrounding_whitespace(self):
        result = self.store.answer(self.prompt(level=2), {'text': ' MOO '})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['status'], 'mastered')

    def test_wrong_sound_still_fails(self):
        result = self.store.answer(self.prompt(), {'text': 'meow'})
        self.assertFalse(result['correct'])
        self.assertEqual(result['progress']['failures'], 1)

    def test_original_annotated_answer_still_passes(self):
        self.assertTrue(self.store.answer(self.prompt(), {'text': self.gloss})['correct'])

    def test_alias_survives_restart_and_restore_without_changing_history(self):
        before = self.store.backup()
        self.store.restore(before)
        store = self.open_store()
        self.assertEqual(store.item('moo')['answers'], [self.gloss, 'moo'])
        self.assertEqual(store.backup()['tables']['progress'], before['tables']['progress'])
        with store.db() as db:
            self.assertIn('moo', store._items(db)['moo']['answers'])

    def test_new_dictionary_card_persists_plain_sound_answer(self):
        with self.store.db() as db:
            db.execute('DELETE FROM items')
            dictionary_id = db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                                      ('哞', 'mōu', encode([self.gloss]))).lastrowid
        item = self.store.add(dict(source='dictionary', id=dictionary_id))['item']
        self.assertEqual(item['answers'], [self.gloss, 'moo'])
        with self.store.db() as db:
            saved = json.loads(db.execute('SELECT data FROM items WHERE id=?', (item['id'],)).fetchone()[0])
        self.assertEqual(saved['answers'], [self.gloss, 'moo'])

    def test_saved_exit_card_accepts_exit_without_article(self):
        with self.store.db() as db:
            item = dict(self.item, text='出口', pinyin='chū kǒu', english='an exit', answers=['an exit'])
            db.execute('UPDATE items SET data=? WHERE id=?', (encode(item), item['id']))
        result = self.store.answer(self.prompt(), {'text': 'exit'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)
        self.assertEqual(result['item']['answers'], ['an exit', 'exit'])
        self.assertEqual(self.open_store().item('moo')['answers'], ['an exit', 'exit'])

    def test_new_dictionary_exit_card_accepts_article_and_bare_noun(self):
        self.store.hanzi.update({'出': {}, '口': {}})
        with self.store.db() as db:
            dictionary_id = db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                                      ('出口', 'chū kǒu', encode(['an exit', 'to export']))).lastrowid
        item = self.store.add(dict(source='dictionary', id=dictionary_id, meaning='an exit'))['item']
        self.assertEqual(item['answers'], ['an exit', 'exit'])
        self.assertNotIn('export', item['answers'])

    def test_sense_identity_and_search_do_not_use_inferred_aliases(self):
        self.store.hanzi['器'] = {}
        senses = [('qì', 'a vessel (used for carrying liquids)'),
                  ('qì', 'a vessel (used for cooking)'), ('qì', 'vessel'), ('qí', 'vessel')]
        with self.store.db() as db:
            ids = [db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                              ('器', reading, encode([sense]))).lastrowid for reading, sense in senses]
        first = self.store.add(dict(source='dictionary', id=ids[0]))['item']
        self.assertIn('vessel', first['answers'])
        results = self.store.search('器')
        self.assertTrue(any(row['source'] == 'dictionary' and row['id'] == ids[2] for row in results))
        items = [first] + [self.store.add(dict(source='dictionary', id=identity))['item'] for identity in ids[1:]]
        self.assertEqual(len({item['id'] for item in items}), 4)
        again = self.store.add(dict(source='dictionary', id=ids[0]))['item']
        self.assertEqual(again['id'], first['id'])

    def test_general_gloss_metadata_survives_backup_and_restart(self):
        self.store.hanzi['塔'] = {}
        with self.store.db() as db:
            identity = db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                                  ('塔', 'tǎ', encode(['(literary) an observatory; a lookout tower']))).lastrowid
        item = self.store.add(dict(source='dictionary', id=identity))['item']
        self.assertIn('observatory', item['answers'])
        self.assertIn('lookout tower', item['answers'])
        self.assertEqual(item['answer_sources'], ['(literary) an observatory; a lookout tower'])
        self.assertEqual(item['dictionary_gloss']['notes'], ['literary'])
        backup = self.store.backup()
        self.store.restore(backup)
        self.assertEqual(self.open_store().item(item['id']), item)

    def test_automatically_generated_vocabulary_uses_the_same_policy(self):
        self.store.hanzi.update({char: {} for char in '望遠鏡'})
        self.store.vocabulary = VocabularyPolicy({'望遠鏡': 1000})
        with self.store.db() as db:
            db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                       ('望遠鏡', 'wàng yuǎn jìng', encode(['a telescope'])))
            entries = self.store._dictionary_neighbors(db, dict(id='source', topic='custom', english='telescope'), set())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['answers'], ['a telescope', 'telescope'])
        self.assertEqual(entries[0]['answer_sources'], ['a telescope'])
