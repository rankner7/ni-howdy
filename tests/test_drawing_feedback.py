import copy
import json
import tempfile
import unittest
from pathlib import Path

from nihowdy.learning import shape_score
from tests.test_guided import isolated_store


# Bundled reference medians in canvas coordinates and approximate screenshot
# reconstructions. These are visual regressions, not captured pointer data.
HANDWRITING_EXAMPLES = {
    '水': (
        [[[473, 86], [500, 105], [521, 130], [508, 445], [507, 809],
          [485, 858], [442, 844], [371, 809], [369, 802], [358, 802]],
         [[147, 409], [209, 418], [354, 388], [381, 395], [392, 405],
          [384, 441], [353, 513], [280, 639], [187, 740], [113, 790]],
         [[737, 218], [750, 229], [766, 263], [721, 317], [591, 439], [590, 448]],
         [[539, 400], [550, 435], [618, 513], [729, 629], [782, 671],
          [820, 693], [990, 715]]],
        [[[578, 36], [587, 136], [590, 334], [590, 584], [584, 907]],
         [[154, 310], [407, 310], [413, 334], [404, 473], [349, 584],
          [283, 654], [211, 720]],
         [[599, 352], [651, 416], [702, 494], [783, 599], [879, 681], [946, 726]],
         [[657, 337], [750, 253], [819, 199]]]),
    '大': (
        [[[210, 442], [268, 447], [514, 397], [719, 366], [770, 371], [810, 383]],
         [[416, 90], [444, 101], [482, 141], [469, 382], [448, 506],
          [426, 580], [386, 669], [361, 704], [307, 760], [202, 833], [138, 859]],
         [[486, 470], [500, 507], [576, 616], [660, 718], [722, 782],
          [774, 823], [953, 858]]],
        [[[346, 343], [392, 343], [509, 316], [660, 298], [720, 271]],
         [[530, 117], [536, 274], [521, 382], [491, 467], [416, 575],
          [280, 702], [139, 831]],
         [[521, 386], [569, 518], [660, 605], [768, 696], [867, 762], [952, 807]]]),
    '人': (
        [[[483, 164], [508, 198], [511, 222], [473, 348], [408, 484],
          [328, 597], [271, 656], [144, 761], [72, 805]],
         [[474, 423], [477, 441], [490, 461], [571, 567], [691, 700],
          [753, 755], [798, 781], [986, 810]]],
        [[[545, 69], [551, 136], [554, 190], [533, 295], [500, 413],
          [449, 536], [392, 654], [343, 696], [238, 780], [175, 831], [72, 907]],
         [[539, 277], [569, 367], [611, 449], [632, 506], [678, 572],
          [732, 626], [801, 687], [898, 777], [985, 864]]]),
}


