"""Taxonomy boundaries and lossless upgrades of existing libraries."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.content import starter_items
from nihowdy.store import Store
from nihowdy.topics import TOPICS, infer_topic
from nihowdy.vocabulary import VocabularyPolicy


class TopicTests(unittest.TestCase):
    def test_subject_boundaries(self):
        examples = {
            'people': ['I', 'friend', 'happy', 'to like'],
            'food': ['tea', 'to eat', 'water'],
            'home': ['home', 'kitchen', 'furniture'],
            'health': ['brain', 'hand', 'pain', 'thirsty'],
            'nature': ['rain', 'cat', 'tree'],
            'travel': ['train', 'ticket', 'to go'],
            'shopping': ['to buy', 'bank', 'goods', 'to put goods on shelves', 'classifier for small amounts'],
            'school': ['student', 'teacher', 'book', 'to learn', 'to train', 'to teach; to train; to admonish'],
            'work': ['job', 'engineer', 'office'],
            'technology': ['computer mouse', 'telephone', 'software'],
            'clothing': ['shirt', 'red', 'shoes'],
            'time': ['one', 'tomorrow', 'hour'],
            'actions': ['to be', 'good', 'small', 'also', 'to use'],
            'leisure': ['sport', 'festival', 'music', 'baseball', 'volleyball'],
            'custom': ['unclassified xyz'],
        }
        self.assertEqual(len(TOPICS), 14)
        for topic, meanings in examples.items():
            for meaning in meanings:
                with self.subTest(meaning=meaning):
                    self.assertEqual(infer_topic([meaning]), topic)


class TopicMigrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'test.sqlite'
        self.catalog = starter_items()
        self.hanzi = {c: {} for item in self.catalog for c in item['text']}
        self.store = self.open_store()

    def open_store(self):
        with patch('nihowdy.store.load_hanzi', return_value=self.hanzi), \
             patch('nihowdy.store.load_taiwan', return_value={}), \
             patch('nihowdy.store.VocabularyPolicy', return_value=VocabularyPolicy({})):
            return Store(self.path)

    def legacy_backup(self):
        backup = self.store.backup()
        tables = backup['tables']
        tables['settings'] = [row for row in tables['settings'] if row['key'] != 'taxonomy_version']
        for row in tables['settings']:
            if row['key'] == 'interests':
                row['value'] = '["people","essentials"]'
        for row in tables['items']:
            item = json.loads(row['data'])
            item.pop('collections', None)
            if item['id'] in {'我', '好', '一'}:
                item['topic'] = 'essentials'
            elif item['id'] in {'腦', '手'}:
                item['topic'] = 'technology'
            elif item['id'] in {'書', '學生'}:
                item['topic'] = 'people'
            elif item['id'] == '買':
                item['topic'] = 'travel'
            row['data'] = json.dumps(item, ensure_ascii=False)
        for identifier, meaning, topic in [('saved-health', 'toe', 'technology'),
                                            ('saved-custom', 'rain', 'custom'),
                                            ('saved-subject', 'rain', 'gardening')]:
            item = dict(self.catalog[0], id=identifier, english=meaning,
                        answers=[meaning, 'computer'], topic=topic, deleted=True)
            tables['items'].append(dict(id=identifier, data=json.dumps(item)))
        tables['expansions'].append(dict(item_id='好', added='["大"]'))
        return backup

    def assert_migrated(self, legacy):
        backup = self.store.backup()
        for table in ('progress', 'sessions', 'prompts', 'attempts', 'trials', 'expansions', 'pending'):
            self.assertEqual(backup['tables'][table], legacy['tables'][table], table)
        items = {row['id']: json.loads(row['data']) for row in backup['tables']['items']}
        for identifier, topic in {'我': 'people', '好': 'actions', '一': 'time',
                                  '腦': 'health', '手': 'health', '買': 'shopping',
                                  '學生': 'school', '書': 'school',
                                  'saved-health': 'health', 'saved-custom': 'nature',
                                  'saved-subject': 'gardening'}.items():
            self.assertEqual(items[identifier]['topic'], topic, identifier)
        self.assertIn('essentials', items['我']['collections'])
        self.assertTrue(items['saved-health']['deleted'])
        with self.store.db() as db:
            self.assertEqual(self.store._settings(db)['interests'], ['people', 'essentials', 'school'])
        return backup

    def test_old_backup_migrates_without_changing_learning_records(self):
        legacy = self.legacy_backup()
        self.store.restore(copy.deepcopy(legacy))
        upgraded = self.assert_migrated(legacy)
        self.store.restore(copy.deepcopy(upgraded))
        self.assertEqual(self.store.backup(), upgraded)

    def test_startup_migrates_once(self):
        legacy = self.legacy_backup()
        with self.store.db() as db:
            db.execute("DELETE FROM settings WHERE key='taxonomy_version'")
            db.execute("UPDATE settings SET value='[\"people\",\"essentials\"]' WHERE key='interests'")
            db.execute('DELETE FROM items')
            db.executemany('INSERT INTO items VALUES (:id,:data)', legacy['tables']['items'])
            db.execute('INSERT INTO expansions VALUES (?,?)', ('好', '["大"]'))
        self.store = self.open_store()
        upgraded = self.assert_migrated(legacy)
        self.store = self.open_store()
        self.assertEqual(self.store.backup(), upgraded)

    def test_collection_generation_retains_subjects_and_ignores_unrelated_words(self):
        self.store.vocabulary = VocabularyPolicy({'他': 100, '毛衣': 1000})
        result = self.store.generate_entries({'source': 'category', 'category': 'essentials', 'count': 2})
        self.assertEqual([(item['text'], item['topic']) for item in result['items']], [('他', 'people')])

    def test_interest_collection_matches_membership(self):
        with self.store.db() as db:
            db.execute('DELETE FROM progress')
        self.store.update_settings({'interests': ['essentials']})
        enrolled = [item for item in self.store.state()['items'] if item['enrolled']]
        self.assertTrue(enrolled)
        self.assertTrue(all('essentials' in item.get('collections', []) for item in enrolled))
        self.assertTrue(all(item['topic'] != 'essentials' for item in enrolled))
