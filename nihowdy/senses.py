"""Reviewed usage notes and conservative senses for automatic vocabulary."""
import re

from .vocabulary import reading_key


USAGE = {
    ('水果', 'shuǐguǒ'): (
        '水果 is the everyday word for fruit as food, such as fruit you buy or eat. '
        'Example: 我喜歡吃水果。 (I like eating fruit.)',
        'https://dict.concised.moe.edu.tw/dictView.jsp?ID=35642'),
    ('果實', 'guǒshí'): (
        '果實 refers to the fruit produced by a plant, and can also mean the results '
        'of work or effort. 水果 is the everyday food term. '
        'Example: 勝利的果實 (the fruits of victory).',
        'https://dict.concised.moe.edu.tw/dictView.jsp?ID=17069'),
    ('實', 'shí'): (
        '實 has senses such as real, solid, and substantial, usually in compounds '
        'in modern Mandarin. Its fruit/seed sense occurs in expressions such as 果實; '
        'use 水果 for everyday fruit as food.',
        'https://dict.concised.moe.edu.tw/dictView.jsp?ID=33409'),
}


def misleading_food_sense(text, pinyin, sense):
    return (text == '實' and reading_key(pinyin) == 'shí' and
            sense.strip().casefold() in {'fruit', 'fruits', 'seed', 'seeds'})


def automatic_sense(text, pinyin, meanings):
    """Use the leading dictionary sense, never mine later senses for a match.

    Dictionary order is only a conservative fallback, not a sense-frequency
    measurement. Annotated/complex first senses require explicit selection.
    """
    if not meanings:
        return None
    sense = meanings[0]
    if (len(sense) > 40 or not sense[:1].islower() or re.search(r'[()\[\];]', sense)
            or misleading_food_sense(text, pinyin, sense)):
        return None
    return sense


def with_usage_note(item):
    note = USAGE.get((item['text'], reading_key(item['pinyin']))) if item['kind'] == 'word' else None
    if not note:
        return item
    item = dict(item, usage_note=note[0], sources=list(item.get('sources', [])))
    if not any(source['url'] == note[1] for source in item['sources']):
        item['sources'].append({'title': 'Taiwan MOE: word usage', 'url': note[1]})
    return item
