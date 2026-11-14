import unittest
from zoneinfo import ZoneInfo

from nihowdy.history import mastery_history


class MasteryHistoryTests(unittest.TestCase):
    def history(self, attempts=(), progress=(), today='2026-11-14'):
        return mastery_history(attempts, progress, {'tea': '茶', 'tea-sense': '茶', 'water': '水'},
                               today, ZoneInfo('America/New_York'), '2026-11-09')

    def event(self, number, day, item='tea', mode='flashcards', status='mastered'):
        return dict(id=number, item_id=item, mode=mode, created_at=f'2026-11-{day:02}T17:00:00+00:00',
                    progress={'status': status})

    def current(self, item='tea', mode='flashcards', status='mastered'):
        return dict(item_id=item, mode=mode, status=status, mastered_on='2026-11-09')

    def test_empty_history_has_zero_baseline_and_today(self):
        self.assertEqual(self.history(), [{'date': '2026-11-08', 'mastered': 0, 'drawing_mastered': 0},
                                         {'date': '2026-11-14', 'mastered': 0, 'drawing_mastered': 0}])

    def test_union_of_modes_and_senses_survives_partial_demotion(self):
        attempts = [self.event(1, 9), self.event(2, 10, mode='drawing'),
                    self.event(3, 10, item='tea-sense'),
                    self.event(4, 11, status='active'),
                    self.event(5, 12, mode='drawing', status='active'),
                    self.event(6, 13, item='tea-sense', status='active')]
        history = {p['date']: p['mastered'] for p in self.history(attempts)}
        self.assertEqual([history[f'2026-11-{day:02}'] for day in range(9, 15)], [1, 1, 1, 1, 0, 0])

    def test_daily_close_and_review_remain_mastered(self):
        attempts = [self.event(1, 9), self.event(2, 9, status='active'),
                    self.event(3, 10), self.event(4, 11, status='review')]
        history = {p['date']: p['mastered'] for p in self.history(attempts, [self.current(status='review')])}
        self.assertEqual(history['2026-11-09'], 0)
        self.assertEqual(history['2026-11-11'], 1)
        self.assertEqual(history['2026-11-14'], 1)

    def test_timestamps_use_local_calendar_day(self):
        attempt = dict(self.event(1, 10), created_at='2026-11-10T02:00:00+00:00')
        self.assertEqual(self.history([attempt], [self.current()])[1],
                         {'date': '2026-11-09', 'mastered': 1, 'drawing_mastered': 0})

    def test_legacy_mastery_and_authoritative_current_count(self):
        self.assertEqual(self.history(progress=[self.current()])[1],
                         {'date': '2026-11-09', 'mastered': 1, 'drawing_mastered': 0})
        self.assertEqual(self.history([self.event(1, 10)])[-1]['mastered'], 0)

    def test_drawing_counts_forms_once_and_demotes_independently(self):
        attempts = [self.event(1, 9), self.event(2, 10, mode='drawing'),
                    self.event(3, 10, item='tea-sense', mode='drawing'),
                    self.event(4, 11, mode='drawing', status='active'),
                    self.event(5, 12, item='tea-sense', mode='drawing', status='review'),
                    self.event(6, 13, item='tea-sense', mode='drawing', status='active')]
        history = self.history(attempts, [self.current()])
        self.assertEqual([p['drawing_mastered'] for p in history], [0, 0, 1, 1, 1, 0, 0])
        self.assertEqual([p['mastered'] for p in history], [0, 1, 1, 1, 1, 1, 1])

    def test_legacy_drawing_and_current_review_count(self):
        progress = [self.current(mode='drawing', status='review'),
                    self.current(item='tea-sense', mode='drawing'), self.current()]
        history = self.history(progress=progress)
        self.assertEqual(history[0]['drawing_mastered'], 0)
        self.assertEqual(history[1]['drawing_mastered'], 1)
        self.assertEqual(history[-1]['drawing_mastered'], 1)
        self.assertEqual(history[-1]['mastered'], 1)
        self.assertEqual(self.history([self.event(1, 10, mode='drawing')])[-1]['drawing_mastered'], 0)

    def test_drawing_daily_close_uses_local_day(self):
        attempts = [dict(self.event(1, 10, mode='drawing'), created_at='2026-11-10T02:00:00+00:00'),
                    dict(self.event(2, 10, mode='drawing', status='active'), created_at='2026-11-10T03:00:00+00:00')]
        self.assertEqual(self.history(attempts)[1],
                         {'date': '2026-11-09', 'mastered': 0, 'drawing_mastered': 0})
