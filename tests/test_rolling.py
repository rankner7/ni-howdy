"""Rolling vocabulary practice, using synthetic content and a temporary database."""
import copy
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.store import Store, encode
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

    def fill_flashcard_bin(self, count):
        with self.store.db() as db:
            original = self.store._item(db, '木')
            for index in range(count):
                item = dict(original, id=f'bin-{index}')
                db.execute('INSERT INTO items VALUES (?,?)', (item['id'], encode(item)))
                db.execute("INSERT INTO progress(item_id,mode,level,attempts) VALUES (?,'flashcards',0,1)", (item['id'],))

    def fill_drawing_bin(self, count):
        with self.store.db() as db:
            original = self.store._item(db, '木')
            for index in range(count):
                item = dict(original, id=f'drawing-bin-{index}')
                db.execute('INSERT INTO items VALUES (?,?)', (item['id'], encode(item)))
                db.execute("INSERT INTO progress(item_id,mode,level,attempts) VALUES (?,'drawing',?,1)",
                           (item['id'], self.store.lowest(item, 'drawing')))

    def drawing_candidates(self):
        captured = []
        def choose(entries, rng):
            captured.extend(key for key, _ in entries)
            return entries[0][0]
        with patch('nihowdy.store.weighted_choice', side_effect=choose):
            self.store.next_prompt('drawing')
        return set(captured)

    def test_full_drawing_bin_blocks_new_words_independently_of_flashcards(self):
        self.fill_drawing_bin(8)
        self.assertEqual(self.drawing_candidates(), {f'drawing-bin-{i}' for i in range(8)})
        self.assertTrue(self.store.next_prompt('flashcards')['introduction'])

    def test_drawing_introduction_reserves_eighth_slot_across_restart_and_backup(self):
        self.fill_drawing_bin(7)
        with patch('nihowdy.store.weighted_choice', return_value='木'):
            prompt = self.store.next_prompt('drawing')
        self.assertTrue(prompt['introduction'])
        self.store = self.open_store()
        self.assertEqual(self.store.next_prompt('drawing')['id'], prompt['id'])
        self.store.answer(prompt['id'], {'continue':True})
        with self.store.db() as db:
            self.store._enroll(db, '一木')
        self.store.restore(self.store.backup())
        available = self.drawing_candidates()
        self.assertNotIn('一木', available)
        # The just-introduced 木 holds its slot but is skipped as an immediate repeat.
        self.assertEqual(available, {f'drawing-bin-{i}' for i in range(7)})
        self.assertEqual(self.progress('drawing')['attempts'], 0)

    def test_drawing_mastery_frees_a_slot(self):
        self.fill_drawing_bin(8)
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=4 WHERE item_id='drawing-bin-0'")
        with patch('nihowdy.store.weighted_choice', return_value='drawing-bin-0'):
            prompt = self.store.next_prompt('drawing')
        result = self.store.answer(prompt['id'], {'drawings':[{
            'strokes':[[[x,900-y] for x,y in stroke] for stroke in HANZI['木']['medians']]}]})
        self.assertEqual(result['progress']['status'], 'mastered')
        self.assertIn('木', self.drawing_candidates())

    def test_existing_drawing_backlog_is_limited_to_eight_without_losing_progress(self):
        self.fill_drawing_bin(9)
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review',level=4 WHERE item_id='drawing-bin-0'")
        self.assertEqual(self.drawing_candidates(), {f'drawing-bin-{i}' for i in range(8)})
        with self.store.db() as db:
            waiting = dict(db.execute("SELECT * FROM progress WHERE item_id='drawing-bin-8' AND mode='drawing'").fetchone())
            self.assertEqual(waiting['attempts'],1)
            self.assertEqual(waiting['status'],'active')
            self.assertEqual(db.execute("SELECT status FROM progress WHERE item_id='drawing-bin-0' AND mode='drawing'").fetchone()[0],'review')

    def test_existing_drawing_backlog_also_prefers_simpler_words(self):
        self.fill_drawing_bin(9)
        self.store.taiwan['一'] = dict(strokes=GUIDE['strokes'][:1],medians=GUIDE['medians'][:1])
        with self.store.db() as db:
            item = self.store._item(db, 'drawing-bin-8')
            item['text'] = '一'
            db.execute('UPDATE items SET data=? WHERE id=?',(encode(item),item['id']))
        available = self.drawing_candidates()
        self.assertIn('drawing-bin-8',available)
        self.assertNotIn('drawing-bin-7',available)
        self.assertEqual(len(available),8)

    def test_deleting_a_drawing_word_frees_a_slot(self):
        self.fill_drawing_bin(8)
        self.store.delete_entries(['drawing-bin-0'])
        available = self.drawing_candidates()
        self.assertIn('木', available)
        self.assertNotIn('drawing-bin-0', available)
        self.assertEqual(len(available), 8)

    def test_drawing_admission_prefers_fewer_strokes_using_taiwan_templates(self):
        self.fill_drawing_bin(7)
        with self.store.db() as db:
            self.store._enroll(db, '一')
            self.store._enroll(db, '二')
        for character, count in [('木',4), ('一',1), ('二',2)]:
            self.store.taiwan[character] = dict(strokes=GUIDE['strokes'][:1]*count,
                                               medians=GUIDE['medians'][:1]*count)
        available = self.drawing_candidates()
        self.assertIn('一', available)
        self.assertNotIn('二', available)
        self.assertNotIn('木', available)
        self.assertEqual(len(available), 8)

    def test_drawing_admission_prefers_fewer_characters_before_strokes(self):
        self.fill_drawing_bin(7)
        with self.store.db() as db:
            self.store._enroll(db, '電腦')
        for character, count in [('木',8), ('電',1), ('腦',1)]:
            self.store.taiwan[character] = dict(strokes=GUIDE['strokes'][:1]*count,
                                               medians=GUIDE['medians'][:1]*count)
        available = self.drawing_candidates()
        self.assertIn('木', available)
        self.assertNotIn('電腦', available)

    def test_drawing_advanced_progress_reserves_slot_even_without_attempt_history(self):
        self.fill_drawing_bin(7)
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2 WHERE item_id='木' AND mode='drawing'")
            self.store._enroll(db, '一')
        self.assertNotIn('一', self.drawing_candidates())

    def test_full_flashcard_bin_blocks_new_introductions_but_not_drawing(self):
        self.fill_flashcard_bin(30)
        flashcard = self.store.next_prompt('flashcards')
        self.assertFalse(flashcard.get('introduction', False))
        self.assertNotEqual(flashcard.get('text'), None)
        self.assertTrue(self.store.next_prompt('drawing')['introduction'])

    def test_introduction_reserves_thirtieth_slot_across_reload_and_backup(self):
        self.fill_flashcard_bin(29)
        with patch('nihowdy.store.weighted_choice', side_effect=lambda entries, rng: '木'):
            prompt = self.store.next_prompt('flashcards')
        self.assertTrue(prompt['introduction'])
        self.store = self.open_store()
        self.assertEqual(self.store.next_prompt('flashcards')['id'], prompt['id'])
        self.store.answer(prompt['id'], {'continue': True})
        self.store.generate_entries({'source':'category', 'category':'nature', 'count':1})
        self.store.restore(self.store.backup())
        captured = []
        def choose(entries, rng):
            captured.extend(key for key, _ in entries)
            return entries[0][0]
        with patch('nihowdy.store.weighted_choice', side_effect=choose):
            self.store.next_prompt('flashcards')
        self.assertNotIn('一木', captured)
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT attempts FROM progress WHERE item_id='一木' AND mode='flashcards'").fetchone()[0], 0)

    def test_mastery_still_adds_words_and_frees_one_slot(self):
        self.fill_flashcard_bin(30)
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2 WHERE item_id='bin-0'")
        with patch('nihowdy.store.weighted_choice', return_value='bin-0'):
            prompt = self.store.next_prompt('flashcards')
        result = self.store.answer(prompt['id'], {'text':'木'})
        self.assertIn('一木', result['added'])
        with patch('nihowdy.store.weighted_choice', return_value='一木'):
            introduction = self.store.next_prompt('flashcards')
        self.assertTrue(introduction['introduction'])
        self.store.answer(introduction['id'], {'continue':True})
        captured = []
        def choose(entries, rng):
            captured.extend(key for key, _ in entries)
            return entries[0][0]
        with patch('nihowdy.store.weighted_choice', side_effect=choose):
            self.store.next_prompt('flashcards')
        self.assertNotIn('木', captured)

    def test_existing_bin_over_cap_and_reviews_remain_available(self):
        self.fill_flashcard_bin(31)
        with self.store.db() as db:
            db.execute("UPDATE progress SET status='review',level=2 WHERE item_id='bin-0'")
        captured = []
        def choose(entries, rng):
            captured.extend(key for key, _ in entries)
            return entries[0][0]
        with patch('nihowdy.store.weighted_choice', side_effect=choose):
            self.store.next_prompt('flashcards')
        self.assertIn('bin-0', captured)
        self.assertEqual(len(captured), 31)
        self.assertNotIn('木', captured)

    def test_introductions_are_free_recoverable_and_once_per_mode(self):
        for mode in ('flashcards', 'drawing'):
            with self.subTest(mode=mode):
                before = self.progress(mode)
                prompt = self.store.next_prompt(mode)
                self.assertTrue(prompt['introduction'])
                self.assertEqual(prompt['item']['text'], '木')
                self.assertEqual(self.store.audio_item(prompt['id'])['text'], '木')
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
