"""Language content, dictionary indexing, and source-backed explanations."""
import gzip
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


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


def dictionary_rows():
    with gzip.open(DATA / "cedict.txt.gz", "rt", encoding="utf-8") as f:
        for line in f:
            match = re.match(r"^(\S+) (\S+) \[([^]]+)\] /(.+)/$", line.strip())
            if not match:
                continue
            traditional, simplified, reading, definitions = match.groups()
            taiwan = re.search(r"Taiwan pr\. \[([^]]+)\]", definitions)
            if taiwan:
                reading = taiwan.group(1)
            # References and classifiers are not English answers.
            meanings = [d for d in definitions.split("/") if not
                        re.match(r"(CL:|variant of|old variant|see |surname |Taiwan pr\.)", d)]
            if meanings:
                yield (traditional, simplified, tone_pinyin(reading),
                       plain_pinyin(reading), json.dumps(meanings, ensure_ascii=False))


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


def infer_topic(meanings):
    """Conservative local semantic tags; unrelated words stay in custom."""
    text = " ".join(meanings).lower()
    groups = {
        "clothing": ["clothes", "clothing", "shirt", "sweater", "sock", "jacket", "trousers", "pants", "shoe", "garment"],
        "technology": ["computer", "keyboard", "software", "telephone", "mobile phone", "internet", "electric", "network", "printer"],
        "food": ["food", "drink", "coffee", "tea", "milk", "rice", "bread", "fruit", "apple", "egg", "vegetable", "meat"],
        "travel": ["train", "bus", "metro", "station", "ticket", "airport", "flight", "transport", "vehicle"],
        "people": ["family", "friend", "student", "teacher", "school", "learn", "study", "book"],
    }
    scores = {topic:sum(bool(re.search(r"\b"+re.escape(word)+r"s?\b", text)) for word in words)
              for topic, words in groups.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "custom"
