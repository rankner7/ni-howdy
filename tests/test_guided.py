"""Guided practice checks with isolated data, never the learner's database."""
import copy
import gzip
import io
import json
import random
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nihowdy.learning import guided_stroke_correct, transition
from nihowdy.store import Store
from nihowdy.taiwan import convert_character, load_taiwan
from nihowdy.vocabulary import VocabularyPolicy
from scripts.prepare_taiwan import prepare


WORDS = ['我', '你', '也', '要', '喝', '水', '茶', '好', '一', '二', '三', '電腦', '木', '一木']
GUIDE = {'strokes': ['M 100 200 L 800 200 L 800 230 L 100 230 Z',
                     'M 440 100 L 470 100 L 470 800 L 440 800 Z'],
         'medians': [[[100, 215], [800, 215]], [[455, 100], [455, 800]]]}
HANZI = {ch: {'strokes': GUIDE['strokes'], 'medians': GUIDE['medians']} for ch in ''.join(WORDS)}
ITEMS = [dict(id=w, text=w, kind='word', topic='essentials', pinyin='test', english=w,
              answers=[w], chinese_answers=[w], tokens=[], sources=[], characters=[])
         for w in WORDS]


def isolated_store(path):
    policy = VocabularyPolicy(counts={})
    # These fixtures represent words already admitted to practice. Keep the
    # progression checks independent of the vocabulary admission policy.
    policy.parts = lambda item, lookup: []
    with patch('nihowdy.store.load_hanzi', return_value=HANZI), \
         patch('nihowdy.store.starter_items', return_value=copy.deepcopy(ITEMS)), \
         patch('nihowdy.store.VocabularyPolicy', return_value=policy):
        store = Store(path, rng=random.Random(8))
    return store


