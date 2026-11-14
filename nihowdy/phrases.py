"""Offline sentence construction with explicit lexical roles and grammar patterns.

Slots are resolved to real vocabulary IDs/readings, not individual Hanzi. Content
verbs and objects must be mastered; longer patterns may introduce a function word.
"""
import unicodedata
import re
from itertools import combinations

from .vocabulary import reading_key

ENGINE_VERSION = 'local-v3'


def phrase_key(text):
    """Punctuation/spacing variants are the same sentence for generation history."""
    return ''.join(c for c in unicodedata.normalize('NFC', text)
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def eligible(tokens, mastered):
    # Strictly MORE than 80%; use integers so the boundary is exact.
    return len(tokens) > 1 and 5 * sum(t in mastered for t in tokens) > 4 * len(tokens)


# Curated senses keep buying, eating, drinking, reading and wearing distinct.
# Each mapping is text: (expected reading, English object phrase).
DRINKS = {
    '水': ('shuǐ', 'water'), '茶': ('chá', 'tea'), '咖啡': ('kā fēi', 'coffee'),
    '牛奶': ('niú nǎi', 'milk'), '豆漿': ('dòu jiāng', 'soy milk'),
    '果汁': ('guǒ zhī', 'juice'), '紅茶': ('hóng chá', 'black tea'),
    '綠茶': ('lǜ chá', 'green tea'), '啤酒': ('pí jiǔ', 'beer'),
}
FOODS = {
    '米飯': ('mǐ fàn', 'rice'), '飯': ('fàn', 'rice'), '麵包': ('miàn bāo', 'bread'),
    '水果': ('shuǐ guǒ', 'fruit'), '蘋果': ('píng guǒ', 'apples'),
    '蛋': ('dàn', 'eggs'), '雞蛋': ('jī dàn', 'eggs'), '麵': ('miàn', 'noodles'),
    '魚': ('yú', 'fish'), '牛肉': ('niú ròu', 'beef'), '雞肉': ('jī ròu', 'chicken'),
}
CLOTHES = {
    '襪子': ('wà zi', 'socks'), '衣服': ('yī fú', 'clothes'),
    '毛衣': ('máo yī', 'a sweater'), '上衣': ('shàng yī', 'a top'),
    '襯衫': ('chèn shān', 'a shirt'), '褲子': ('kù zi', 'trousers'),
    '鞋子': ('xié zi', 'shoes'), '外套': ('wài tào', 'a coat'),
}
BOOKS = {'書': ('shū', 'a book'), '報紙': ('bào zhǐ', 'a newspaper')}
GOODS = {
    **DRINKS, **FOODS, **CLOTHES, **BOOKS,
    '電腦': ('diàn nǎo', 'a computer'), '手機': ('shǒu jī', 'a mobile phone'),
    '電話': ('diàn huà', 'a telephone'), '電視': ('diàn shì', 'a television'),
    '鍵盤': ('jiàn pán', 'a keyboard'), '滑鼠': ('huá shǔ', 'a computer mouse'),
    '票': ('piào', 'a ticket'),
}
LANGUAGES = {'中文': ('zhōng wén', 'Chinese'), '英文': ('yīng wén', 'English'),
             '日文': ('rì wén', 'Japanese')}
PLACES = {
    '家': ('jiā', 'home'), '學校': ('xué xiào', 'school'),
    '車站': ('chē zhàn', 'the station'), '書店': ('shū diàn', 'the bookshop'),
    '咖啡店': ('kā fēi diàn', 'the coffee shop'), '公園': ('gōng yuán', 'the park'),
    '餐廳': ('cān tīng', 'the restaurant'),
}
SUBJECTS = {'我': ('wǒ', 'I'), '你': ('nǐ', 'You'), '他': ('tā', 'He'),
            '她': ('tā', 'She'), '我們': ('wǒ men', 'We'), '你們': ('nǐ men', 'You'),
            '他們': ('tā men', 'They')}
ROLES = {'人': ('rén', 'person'), '學生': ('xué shēng', 'student'),
         '老師': ('lǎo shī', 'teacher'), '朋友': ('péng yǒu', 'friend')}
PLURAL_IDENTITY = re.compile(r'^(我們|你們|他們)(也|不)?是(好)?(人|學生|老師|朋友)$')
DEVICES = {text: GOODS[text] for text in ('電腦', '手機', '電話', '電視', '鍵盤', '滑鼠')}
# Keep coordinated objects in the same semantic group. In particular, avoid
# treating a person as a possession or using a literal 大人/小人 as big/small person.
OBJECT_GROUPS = (DRINKS, FOODS, CLOTHES, BOOKS, DEVICES)
SIZED = {text: GOODS[text] for text in ('電腦', '手機', '電話', '電視', '鍵盤', '滑鼠',
                                      '書', '毛衣', '襯衫', '外套', '蘋果', '蛋')}
SIZED.update({'蘋果': ('píng guǒ', 'an apple'), '蛋': ('dàn', 'an egg')})
ADJECTIVES = {'大': ('dà', 'big'), '小': ('xiǎo', 'small')}
FUNCTIONS = {
    '要': ('yào', 'want'), '想': ('xiǎng', 'want'), '喜歡': ('xǐ huān', 'like'),
    '可以': ('kě yǐ', 'can'), '也': ('yě', 'also'), '不': ('bù', 'not'),
    '嗎': ('ma', ''), '今天': ('jīn tiān', 'today'), '明天': ('míng tiān', 'tomorrow'),
    '在': ('zài', 'at'), '和': ('hé', 'and'),
    '的': ('de', 'possessive particle'), '很': ('hěn', ''),
}
ACTIONS = [
    ('喝', 'hē', 'drink', 'drinking', DRINKS),
    ('吃', 'chī', 'eat', 'eating', FOODS),
    ('買', 'mǎi', 'buy', 'buying', GOODS),
    ('看', 'kàn', 'read', 'reading', BOOKS),
    ('學', 'xué', 'study', 'studying', LANGUAGES),
    ('穿', 'chuān', 'wear', 'wearing', CLOTHES),
]


def role_description(noun, plural=False, good=False):
    if plural:
        noun = 'people' if noun == 'person' else noun + 's'
    return ('' if plural else 'a ') + ('good ' if good else '') + noun


def with_identity_agreement(item):
    """Repair saved automatic identities without changing custom/corpus phrases."""
    if item.get('kind') != 'phrase' or not (item.get('phrase_engine') or '').startswith('local-'):
        return item
    match = PLURAL_IDENTITY.fullmatch(phrase_key(item['text']))
    if not match:
        return item
    subject, modifier, good, role = match.groups()
    name, noun = SUBJECTS[subject][1], ROLES[role][1]
    adverb = {'也': 'also ', '不': 'not ', None: ''}[modifier]
    english = f'{name} are {adverb}{role_description(noun, plural=True, good=bool(good))}.'
    malformed = f'{name} are {adverb}{role_description(noun, good=bool(good))}.'
    def key(answer):
        return answer.strip().rstrip('.!?').casefold()
    answers = list(dict.fromkeys([english, *(a for a in item['answers'] if key(a) != key(malformed))]))
    return dict(item, english=english, answers=answers)


def candidates(items, mastered):
    """Yield diverse, source-resolved sentences that meet the mastery contract."""
    forms = {}
    for item in items.values():
        if item['kind'] == 'word' and not item.get('deleted'):
            forms.setdefault((item['text'], reading_key(item['pinyin'])), []).append(item)

    def resolve(text, reading, known=False):
        matches = forms.get((text, reading_key(reading)), [])
        # Prefer the mastered sense if the same form has multiple catalog entries.
        matches = sorted(matches, key=lambda i: (i['id'] not in mastered, i['id']))
        return next((i for i in matches if not known or i['id'] in mastered), None)

    def slots(mapping, known=False):
        return [(entry, english) for text, (reading, english) in mapping.items()
                if (entry := resolve(text, reading, known))]

    functions = {text: resolve(text, reading) for text, (reading, _) in FUNCTIONS.items()}
    subjects = slots(SUBJECTS, known=True)
    places = slots(PLACES, known=True)
    seen = set()

    def sentence(parts, english, family, explanation, question=False, clause_at=None,
                 alternatives=()):
        if any(part is None for part in parts):
            return None
        tokens = [part['id'] for part in parts]
        if not eligible(tokens, mastered):
            return None
        text = ''.join(('，' if index == clause_at else '') + part['text']
                       for index, part in enumerate(parts)) + ('？' if question else '。')
        key = phrase_key(text)
        if key in seen:
            return None
        seen.add(key)
        sources = {s['url']: s for part in parts for s in part.get('sources', [])}
        return dict(id='phrase:' + text, kind='phrase', text=text,
                    pinyin=' '.join(part['pinyin'] for part in parts), english=english,
                    answers=[english, *alternatives], chinese_answers=[text], tokens=tokens,
                    topic=parts[-1]['topic'], region='TW', script='Hant', status='ready',
                    characters=[], explanation=explanation,
                    explanation_origin='Generated locally from a constrained grammar pattern',
                    phrase_engine=ENGINE_VERSION, phrase_family=family, sources=list(sources.values()))

    for subject, name in subjects:
        third = name in ('He', 'She')
        plural_subject = subject['text'] in ('我們', '你們', '他們')
        be = 'am' if name == 'I' else 'is' if third else 'are'
        is_word = resolve('是', 'shì', known=True)
        have = resolve('有', 'yǒu', known=True)
        like = functions['喜歡']
        good = resolve('好', 'hǎo', known=True)
        for role, noun in slots(ROLES, known=True):
            yield sentence([subject, is_word, role], f'{name} {be} {role_description(noun, plural_subject)}.',
                           'identity', 'Subject + 是 + noun identifies a person.')
        for role, noun in slots(ROLES, known=True):
            yield sentence([subject, is_word, good, role], f'{name} {be} {role_description(noun, plural_subject, good=True)}.',
                           'identity', '是 identifies someone. 好 goes directly before a role noun: 好人 means a good person.')
            yield sentence([subject, functions['也'], is_word, role],
                           f'{name} {be} also {role_description(noun, plural_subject)}.', 'identity',
                           'Subject + 也 + 是 + role. 也 connects this identity to the preceding context.')
            yield sentence([subject, functions['不'], is_word, role],
                           f'{name} {be} not {role_description(noun, plural_subject)}.', 'identity',
                           '不 goes before 是 to negate an identity.')
            yield sentence([subject, like, good, role],
                           f"{name} {'likes' if third else 'like'} good {noun + 's' if noun != 'person' else 'people'}.",
                           'preferences', '喜歡 can take a noun object directly. 好 modifies the following noun.')
            if role['text'] in ('朋友', '老師'):
                yield sentence([subject, have, good, role],
                               f"{name} {'has' if third else 'have'} a good {noun}.", 'possession',
                               '有 expresses having a relationship, such as a good friend or teacher.')

        for group in OBJECT_GROUPS:
            objects = slots(group, known=True)
            for obj, noun in objects:
                yield sentence([subject, have, obj],
                               f"{name} {'has' if third else 'have'} {noun}.",
                               'possession', 'Subject + 有 + object expresses possession.')
                yield sentence([subject, like, obj],
                               f"{name} {'likes' if third else 'like'} {noun}.",
                               'preferences', 'Subject + 喜歡 + object expresses a preference.')
                yield sentence([subject, functions['也'], have, obj],
                               f"{name} also {'has' if third else 'have'} {noun}.", 'possession',
                               'Subject + 也 + 有 + object. 有 expresses possession or availability.')
                yield sentence([subject, functions['也'], like, obj],
                               f"{name} also {'likes' if third else 'like'} {noun}.", 'preferences',
                               '喜歡 takes a noun directly; a second action verb is not required.')
                for other, other_name in subjects:
                    if other['id'] == subject['id']:
                        continue
                    other_pronoun = 'I' if other_name == 'I' else other_name.lower()
                    other_have = 'has' if other_name in ('He', 'She') else 'have'
                    yield sentence([subject, have, obj, other, functions['也'], have, obj],
                                   f"{name} {'has' if third else 'have'} {noun}, and {other_pronoun} {other_have} {noun} too.",
                                   'shared-possession', 'Two clauses contrast their subjects. 也 in the second clause means too.', clause_at=3)
            for (first, a), (second, b) in combinations(objects, 2):
                pronoun = 'I' if name == 'I' else name.lower()
                have_verb = 'has' if third else 'have'
                like_verb = 'likes' if third else 'like'
                yield sentence([subject, have, first, functions['也'], have, second],
                               f'{name} {have_verb} {a}, and {pronoun} also {have_verb} {b}.', 'possession',
                               'Two 有 clauses share a subject. 也 means also and links the second thing the speaker has.',
                               clause_at=3, alternatives=(f'{name} {have_verb} {a} and {b}.',))
                yield sentence([subject, like, first, functions['也'], like, second],
                               f'{name} {like_verb} {a}, and {pronoun} also {like_verb} {b}.', 'preferences',
                               'Repeat 喜歡 to link two preferences. 也 means also; the second clause shares the first subject. 和 instead joins noun objects.',
                               clause_at=3, alternatives=(f'{name} {like_verb} {a} and {b}.',))
                for other, other_name in subjects:
                    if other['id'] == subject['id']:
                        continue
                    other_pronoun = 'I' if other_name == 'I' else other_name.lower()
                    for verb, singular, plural in ((have, 'has', 'have'), (like, 'likes', 'like')):
                        yield sentence([subject, verb, first, other, verb, second],
                                       f"{name} {singular if third else plural} {a}, and {other_pronoun} {singular if other_name in ('He', 'She') else plural} {b}.",
                                       'comparison', 'Use two short clauses to compare what different people have or like.', clause_at=3)

        possessive = {'I': 'My', 'You': 'Your', 'He': 'His', 'She': 'Her',
                      'We': 'Our', 'They': 'Their'}[name]
        for obj, noun in slots(SIZED, known=True):
            bare_noun = noun.removeprefix('a ').removeprefix('an ')
            for adjective, meaning in slots(ADJECTIVES, known=True):
                yield sentence([subject, functions['的'], obj, functions['很'], adjective],
                               f'{possessive} {bare_noun} is {meaning}.', 'description',
                               'Possessor + 的 + noun identifies whose thing it is. 很 connects it to an adjective without 是; it need not mean very here.')
                yield sentence([obj, functions['也'], functions['很'], adjective],
                               f'The {bare_noun} is also {meaning}.', 'description',
                               'Noun + 也 + 很 + adjective describes an additional thing. Do not insert 是 before the adjective.')
        for verb_text, reading, base, gerund, objects in ACTIONS:
            verb = resolve(verb_text, reading, known=True)
            if not verb:
                continue
            objects = slots(objects, known=True)
            for obj, noun in objects:
                action = {'drink':'drinks', 'eat':'eats', 'buy':'buys', 'read':'reads',
                          'study':'studies', 'wear':'wears'}[base] if third else base
                yield sentence([subject, verb, obj], f'{name} {action} {noun}.',
                               'actions', 'Subject + action + object describes an action.')
                for modal in ('要', '想', '喜歡', '可以'):
                    word = functions[modal]
                    if word is None:
                        continue
                    if modal == '喜歡':
                        predicate = ('likes' if third else 'like') + f' {gerund} {noun}'
                        question_predicate = f'like {gerund} {noun}'
                    elif modal == '可以':
                        predicate = f'can {base} {noun}'
                        question_predicate = f'{base} {noun}'
                    else:
                        predicate = ('wants' if third else 'want') + f' to {base} {noun}'
                        question_predicate = f'want to {base} {noun}'
                    core = [subject, word, verb, obj]
                    explanation = 'Subject + modal/preference verb + action + object. The object fits the action.'
                    yield sentence(core, f'{name} {predicate}.', 'preference' if modal == '喜歡' else 'plans', explanation)
                    aux = 'Can' if modal == '可以' else 'Does' if third else 'Do'
                    question_name = 'I' if name == 'I' else name.lower()
                    yield sentence(core + [functions['嗎']],
                                   f'{aux} {question_name} {question_predicate}?', 'questions',
                                   'Add 嗎 at the end to turn a statement into a yes/no question.', True)
                    # Time follows the subject; do not use "like ... tomorrow".
                    if modal in ('要', '想', '可以'):
                        for time in ('今天', '明天'):
                            suffix = FUNCTIONS[time][1]
                            timed = [subject, functions[time], word, verb, obj]
                            yield sentence(timed, f'{name} {predicate} {suffix}.', 'time',
                                           'Place 今天 (today) or 明天 (tomorrow) after the subject and before the verb phrase.')
                            yield sentence(timed + [functions['嗎']],
                                           f'{aux} {question_name} {question_predicate} {suffix}?', 'questions',
                                           'Subject + time + modal + action + object + 嗎 forms a question about a plan.', True)
                    if modal in ('要', '想'):
                        yield sentence([subject, functions['也'], word, verb, obj],
                                       f'{name} also {predicate}.', 'also',
                                       '也 (also) comes before the verb phrase and links this statement to prior context.')
                    if modal == '想':
                        yield sentence([subject, functions['不'], word, verb, obj],
                                       f"{name} {'does not' if third else 'do not'} want to {base} {noun}.",
                                       'negation', '不 goes before 想: 不想 means do not want to.')
                for place, location in places:
                    allowed = {'家': {'喝', '吃', '看', '學', '穿'}, '學校': {'學', '看', '吃'},
                               '咖啡店': {'喝', '看'}, '餐廳': {'吃', '喝'},
                               '公園': {'看'}}.get(place['text'], set())
                    if verb_text not in allowed:
                        continue
                    prep = 'at' if place['text'] != '公園' else 'in'
                    be = 'am' if name == 'I' else 'is' if third else 'are'
                    yield sentence([subject, functions['在'], place, verb, obj],
                                   f'{name} {be} {gerund} {noun} {prep} {location}.', 'location',
                                   '在 + place goes before the action to say where it takes place.')
            # Coordination uses two objects appropriate for the same verb.
            for (first, a), (second, b) in combinations(objects, 2):
                yield sentence([subject, functions['要'], verb, first, functions['和'], second],
                               f"{name} {'wants' if third else 'want'} to {base} {a} and {b}.",
                               'coordination', '和 joins two noun objects of the same action.')
        go = resolve('去', 'qù', known=True)
        if go:
            for place, destination in places:
                for modal in ('要', '想'):
                    yield sentence([subject, functions[modal], go, place],
                                   f"{name} {'wants' if third else 'want'} to go {'' if destination == 'home' else 'to '}{destination}.",
                                   'destinations', 'Subject + 要/想 + 去 + destination describes a planned trip.')

