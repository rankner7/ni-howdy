import copy
import json
import tempfile
import unittest
from pathlib import Path

from nihowdy.learning import shape_score
from tests.test_guided import isolated_store


class GeometryFeedbackTests(unittest.TestCase):
    target = [[[100, 200], [800, 200]], [[450, 100], [450, 800]]]

    def test_missing_stroke_highlight_preserves_matching_ink(self):
        grade = shape_score(self.target[:1], self.target, include_feedback=True)
        self.assertFalse(grade['correct'])
        self.assertEqual(grade['feedback']['missing_strokes'], [1])
        self.assertEqual(grade['feedback']['incorrect_ink'], [])
        self.assertEqual(grade['feedback']['ink'], self.target[:1])

    def test_extra_and_misplaced_ink_marked(self):
        wrong = [[[100, 950], [800, 950]]]
        grade = shape_score(self.target + wrong, self.target, include_feedback=True)
        self.assertFalse(grade['correct'])
        self.assertEqual(grade['feedback']['missing_strokes'], [])
        self.assertEqual(grade['feedback']['incorrect_ink'][0][0], (100, 950))
        self.assertEqual(grade['feedback']['incorrect_ink'][0][-1], [800, 950])

    def test_empty_and_single_point_answers_show_missing_shape(self):
        for ink in ([], [[[10, 10]]]):
            with self.subTest(ink=ink):
                grade = shape_score(ink, self.target, include_feedback=True)
                self.assertFalse(grade['correct'])
                self.assertEqual(grade['feedback']['missing_strokes'], [0, 1])
                self.assertEqual(grade['feedback']['ink'], ink)

    def test_feedback_uses_the_grading_alignment(self):
        ink = [[[x*.6+150, y*.6+80] for x,y in s] for s in self.target]
        ink.append([[150, 80], [150, 560]])
        before = copy.deepcopy(ink)
        ordinary = shape_score(ink, self.target, normalize=True)
        grade = shape_score(ink, self.target, normalize=True, include_feedback=True)
        feedback = grade.pop('feedback')
        self.assertEqual(grade, ordinary)
        self.assertNotEqual(feedback['ink'], ink)
        # Both axes use the same scale, preserving the user's shape.
        source_width = ink[0][-1][0] - ink[0][0][0]
        source_height = ink[1][-1][1] - ink[1][0][1]
        aligned = feedback['ink']
        self.assertAlmostEqual((aligned[0][-1][0]-aligned[0][0][0])/source_width,
                               (aligned[1][-1][1]-aligned[1][0][1])/source_height)
        self.assertEqual(ink, before)

    def test_correct_reversed_answer_has_no_correction(self):
        ink = [list(reversed(s)) for s in reversed(self.target)]
        grade = shape_score(ink, self.target, include_feedback=True)
        self.assertTrue(grade['correct'])
        self.assertNotIn('feedback', grade)


class StoredFeedbackTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = isolated_store(Path(directory.name) / 'feedback.sqlite')
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            self.store._enroll(db, '電腦')
            db.execute("DELETE FROM progress WHERE mode!='drawing'")

    def answer_for(self, level):
        with self.store.db() as db:
            db.execute('UPDATE progress SET level=?', (level,))
            db.execute('UPDATE prompts SET finished=1')
        prompt = self.store.next_prompt('drawing')
        with self.store.db() as db:
            plans = json.loads(db.execute('SELECT payload FROM prompts WHERE id=?', (prompt['id'],)).fetchone()[0])['drawing']
        answer = {'drawings': [{'strokes': [[[x, 900-y] for x,y in self.store.hanzi[p['character']]['medians'][j]]
                                           for j in p['missing']]} for p in plans]}
        return prompt, plans, answer

    def test_two_hardest_levels_reveal_only_incorrect_characters(self):
        for level in (3, 4):
            with self.subTest(level=level):
                prompt, plans, answer = self.answer_for(level)
                self.assertNotIn('overlay', prompt['characters'][0])
                answer['drawings'][0]['strokes'] = []
                result = self.store.answer(prompt['id'], answer)
                self.assertFalse(result['correct'])
                bad, good = result['details']
                self.assertTrue(good['correct'])
                self.assertNotIn('overlay', good)
                data = self.store.hanzi[plans[0]['character']]
                self.assertEqual(bad['overlay']['reference'], data['strokes'])
                self.assertEqual(bad['overlay']['missing'], [data['strokes'][j] for j in plans[0]['missing']])
                self.assertEqual(bad['overlay']['ink'], [])
                self.assertEqual(self.store.answer(prompt['id'], answer), result)

    def test_easier_missing_stroke_level_has_no_overlay(self):
        prompt, _, answer = self.answer_for(2)
        answer['drawings'][0]['strokes'] = []
        result = self.store.answer(prompt['id'], answer)
        self.assertFalse(result['correct'])
        self.assertNotIn('overlay', result['details'][0])

    def test_hint_penalty_does_not_mark_correct_drawing_as_wrong(self):
        prompt, _, answer = self.answer_for(4)
        self.store.info(prompt['id'])
        result = self.store.answer(prompt['id'], answer)
        self.assertFalse(result['correct'])
        self.assertTrue(result['answer_correct'])
        self.assertTrue(all(d['correct'] for d in result['details']))
        self.assertTrue(all('overlay' not in d for d in result['details']))
