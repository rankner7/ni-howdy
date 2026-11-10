"""Local Taiwan Mandarin speech with explicit dictionary readings and caching."""
import hashlib
import re
import threading
import wave
from pathlib import Path


class Audio:
    def __init__(self, data_dir):
        self.directory = Path(data_dir)
        self.model_path = self.directory / "models/primetts.onnx"
        self.cache = self.directory / "audio"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = None
        self.lock = threading.Lock()

    def available(self):
        try:
            import onnxruntime  # noqa: F401
            import pypinyin  # noqa: F401
            return self.model_path.exists()
        except ImportError:
            return False

    def render(self, item):
        key = hashlib.sha256(("primetts-v21-pinyin-v1:"+item["text"]+":"+item["pinyin"]).encode()).hexdigest()
        output = self.cache / (key+".wav")
        if output.exists():
            return output
        if not self.available():
            raise ValueError("Local audio is not installed. Run ./setup.sh, then ./run.sh. Your answer has not been scored.")
        with self.lock:
            if output.exists():
                return output
            import numpy as np
            import onnxruntime as ort
            from pypinyin.style.bopomofo import converter
            if self.session is None:
                options = ort.SessionOptions()
                options.intra_op_num_threads = 2
                self.session = ort.InferenceSession(str(self.model_path), sess_options=options,
                                                    providers=["CPUExecutionProvider"])
            symbols = (["_blank", "_pad", "UNK", "SP"] + [chr(c) for c in range(0x3105, 0x312A)] +
                       ['AA','AE','AH','AO','AW','AY','B','CH','D','DH','EH','ER','EY','F','G','HH',
                        'IH','IY','JH','K','L','M','N','NG','OW','OY','P','R','S','SH','T','TH',
                        'UH','UW','V','W','Y','Z','ZH'] + [',','.', '?', '!', '…', '-', "'", 'ㄭ'])
            syllables = re.findall(r"[a-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+", item["pinyin"].lower())
            phones, tones = [], []
            parsed = []
            for syllable in syllables:
                bopo = converter.to_bopomofo(syllable)
                tone = next((n for mark, n in [("ˊ",2),("ˇ",3),("ˋ",4),("˙",5)] if mark in bopo), 1)
                units = [c for c in bopo if c in symbols]
                if len(units) == 1 and units[0] in "ㄓㄔㄕㄖㄗㄘㄙ":
                    units.append("ㄭ")
                if not units:
                    raise ValueError("This entry needs a valid Mandarin reading before audio can be generated.")
                parsed.append((units, tone))
            for index, (units, tone) in enumerate(parsed):
                # Surface third-tone sandhi; stored teaching pinyin retains dictionary tones.
                if tone == 3 and index+1 < len(parsed) and parsed[index+1][1] == 3:
                    tone = 2
                for unit in units:
                    phones.append(symbols.index(unit))
                    tones.append(tone)
            phones.append(symbols.index('.'))
            tones.append(0)
            def blank(values):
                return np.array([[0] + [v for x in values for v in (x, 0)]], np.int64)
            wav = self.session.run(None, {"x":blank(phones), "tone":blank(tones), "lang":blank([0]*len(phones)),
                       "x_lengths":np.array([2*len(phones)+1], np.int64), "sid":np.array([0], np.int64),
                       "noise_scale":np.array([.667], np.float32), "length_scale":np.array([1.05], np.float32)})[0].reshape(-1)
            samples = (np.clip(wav, -1, 1)*32767).astype('<i2')
            temporary = output.with_suffix('.tmp')
            with wave.open(str(temporary), 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(samples.tobytes())
            temporary.replace(output)
        return output
