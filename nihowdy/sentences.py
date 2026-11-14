"""Offline, attributed Tatoeba sentences shared by examples and practice."""
from functools import lru_cache
import gzip
import json
from pathlib import Path

from .phrases import eligible

ENGINE = 'tatoeba-v1'

# Sentence-by-sentence review, not a global love/like substitution. Preserve
# subjects, tense, intensifiers, relative clauses, and the imported alternatives.
PREFERENCE_TRANSLATIONS = {
    '湯姆喜歡你。': ('Tom likes you.',),
    '他非常喜歡音樂。': ('He likes music very much.',),
    '他們喜歡那個': ('They like that.',),
    '湯姆喜歡狗。': ('Tom likes dogs.',),
    '他喜歡火車。': ('He likes trains.',),
    '我喜歡燒烤食物。': ('I like barbecued food.', 'I like barbecue.'),
    '瑪麗，我喜歡你！': ('Mary, I like you.',),
    '湯姆喜歡曲棍球。': ('Tom likes hockey.',),
    '我喜歡那個故事。': ('I like that story.',),
    '湯姆喜歡香蕉。': ('Tom likes bananas.', 'Tom liked bananas.'),
    '我喜歡蘋果酒。': ('I like apple cider.',),
    '你為什麼喜歡我？': ('Why do you like me?',),
    '湯姆喜歡做這事。': ('Tom likes doing this.', 'Tom likes to do this.'),
    '我們喜歡吃蘋果。': ('We like eating apples.',),
    '我很喜歡我的黃色套衫。': ('I really like my yellow sweater.', 'I like my yellow sweater very much.'),
    '每一個人都喜歡那個地方。': ('Everyone likes that place.',),
    '河馬喜歡水。': ('Hippopotamuses like water.',),
    '我喜歡看電影。': ('I like watching movies.', 'I like to watch movies.', 'I like going to the movies.'),
    '湯姆在做他喜歡做的事。': ('Tom is doing what he likes.',),
    '我喜歡逗人笑。': ('I like to make people laugh.', 'I like making people laugh.'),
    '我喜歡冬天旅遊。': ('I like traveling in the winter.', 'I like to travel in the winter.'),
    '我女兒喜歡跳繩。': ('My daughter likes jumping rope.', 'My daughter likes to jump rope.'),
    '爹地喜歡講有趣的事。': ('Daddy likes to say funny things.', 'Daddy likes saying funny things.'),
    '孩子們喜歡在沙灘上玩。': ('Children like playing on the beach.', 'Children like to play on the beach.'),
    '我喜歡聖誕蛋糕上有草莓。': ('I like strawberries on Christmas cake.',),
    '我喜歡孩子們笑的聲音。': ('I like the sound of children laughing.',),
    '他喜歡喝啤酒，而且每天都喝醉。': ('He likes drinking beer and gets drunk every day.',),
    '我弟弟很喜歡拍山的照片。': ('My younger brother really likes to take photos of mountains.',),
    '我肯定你會喜歡我們今晚的菜餚。': ("I'm sure you'll like what we have on the menu tonight.",),
    '我的一個女性朋友喜歡跟我一起去同志酒吧。': ('A female friend of mine likes to go to gay bars with me.',),
    '湯姆和瑪莉的小兒子喜歡坐在廚房地板上敲打鍋碗瓢盆。':
        ("Tom and Mary's little boy likes sitting on the kitchen floor banging pots and pans.",),
}

# Reviewed teaching translations supplement the linked corpus translations.
REVIEWED_TRANSLATIONS = {
    # Tatoeba #13166880 directly links both #4980513 (present) and #9858945 (past).
    '我們吃蘋果。': 'We eat apples.',
    **{text: answers[0] for text, answers in PREFERENCE_TRANSLATIONS.items()},
}


def with_reviewed_translation(item):
    if item.get('kind') != 'phrase':
        return item
    primary = REVIEWED_TRANSLATIONS.get(item['text'])
    if not primary:
        return item
    return dict(item, english=primary, answers=translations(item))


def translations(record):
    primary = REVIEWED_TRANSLATIONS.get(record['text'])
    return list(dict.fromkeys([primary, *PREFERENCE_TRANSLATIONS.get(record['text'], ()),
                              *record['answers']])) if primary else record['answers']


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
