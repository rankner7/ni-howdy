"""Build the offline Tatoeba subset. Build dependencies: jieba, opencc-python-reimplemented, pypinyin.
Usage: .venv/bin/python scripts/build_sentences.py /path/to/cmn-eng.zip
"""
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

import jieba
from opencc import OpenCC
from pypinyin import pinyin, Style

root = Path(__file__).resolve().parent.parent
archive = Path(sys.argv[1])
converter = OpenCC('s2twp')
simplify = OpenCC('t2s')
records = {}
with zipfile.ZipFile(archive) as source:
    lines = source.read('cmn.txt').decode('utf-8-sig').splitlines()
    license_text = source.read('_about.txt').decode('utf-8-sig')
for line in lines:
    english, original, attribution = line.split('\t', 2)
    ids = re.findall(r'#(\d+) \(([^)]*)\)', attribution)
    if len(ids) != 2 or not 2 <= len(original) <= 80:
        continue
    text = converter.convert(original)
    if any(c.isascii() and c.isalnum() for c in text):
        continue
    tokens = [converter.convert(t) for t in jieba.cut(simplify.convert(text))
              if any('\u3400' <= c <= '\u9fff' for c in t)]
    # Conversion must preserve complete vocabulary boundaries.
    if ''.join(tokens) != ''.join(c for c in text if '\u3400' <= c <= '\u9fff'):
        continue
    key = (text, ids[1][0])
    record = records.setdefault(key, dict(text=text, original=original, tokens=tokens,
        pinyin=' '.join(s[0] for s in pinyin(text, style=Style.TONE, errors=lambda _: [])),
        answers=[], attribution=[], sentence_id=ids[1][0]))
    if english not in record['answers']: record['answers'].append(english)
    if attribution not in record['attribution']: record['attribution'].append(attribution)
with gzip.open(root/'data/sentences.json.gz', 'wt', encoding='utf-8') as out:
    json.dump(list(records.values()), out, ensure_ascii=False, separators=(',', ':'))
(root/'data/licenses/Tatoeba.txt').write_text(license_text + '\nSource archive SHA256: ' + hashlib.sha256(archive.read_bytes()).hexdigest() + '\nChinese adapted with OpenCC s2twp; pinyin and segmentation generated locally.\n', encoding='utf-8')
print(f'Prepared {len(records)} sentences')
