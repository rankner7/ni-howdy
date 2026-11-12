import random
import unittest
from nihowdy.learning import (correct_answer, transition, weight, review_trials,
                             phrase_coverage, shape_score)


def progress(**updates):
    return dict(level=0, failures=0, boost=0, attempts=0, status="active",
                mastered_on=None, checked_on=None, **updates)


class LearningTests(unittest.TestCase):
    def test_strict_text(self):
        self.assertTrue(correct_answer(" COMPUTER ", ["computer"]))
        self.assertFalse(correct_answer("computer.", ["computer"]))
        self.assertFalse(correct_answer("a computer", ["computer"]))
        self.assertFalse(correct_answer("compter", ["computer"]))

    def test_three_failures_then_success(self):
        p = progress()
        for _ in range(2):
            p = transition(p, False, 0, 2, "2026-11-10")
            self.assertEqual(p["boost"], 0)
        p = transition(p, False, 0, 2, "2026-11-10")
        self.assertEqual(p["boost"], 1)
        p = transition(p, True, 0, 2, "2026-11-10")
        self.assertEqual((p["level"], p["boost"], p["failures"]), (1, 0, 0))

    def test_master_and_demote(self):
        p = progress()
        for _ in range(3):
            p = transition(p, True, 0, 2, "2026-11-10")
        self.assertEqual(p["status"], "mastered")
        p["status"] = "review"
        for _ in range(3):
            p = transition(p, False, 0, 2, "2026-11-11")
        self.assertEqual((p["status"], p["level"]), ("active", 1))

    def test_weights(self):
        a = progress()
        b = dict(a, level=1)
        self.assertEqual(weight(a), weight(b) * 2)
        self.assertEqual(weight(dict(a, attempts=3, boost=1)), 2)
        self.assertEqual(weight(a, mode='flashcards'),
                         weight(dict(a, level=1, attempts=1), mode='flashcards'))
        self.assertEqual(weight(dict(a, attempts=1), mode='flashcards'), 1)
        self.assertEqual(weight(a, mode='drawing'), 2)

    def test_daily_trials(self):
        rng = random.Random(2)
        trials = review_trials("2026-11-09", "2026-11-12", 0, rng)
        self.assertEqual([x[0] for x in trials], ["2026-11-10", "2026-11-11", "2026-11-12"])
        self.assertEqual(review_trials("2026-11-12", "2026-11-12", .05, rng), [])
        self.assertEqual(len(review_trials("2026-11-09", "2026-11-12", 1, rng)), 1)

    def test_phrase_threshold(self):
        self.assertEqual(phrase_coverage(["I", "also", "want", "drink", "tea"],
                                        {"I", "also", "want", "drink"}), .8)
        self.assertEqual(phrase_coverage(["I", "want", "drink", "tea"],
                                        {"I", "want", "drink"}), .75)

    def test_shape_is_order_and_direction_independent(self):
        target = [[[100, 200], [800, 200]], [[450, 100], [450, 800]]]
        drawn = [list(reversed(s)) for s in reversed(target)]
        self.assertTrue(shape_score(drawn, target)["correct"])
        self.assertFalse(shape_score([], target)["correct"])
        self.assertFalse(shape_score(target[:1], target)["correct"])
        self.assertFalse(shape_score([[[0, 0], [1024, 1024]]], target)["correct"])

    def test_full_glyph_tolerates_scale_and_translation(self):
        target = [[[100,200],[800,200]], [[450,100],[450,800]]]
        drawn = [[[x*.6+160,y*.6+70] for x,y in s] for s in target]
        self.assertTrue(shape_score(drawn,target,normalize=True)['correct'])
        self.assertFalse(shape_score(drawn,target,normalize=False)['correct'])


if __name__ == "__main__":
    unittest.main()
