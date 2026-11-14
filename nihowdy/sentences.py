"""Offline, attributed Tatoeba sentences shared by examples and practice."""
from functools import lru_cache
import gzip
import json
from pathlib import Path

from .phrases import eligible

ENGINE = 'tatoeba-v1'

# Reviewed teaching translations supplement the linked corpus translations.
REVIEWED_TRANSLATIONS = {'他喜歡火車。': 'He likes trains.'}


def with_reviewed_translation(item):
    if item.get('kind') != 'phrase':
        return item
    primary = REVIEWED_TRANSLATIONS.get(item['text'])
    if not primary:
        return item
    return dict(item, english=primary, answers=translations(item))


def translations(record):
    primary = REVIEWED_TRANSLATIONS.get(record['text'])
    return list(dict.fromkeys([primary, *record['answers']])) if primary else record['answers']


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
    return [dict(text=r['text'], pinyin=r['pinyin'], english=translations(r)[0],
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
        answers = translations(record)
        yield dict(id='tatoeba:'+record['sentence_id'], kind='phrase', text=record['text'],
                   pinyin=record['pinyin'], english=answers[0], answers=answers,
                   chinese_answers=[record['text']], original_text=record['original'],
                   tokens=tokens, topic='custom', region='TW', script='Hant', status='ready',
                   characters=[], explanation='Corpus example from Tatoeba. Traditional Chinese adapted with OpenCC; pinyin and word boundaries generated locally. Regional usage and readings may vary.',
                   explanation_origin='Tatoeba contributors via ManyThings.org · CC BY 2.0 France',
                   phrase_engine=ENGINE, phrase_family='corpus', sources=sources(record))
