"""Language content, dictionary indexing, and source-backed explanations."""
import gzip
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from .topics import TOPIC_KEYWORDS, infer_topic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DICTIONARY_VERSION = '3'
LEGACY_AND_GLOSS = '(joining two nouns) and; together with; with (Taiwan pr. [han4])'
AND_USAGE = (
    '和 joins nouns: 蘋果和蛋 means apples and eggs. Hé and hàn are both used; '
    'hàn is a Taiwan pronunciation. 和 can also mean with in the pattern '
    '和……一起 (together with someone). It does not generally join complete clauses.'
)
AND_SOURCE = 'https://tocfl.edu.tw/assets/files/epaper/epaper87.pdf'


def load_hanzi():
    with gzip.open(DATA / "hanzi.json.gz", "rt") as f:
        return json.load(f)


def plain_pinyin(text):
    text = text.lower().replace("u:", "ü").replace("ü", "v")
    # Preserve ü after combining marks are decomposed.
    text = re.sub(r"u\u0308", "v", unicodedata.normalize("NFD", text))
    return "".join(c for c in text if c in "abcdefghijklmnopqrstuvwxyz")


def tone_pinyin(text):
    def convert(match):
        syllable, number = match.group(1).lower().replace("u:", "ü"), int(match.group(2))
        if number == 5:
            return syllable
        vowels = [i for i, c in enumerate(syllable) if c in "aeiouü"]
        if not vowels:
            return syllable
        index = (syllable.index("a") if "a" in syllable else
                 syllable.index("e") if "e" in syllable else
                 syllable.index("o") if "ou" in syllable else vowels[-1])
        table = dict(zip("aeiouü", ["āáǎà", "ēéěè", "īíǐì", "ōóǒò", "ūúǔù", "ǖǘǚǜ"]))
        return syllable[:index] + table[syllable[index]][number-1] + syllable[index+1:]
    return re.sub(r"([A-Za-züÜ:]+)([1-5])", convert, text)


def dictionary_readings(traditional, reading, definitions):
    """Keep inline pronunciation notes scoped to their own dictionary sense."""
    parts = definitions.split('/')
    regional = next((match for part in parts
                     if (match := re.fullmatch(r'Taiwan pr\. \[([^]]+)\]', part))), None)
    default = regional[1] if regional else reading
    groups = {}
    for sense in parts:
        if re.match(r'(CL:|variant of|old variant|see |surname |Taiwan pr\.)', sense):
            continue
        if traditional == '和' and reading.lower() == 'he2' and sense == LEGACY_AND_GLOSS:
            # Both readings are documented by Taiwan's TOCFL/NAER materials.
            # Put the common hé entry first, with plain selectable meanings.
            for pronunciation in ('he2', 'han4'):
                groups.setdefault(pronunciation, []).extend(['and', 'together with', 'with'])
            continue
        annotation = re.search(r'Taiwan pr\. \[([^]]+)\]', sense)
        pronunciation = annotation[1] if annotation else default
        if annotation:
            sense = re.sub(r'\s*\(?Taiwan pr\. \[[^]]+\]\)?', '', sense).strip()
        if sense:
            groups.setdefault(pronunciation, []).append(sense)
    return groups.items()


def dictionary_rows():
    with gzip.open(DATA / "cedict.txt.gz", "rt", encoding="utf-8") as f:
        for line in f:
            match = re.match(r"^(\S+) (\S+) \[([^]]+)\] /(.+)/$", line.strip())
            if not match:
                continue
            traditional, simplified, reading, definitions = match.groups()
            for pronunciation, meanings in dictionary_readings(traditional, reading, definitions):
                yield (traditional, simplified, tone_pinyin(pronunciation),
                       plain_pinyin(pronunciation), json.dumps(meanings, ensure_ascii=False))


def sources_for(text):
    return [
        {"title": "Taiwan Ministry of Education dictionary", "url": "https://www.moedict.tw/" + quote(text)},
        {"title": "CC-CEDICT dictionary", "url": "https://cc-cedict.org/wiki/"},
        {"title": "Make Me a Hanzi: character structure", "url": "https://github.com/skishore/makemeahanzi"},
    ]


def construction(text, hanzi):
    chars = []
    for ch in dict.fromkeys(text):
        data = hanzi.get(ch, {})
        etym = data.get("etymology") or {}
        description = etym.get("hint") or "No supported historical explanation is available in the local dataset."
        if etym.get("type") == "pictophonetic":
            description = (f"{etym.get('semantic') or 'The semantic component'} relates to meaning; "
                           f"{etym.get('phonetic') or 'the phonetic component'} supplies a sound clue. "
                           + (etym.get("hint") or "Sound relationships may have changed over time."))
        chars.append({"character": ch, "definition": data.get("definition", ""),
                      "decomposition": data.get("decomposition", ""),
                      "note": description, "kind": etym.get("type", "construction")})
    return chars


def component_groups(char, hanzi):
    data = hanzi.get(char, {})
    decomposition = data.get("decomposition", "")
    if not decomposition or decomposition[0] not in "⿰⿱⿲⿳" or "？" in decomposition:
        return []
    matches = data.get("matches", [])
    groups = {}
    for i, match in enumerate(matches):
        if match:
            groups.setdefault(match[0], []).append(i)
    # Every stroke must belong to a visible component; don't assemble partial glyphs.
    if len(groups) < 2 or sum(map(len, groups.values())) != len(data.get("strokes", [])):
        return []
    return [groups[k] for k in sorted(groups)]


def starter_items():
    return json.loads((DATA / "starter.json").read_text())
