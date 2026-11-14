import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nihowdy.audio import Audio


class AudioTests(unittest.TestCase):
    def test_new_character_fetches_recording_before_using_cached_synthesis(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Audio(directory)
            item={'text':'學','pinyin':'xué'}
            key=hashlib.sha256('primetts-v21-pinyin-v1:學:xué'.encode()).hexdigest()
            (audio.cache/(key+'.wav')).write_bytes(b'old-inaccurate-audio')
            def prepare(item, root, index):
                (root/'4150.mp3').write_bytes(b'ID3recording')
                return '學|xué',{'file':'4150.mp3','start':0,'end':.69}
            with patch('nihowdy.audio.recording_id',return_value='4150'), patch('nihowdy.audio.prepare',side_effect=prepare) as fetch:
                result=audio.render(item)
                self.assertEqual(result.name,'4150.mp3')
                self.assertEqual(audio.render(item),result)
                fetch.assert_called_once()
            self.assertIn('Ministry of Education',audio.playback(item)['source'])

    def test_unavailable_recording_falls_back_without_repeated_downloads(self):
        import subprocess
        for error in (OSError('offline'), ValueError('unsafe clip'), subprocess.CalledProcessError(28,['curl'])):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                audio=Audio(directory)
                item={'text':'學','pinyin':'xué'}
                key=hashlib.sha256('primetts-v21-pinyin-v1:學:xué'.encode()).hexdigest()
                cached=audio.cache/(key+'.wav')
                cached.write_bytes(b'cached-synthesis')
                with patch('nihowdy.audio.recording_id',return_value='4150'), patch('nihowdy.audio.prepare',side_effect=error) as fetch:
                    self.assertEqual(audio.render(item),cached)
                    self.assertEqual(audio.render(item),cached)
                    fetch.assert_called_once()
                root=audio.cache/'recordings'
                (root/'4150.mp3').write_bytes(b'ID3recording')
                (root/'index.json').write_text(json.dumps({'學|xué':{'file':'4150.mp3','start':0,'end':.69}}))
                self.assertEqual(audio.render(item).name,'4150.mp3')

    def test_unindexed_word_keeps_synthesis_without_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Audio(directory)
            item={'text':'你好','pinyin':'nǐ hǎo'}
            key=hashlib.sha256('primetts-v21-pinyin-v1:你好:nǐ hǎo'.encode()).hexdigest()
            cached=audio.cache/(key+'.wav')
            cached.write_bytes(b'cached-synthesis')
            with patch('nihowdy.audio.prepare') as fetch:
                self.assertEqual(audio.render(item),cached)
                fetch.assert_not_called()

    def test_failed_recording_is_retried_on_later_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Audio(directory)
            item={'text':'學','pinyin':'xué'}
            with patch('nihowdy.audio.recording_id',return_value='4150'), patch('nihowdy.audio.prepare',side_effect=OSError('offline')) as fetch, patch('nihowdy.audio.time.monotonic',side_effect=[0,1,301]):
                self.assertIsNone(audio.prepare_recording(item))
                self.assertIsNone(audio.prepare_recording(item))
                self.assertIsNone(audio.prepare_recording(item))
                self.assertEqual(fetch.call_count,2)

    def test_reading_specific_recording_overrides_old_synthesis(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Audio(directory)
            root=Path(directory)/'audio/recordings'
            root.mkdir()
            clip=root/'2727.mp3'
            clip.write_bytes(b'ID3original-recording')
            (root/'index.json').write_text(json.dumps({'好|hǎo':{'file':clip.name,'start':0,'end':.7}}))
            key=hashlib.sha256('primetts-v21-pinyin-v1:好:hǎo'.encode()).hexdigest()
            (audio.cache/(key+'.wav')).write_bytes(b'old-inaccurate-audio')
            self.assertEqual(audio.render({'text':'好','pinyin':'hǎo'}),clip)
            self.assertEqual(audio.playback({'text':'好','pinyin':'hǎo'})['end'],.7)
            self.assertIsNone(audio.recording({'text':'好','pinyin':'hào'}))

    def test_recording_path_cannot_escape_recording_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Audio(directory)
            root=audio.cache/'recordings'
            root.mkdir()
            (root/'index.json').write_text(json.dumps({'我|wǒ':{'file':'../../other.mp3','start':0,'end':1}}))
            self.assertIsNone(audio.recording({'text':'我','pinyin':'wǒ'}))


if __name__=='__main__':
    unittest.main()