class GuidedTests(unittest.TestCase):
    def next_prompt(self, mode):
        prompt = self.store.next_prompt(mode)
        while prompt.get('introduction'):
            self.store.answer(prompt['id'], {'continue': True})
            prompt = self.store.next_prompt(mode)
        return prompt

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'practice.sqlite'
        self.store = isolated_store(self.path)
        # Explicit fixture standards test behavior without claiming these
        # synthetic shapes are Taiwan character data.
        self.store.taiwan = {ch: copy.deepcopy(GUIDE) for ch in HANZI}
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            self.store._enroll(db, '電腦')
            db.execute("DELETE FROM progress WHERE mode!='drawing'")

    def answer(self, prompt):
        return {'drawings': [{'strokes': copy.deepcopy(p['guide']['medians'])}
                             for p in prompt['characters']]}

    def test_five_whole_words_persist_and_score_once(self):
        for repetition in range(1, 6):
            prompt = self.next_prompt('drawing')
            self.assertEqual(prompt['guided_completions'], repetition - 1)
            self.assertEqual(len(prompt['characters']), 2)
            self.assertEqual(self.next_prompt('drawing')['id'], prompt['id'])
            result = self.store.answer(prompt['id'], self.answer(prompt))
            self.assertTrue(result['correct'])
            self.assertEqual(result['progress']['guided_completions'], repetition)
            self.assertEqual(result['progress']['level'], 2 if repetition == 5 else 1)
            self.assertEqual(self.store.answer(prompt['id'], self.answer(prompt)), result)
            self.store = isolated_store(self.path)
            self.store.taiwan = {ch: copy.deepcopy(GUIDE) for ch in HANZI}
        prompt = self.next_prompt('drawing')
        self.assertEqual(prompt['level'], 2)
        self.assertIn('pinyin', prompt)
        self.assertNotIn('guide', prompt['characters'][0])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 5)

    def test_partial_word_does_not_count(self):
        prompt = self.next_prompt('drawing')
        answer = self.answer(prompt)
        answer['drawings'].pop()
        with self.assertRaisesRegex(ValueError, 'each character'):
            self.store.answer(prompt['id'], answer)
        self.assertEqual(self.next_prompt('drawing')['guided_completions'], 0)

    def test_components_advance_into_guided(self):
        self.store.hanzi = copy.deepcopy(HANZI)
        self.store.hanzi['我'].update(decomposition='⿰木木', matches=[[0], [1]])
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
            self.store._enroll(db, '我')
            db.execute("DELETE FROM progress WHERE mode!='drawing'")
        prompt = self.next_prompt('drawing')
        self.assertEqual(prompt['level'], 0)
        answer = {'drawings': [{'placements': [s['id'] for s in c['slots']]} for c in prompt['characters']]}
        result = self.store.answer(prompt['id'], answer)
        self.assertEqual(result['progress']['level'], 1)
        self.assertEqual(self.next_prompt('drawing')['guided_completions'], 0)

    def test_wrong_order_direction_omission_and_extra_ink_rejected(self):
        for change in ('reverse', 'swap', 'omit', 'extra'):
            with self.subTest(change=change):
                prompt = self.next_prompt('drawing')
                answer = self.answer(prompt)
                strokes = answer['drawings'][0]['strokes']
                if change == 'reverse': strokes[0].reverse()
                elif change == 'swap': strokes.reverse()
                elif change == 'omit': strokes.pop()
                else: strokes.append(strokes[0])
                self.assertFalse(self.store.answer(prompt['id'], answer)['correct'])

    def test_information_cannot_earn_repetition(self):
        prompt = self.next_prompt('drawing')
        self.store.info(prompt['id'])
        self.store.info(prompt['id'])
        result = self.store.answer(prompt['id'], self.answer(prompt))
        self.assertEqual(result['progress']['guided_completions'], 0)
        self.assertEqual(result['progress']['failures'], 1)
        self.assertTrue(result['answer_correct'])

    def test_completed_word_returns_to_random_pool(self):
        with self.store.db() as db:
            self.store._enroll(db, '我')
        first = self.next_prompt('drawing')
        self.store.answer(first['id'], self.answer(first))
        second = self.next_prompt('drawing')
        self.assertNotEqual(first['total_characters'], second['total_characters'])
        self.store.answer(second['id'], self.answer(second))
        third = self.next_prompt('drawing')
        self.assertEqual(third['total_characters'], first['total_characters'])
        self.assertEqual(third['guided_completions'], 1)

    def test_no_prc_fallback_when_taiwan_missing(self):
        self.store.taiwan = {}
        prompt = self.next_prompt('drawing')
        self.assertTrue(prompt['empty'])
        self.assertIn('Taiwan', prompt['message'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT level FROM progress').fetchone()[0], 1)

    def test_backup_roundtrip_and_old_backup_migration(self):
        prompt = self.next_prompt('drawing')
        self.store.answer(prompt['id'], self.answer(prompt))
        current = self.store.backup()
        self.store.restore(current)
        self.assertEqual(self.next_prompt('drawing')['guided_completions'], 1)
        legacy = copy.deepcopy(current)
        legacy['version'] = 1
        legacy['tables']['prompts'] = []
        legacy['tables']['attempts'] = []
        for setting in legacy['tables']['settings']:
            if setting['key'] == 'schema': setting['value'] = '1'
        for p in legacy['tables']['progress']:
            p.pop('guided_completions')
            p.update(level=3, status='mastered')
        self.store.restore(legacy)
        self.store = isolated_store(self.path)
        with self.store.db() as db:
            p = dict(db.execute('SELECT * FROM progress').fetchone())
        self.assertEqual((p['level'], p['status'], p['guided_completions']), (4, 'mastered', 5))

    def test_existing_database_and_pending_prompt_migrate_once(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2")
        prompt = self.next_prompt('drawing')
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=1")
            db.execute("UPDATE prompts SET level=1")
            db.execute("UPDATE settings SET value='1' WHERE key='schema'")
            db.execute('ALTER TABLE progress DROP COLUMN guided_completions')
        self.store = isolated_store(self.path)
        recovered = self.next_prompt('drawing')
        self.assertEqual((recovered['id'], recovered['level']), (prompt['id'], 2))
        self.store = isolated_store(self.path)
        self.assertEqual(self.next_prompt('drawing')['level'], 2)

    def test_later_drawing_levels_keep_cues_and_shape_grading(self):
        for level in (2, 3, 4):
            with self.store.db() as db:
                db.execute('UPDATE progress SET level=?', (level,))
                db.execute('UPDATE prompts SET finished=1')
            prompt = self.next_prompt('drawing')
            self.assertEqual('pinyin' in prompt, level == 2)
            with self.store.db() as db:
                plan = json.loads(db.execute('SELECT payload FROM prompts WHERE id=?', (prompt['id'],)).fetchone()[0])
            answer = {'drawings': [{'strokes': [[[x, 900-y] for x, y in reversed(HANZI[c['character']]['medians'][i])]
                                               for i in reversed(c['missing'])]} for c in plan['drawing']]}
            self.assertTrue(self.store.answer(prompt['id'], answer)['correct'])


class TraceTests(unittest.TestCase):
    def test_tolerance_and_bends(self):
        dot = [[100, 100], [130, 135]]
        self.assertTrue(guided_stroke_correct(dot, dot))
        self.assertFalse(guided_stroke_correct(list(reversed(dot)), dot))
        target = [[100, 100], [800, 100], [800, 800], [650, 700]]
        self.assertTrue(guided_stroke_correct([[x+20, y-15] for x,y in target], target))
        self.assertFalse(guided_stroke_correct(list(reversed(target)), target))
        self.assertFalse(guided_stroke_correct([target[0], target[-1]], target))
        self.assertFalse(guided_stroke_correct([target[0], target[0]], target))
        self.assertFalse(guided_stroke_correct([], target))
        self.assertFalse(guided_stroke_correct(target + list(reversed(target)) + target, target))

    def test_demotion_to_guided_starts_a_new_set(self):
        p = dict(level=2, failures=2, boost=0, attempts=5, status='active', guided_completions=5)
        p = transition(p, False, 0, 4, '2026-11-12', guided=True)
        self.assertEqual((p['level'], p['guided_completions']), (1, 0))

    def test_bundled_taiwan_direction_and_order(self):
        data = load_taiwan()
        self.assertEqual(len(data['我']['medians']), 7)
        # Taiwan 我: the dot precedes the final left-falling stroke.
        dot, falling = data['我']['medians'][-2:]
        self.assertGreater(dot[-1][0], dot[0][0])
        self.assertLess(falling[-1][0], falling[0][0])
        for entry in data.values():
            for stroke in entry['medians']:
                self.assertTrue(guided_stroke_correct(stroke, stroke))

    def test_importer_excludes_synthetic_entries(self):
        stroke = {'outline': [{'type': 'M', 'x': 100, 'y': 200}, {'type': 'L', 'x': 900, 'y': 200}],
                  'track': [{'x': 100, 'y': 200}, {'x': 900, 'y': 200}]}
        self.assertEqual(convert_character([stroke])['medians'][0][0], [51.2, 102.4])
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as target:
            for name, content in [('utf8/4e00.xml', b'<Stroke/>'),
                                  ('json/4e00.json', json.dumps([stroke]).encode()),
                                  ('json/6728.json', json.dumps([stroke]).encode())]:
                entry = tarfile.TarInfo('zh-stroke-data-master/' + name)
                entry.size = len(content)
                target.addfile(entry, io.BytesIO(content))
        archive.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'taiwan.json.gz'
            prepare(archive, output)
            with gzip.open(output, 'rt') as source:
                self.assertEqual(list(json.load(source)['characters']), ['一'])

    def test_importer_fits_outlying_controls_and_tracks_together(self):
        stroke = {
            'outline': [
                {'type': 'M', 'x': 100, 'y': 200},
                {'type': 'Q', 'begin': {'x': -100, 'y': 200}, 'end': {'x': 900, 'y': 200}},
                {'type': 'C', 'begin': {'x': 2100, 'y': 300},
                 'mid': {'x': 2100, 'y': 800}, 'end': {'x': 900, 'y': 900}},
            ],
            'track': [{'x': 100, 'y': -200}, {'x': 900, 'y': 2200}],
        }
        result = convert_character([stroke, stroke])
        # Expanded bounds are [-100,2100] x [-200,2200]. Both axes use
        # the same scale, with the narrower dimension centred in the square.
        self.assertEqual(result['medians'][0], [[128.0, 0.0], [469.333, 1024.0]])
        self.assertEqual(result['medians'][0], result['medians'][1])
        self.assertIn('M128.0 170.667', result['strokes'][0])
        self.assertIn('Q42.667 170.667 469.333 170.667', result['strokes'][0])
        self.assertIn('C981.333 213.333 981.333 426.667 469.333 469.333', result['strokes'][0])
        self.assertTrue(guided_stroke_correct(result['medians'][0], result['medians'][0]))

    def test_archive_import_retains_outlying_geometry_and_reports_bad_coordinates(self):
        # Synthetic fixtures exercise the full archive-to-asset path. These
        # shapes do not claim to represent the named characters' real glyphs.
        valid = {'outline': [{'type': 'M', 'x': -50, 'y': 200},
                             {'type': 'Q', 'begin': {'x': 2050, 'y': 300},
                              'end': {'x': 900, 'y': 400}}],
                 'track': [{'x': 100, 'y': 200}, {'x': 900, 'y': 400}]}
        invalid = copy.deepcopy(valid)
        invalid['track'][0]['x'] = float('nan')
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as target:
            for code, stroke in [('4e00', valid), ('4e8c', invalid)]:
                for name, content in [('utf8/' + code + '.xml', b'<Stroke/>'),
                                      ('json/' + code + '.json', json.dumps([stroke]).encode())]:
                    entry = tarfile.TarInfo('zh-stroke-data-master/' + name)
                    entry.size = len(content)
                    target.addfile(entry, io.BytesIO(content))
        archive.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'taiwan.json.gz'
            messages = io.StringIO()
            with redirect_stdout(messages):
                prepare(archive, output)
            with gzip.open(output, 'rt') as source:
                document = json.load(source)
            self.assertEqual(document['characters'], {'一': convert_character([valid])})
            self.assertIn('Excluded 1 characters', messages.getvalue())
            self.assertIn('二: Invalid Taiwan stroke coordinate in stroke 1', messages.getvalue())

    def test_importer_preserves_nominal_geometry(self):
        stroke = {'outline': [{'type': 'M', 'x': 0, 'y': 0}, {'type': 'L', 'x': 2000, 'y': 2000}],
                  'track': [{'x': 100, 'y': 200}, {'x': 900, 'y': 200}]}
        result = convert_character([stroke])
        self.assertEqual(result['strokes'], ['M0.0 0.0 L1024.0 1024.0 Z'])
        self.assertEqual(result['medians'], [[[51.2, 102.4], [460.8, 102.4]]])

    def test_importer_still_rejects_invalid_numbers(self):
        for bad in (float('nan'), float('inf'), -float('inf'), '200', None, True):
            for field in ('track', 'outline'):
                with self.subTest(value=bad, field=field):
                    stroke = {'outline': [{'type': 'M', 'x': 100, 'y': 200}],
                              'track': [{'x': 100, 'y': 200}, {'x': 900, 'y': 200}]}
                    stroke[field][0]['x'] = bad
                    with self.assertRaisesRegex(ValueError, 'stroke 1.*finite numbers'):
                        convert_character([stroke])