class GeometryFeedbackTests(unittest.TestCase):
    target = [[[100, 200], [800, 200]], [[450, 100], [450, 800]]]

    def test_hard_handwriting_examples_pass_with_unwarped_feedback(self):
        for character, (reference, ink) in HANDWRITING_EXAMPLES.items():
            with self.subTest(character=character):
                before = copy.deepcopy(ink)
                ordinary = shape_score(ink, reference, normalize=True)
                grade = shape_score(ink, reference, normalize=True, include_feedback=True)
                feedback = grade.pop('feedback')
                self.assertEqual(grade, ordinary)
                self.assertTrue(grade['correct'])
                self.assertTrue(grade['borderline'])
                self.assertTrue(feedback['missing_strokes'])
                self.assertTrue(feedback['incorrect_ink'])
                self.assertEqual(ink, before)
                # Feedback retains one global scale and translation; local
                # matching adjustments must not hide the learner's mistakes.
                for source, aligned in zip(ink, feedback['ink']):
                    self.assertEqual(len(source), len(aligned))
                reversed_ink = [list(reversed(s)) for s in reversed(ink)]
                self.assertTrue(shape_score(reversed_ink, reference, normalize=True)['correct'])
                smaller = [[[x*.6+160, y*.6+70] for x, y in s] for s in ink]
                self.assertTrue(shape_score(smaller, reference, normalize=True)['correct'])
                self.assertFalse(shape_score(ink, reference)['correct'])

    def test_hard_layout_matching_rejects_missing_or_duplicated_strokes(self):
        for character, (reference, ink) in HANDWRITING_EXAMPLES.items():
            for index in range(len(ink)):
                with self.subTest(character=character, missing=index):
                    missing = ink[:index] + ink[index+1:]
                    self.assertFalse(shape_score(missing, reference, normalize=True)['correct'])
                    duplicated = missing + [missing[0]]
                    self.assertFalse(shape_score(duplicated, reference, normalize=True)['correct'])

    def test_hard_layout_matching_rejects_large_position_errors(self):
        reference, ink = HANDWRITING_EXAMPLES['大']
        misplaced = copy.deepcopy(ink)
        misplaced[0] = [[x, y+350] for x, y in misplaced[0]]
        self.assertFalse(shape_score(misplaced, reference, normalize=True)['correct'])

    def test_wider_tolerance_accepts_offset_ink_without_correction(self):
        ink = [[[x, y+70] for x, y in s] for s in self.target]
        grade = shape_score(ink, self.target, include_feedback=True)
        self.assertTrue(grade['correct'])
        self.assertFalse(grade['borderline'])
        self.assertNotIn('feedback', grade)

    def test_ye_bend_with_short_hook_passes_with_feedback(self):
        # Approximate reconstruction of the learner's screenshot, not captured
        # pointer data. Reference is the bundled final stroke of 也, in canvas
        # coordinates. The ink sits left/below it and has a shortened hook.
        reference = [[[251, 360], [272, 373], [303, 407], [295, 592],
                      [308, 728], [320, 757], [338, 778], [389, 808],
                      [479, 830], [583, 840], [759, 836], [848, 822],
                      [900, 792], [899, 608]]]
        ink = [[[205, 373], [214, 431], [214, 542], [223, 626],
                [250, 735], [277, 810], [313, 849], [398, 882],
                [452, 894], [584, 907], [702, 910], [837, 907],
                [894, 891], [870, 846], [828, 786]]]
        grade = shape_score(ink, reference, include_feedback=True)
        self.assertTrue(grade['correct'])
        self.assertTrue(grade['borderline'])
        self.assertLess(grade['coverage'], .76)
        self.assertEqual(grade['feedback']['missing_strokes'], [0])
        self.assertTrue(grade['feedback']['incorrect_ink'])
        # Completing just the bottom or just the upright must still fail.
        for partial in (ink[0][:5], ink[0][7:]):
            self.assertFalse(shape_score([partial], reference)['correct'])
        self.assertFalse(shape_score([], reference)['correct'])

    def test_wider_band_cannot_rescue_a_wholly_misplaced_stroke(self):
        # Within the wider radius, but below the tighter per-stroke floor.
        ink = [[[100, 285], [800, 285]]]
        self.assertFalse(shape_score(ink, self.target[:1])['correct'])

    def test_borderline_short_strokes_pass_with_feedback(self):
        ink = [[[100, 200], [570, 200]], [[450, 100], [450, 570]]]
        grade = shape_score(ink, self.target, include_feedback=True)
        self.assertTrue(grade['correct'])
        self.assertTrue(grade['borderline'])
        self.assertEqual(grade['feedback']['missing_strokes'], [0, 1])
        self.assertEqual(grade['feedback']['ink'], ink)
        self.assertFalse(shape_score([[[100, 200], [450, 200]],
                                     [[450, 100], [450, 450]]], self.target)['correct'])

    def test_borderline_extra_ink_passes_but_substantial_extra_ink_fails(self):
        small_extra = [[[100, 950], [550, 950]]]
        grade = shape_score(self.target + small_extra, self.target, include_feedback=True)
        self.assertTrue(grade['correct'])
        self.assertTrue(grade['borderline'])
        self.assertTrue(grade['feedback']['incorrect_ink'])
        self.assertFalse(shape_score(self.target + [[[100, 950], [800, 950]]], self.target)['correct'])

    def test_missing_short_stroke_fails_despite_high_overall_coverage(self):
        target = self.target + [[[800, 700], [850, 750]]]
        grade = shape_score(self.target, target)
        self.assertGreater(grade['coverage'], .84)
        self.assertFalse(grade['correct'])
        self.assertFalse(grade['borderline'])

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

    def test_shape_levels_reveal_only_incorrect_characters(self):
        for level in (2, 3, 4):
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

    def test_easy_overlay_highlights_only_strokes_the_learner_must_add(self):
        prompt, plans, answer = self.answer_for(2)
        answer['drawings'][0]['strokes'] = []
        result = self.store.answer(prompt['id'], answer)
        self.assertFalse(result['correct'])
        overlay = result['details'][0]['overlay']
        paths = self.store.hanzi[plans[0]['character']]['strokes']
        self.assertEqual(overlay['reference'], paths)
        self.assertEqual(overlay['missing'], [paths[j] for j in plans[0]['missing']])
        self.assertTrue(overlay['missing'])
        self.assertTrue(all(path not in overlay['missing'] for path in plans[0]['template']))

    def test_borderline_answer_advances_and_persists_feedback(self):
        prompt, _, answer = self.answer_for(3)
        for drawing in answer['drawings']:
            for stroke in drawing['strokes']:
                start, end = stroke[0], stroke[-1]
                stroke[-1] = [a + (b-a)*.67 for a, b in zip(start, end)]
        result = self.store.answer(prompt['id'], answer)
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 4)
        self.assertTrue(all(d['borderline'] and 'overlay' in d for d in result['details']))
        self.assertEqual(self.store.answer(prompt['id'], answer), result)

    def test_hard_handwriting_mastery_preserves_feedback(self):
        reference, ink = HANDWRITING_EXAMPLES['水']
        medians = [[[x, 900-y] for x, y in s] for s in reference]
        paths = ['M ' + ' L '.join(f'{x} {y}' for x, y in s) for s in medians]
        self.store.hanzi['水'] = {'medians': medians, 'strokes': paths}
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            self.store._enroll(db, '水')
            db.execute("DELETE FROM progress WHERE mode!='drawing'")
            db.execute('UPDATE progress SET level=4')
        prompt = self.store.next_prompt('drawing')
        answer = {'drawings': [{'strokes': ink}]}
        result = self.store.answer(prompt['id'], answer)
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['status'], 'mastered')
        detail = result['details'][0]
        self.assertTrue(detail['borderline'])
        self.assertEqual(detail['overlay']['reference'], paths)
        self.assertTrue(detail['overlay']['missing'])
        self.assertTrue(detail['overlay']['incorrect_ink'])
        # Match the API representation: resampled point tuples become JSON
        # arrays both on the first response and when read back from storage.
        self.assertEqual(self.store.answer(prompt['id'], answer), json.loads(json.dumps(result)))

    def test_hint_penalty_does_not_mark_correct_drawing_as_wrong(self):
        prompt, _, answer = self.answer_for(4)
        self.store.info(prompt['id'])
        result = self.store.answer(prompt['id'], answer)
        self.assertFalse(result['correct'])
        self.assertTrue(result['answer_correct'])
        self.assertTrue(all(d['correct'] for d in result['details']))
        self.assertTrue(all('overlay' not in d for d in result['details']))
