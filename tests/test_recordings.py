import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.setup_recordings import recording_items
from nihowdy.recordings import load_index, recording_id, save_recording


class RecordingItemsTests(unittest.TestCase):
    def test_reference_readings_preserve_tones_and_regional_labels(self):
        try:
            import pypinyin  # noqa: F401
        except ImportError:
            self.skipTest('Optional pinyin dependency is not installed')
        index=load_index()
        self.assertEqual(recording_id({'text':'嗎','pinyin':'ma'},index),'0541')
        self.assertEqual(recording_id({'text':'的','pinyin':'de'},index),'1020')
        self.assertEqual(recording_id({'text':'車','pinyin':'chē'},index),'4668')
        self.assertEqual(recording_id({'text':'車','pinyin':'jū'},index),'3414')
        self.assertEqual(recording_id({'text':'學','pinyin':'xue\u0301'},index),'4150')
        self.assertIsNone(recording_id({'text':'學','pinyin':'xuè'},index))

    def test_saving_recordings_preserves_other_readings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            save_recording(root,('學|xué',{'file':'4150.mp3'}))
            save_recording(root,('聲|shēng',{'file':'5091.mp3'}))
            self.assertEqual(len(json.loads((root/'index.json').read_text())),2)

    def test_library_characters_are_prepared_with_their_stored_readings(self):
        with tempfile.TemporaryDirectory() as directory:
            with sqlite3.connect(Path(directory)/'nihowdy.sqlite') as connection:
                connection.execute('CREATE TABLE items(data TEXT)')
                items=[
                    {'kind':'word','text':'聲','pinyin':'shēng'},
                    {'kind':'word','text':'聲','pinyin':'shēng'},
                    {'kind':'word','text':'好','pinyin':'hào'},
                    {'kind':'word','text':'聲音','pinyin':'shēng yīn'},
                    {'kind':'phrase','text':'好','pinyin':'hǎo'},
                ]
                connection.executemany('INSERT INTO items VALUES (?)',[(json.dumps(i),) for i in items])
            readings=[(i['text'],i['pinyin']) for i in recording_items(directory,'聲好')]
            self.assertEqual(readings.count(('聲','shēng')),1)
            self.assertIn(('好','hǎo'),readings)
            self.assertIn(('好','hào'),readings)
            self.assertEqual(len(readings),3)

    def test_fresh_setup_uses_starters_without_creating_a_database(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(recording_items(directory,'我好'))
            self.assertFalse((Path(directory)/'nihowdy.sqlite').exists())


if __name__=='__main__':
    unittest.main()
