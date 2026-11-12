"""Corpus-based vocabulary addition weights and normalized reading keys."""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import unicodedata

DATA=Path(__file__).resolve().parent.parent/'data'
ADDITION_FREQUENCY_EXPONENT = 1.5


@lru_cache(maxsize=1)
def frequency_data():
    with gzip.open(DATA/'word-frequency.json.gz','rt') as source:
        return json.load(source)


def reading_key(pinyin):
    return ''.join(unicodedata.normalize('NFC',pinyin).lower().split())


class VocabularyPolicy:
    def __init__(self, counts=None):
        self.counts=frequency_data()['counts'] if counts is None else counts

    def frequency_count(self, text):
        """Raw observed occurrences, used for display and lexical evidence."""
        return self.counts.get(text,0)

    def addition_weight(self, text):
        """Favor common words more strongly when sampling new additions."""
        return self.frequency_count(text) ** ADDITION_FREQUENCY_EXPONENT
