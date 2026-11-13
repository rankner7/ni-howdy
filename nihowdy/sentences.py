"""Offline, attributed Tatoeba sentences shared by examples and practice."""
from functools import lru_cache
import gzip
import json
from pathlib import Path

from .phrases import eligible

ENGINE = 'tatoeba-v1'


@lru_cache(maxsize=1)
def corpus():
    with gzip.open(Path(__file__).resolve().parent.parent/'data/sentences.json.gz', 'rt', encoding='utf-8') as source:
        return json.load(source)


def sources(record):
    return [dict(title='Tatoeba via ManyThings.org · ' + attribution,
                 url='https://tatoeba.org/en/sentences/show/' + record['sentence_id'])
            for attribution in record['attribution']]


def examples(word):
    matches = [r for r in corpus() if word['text'] in r['tokens']]
    matches.sort(key=lambda r: (len(r['tokens']), len(r['text'])))
    return [dict(text=r['text'], pinyin=r['pinyin'], english=r['answers'][0],
                 sources=sources(r), note='Traditional Chinese adapted with OpenCC; pinyin generated locally.')
            for r in matches[:3]]


def candidates(items, mastered):
    forms = {}
    for item in items.values():
        if item['kind'] == 'word' and not item.get('deleted'):
            forms.setdefault(item['text'], []).append(item)
    for record in corpus():
        # Ambiguous catalog senses are withheld from scored practice.
        if any(len(forms.get(text, [])) != 1 for text in record['tokens']):
            continue
        tokens = [forms[text][0]['id'] for text in record['tokens']]
        if not eligible(tokens, mastered):
            continue
        yield dict(id='tatoeba:'+record['sentence_id'], kind='phrase', text=record['text'],
                   pinyin=record['pinyin'], english=record['answers'][0], answers=record['answers'],
                   chinese_answers=[record['text']], original_text=record['original'],
                   tokens=tokens, topic='custom', region='TW', script='Hant', status='ready',
                   characters=[], explanation='Corpus example from Tatoeba. Traditional Chinese adapted with OpenCC; pinyin and word boundaries generated locally. Regional usage and readings may vary.',
                   explanation_origin='Tatoeba contributors via ManyThings.org · CC BY 2.0 France',
                   phrase_engine=ENGINE, phrase_family='corpus', sources=sources(record))
