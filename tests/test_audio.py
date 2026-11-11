import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from nihowdy.audio import Audio


class AudioTests(unittest.TestCase):
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
