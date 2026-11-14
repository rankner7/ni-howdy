"""Conservative dictionary answer aliases and English sentence equivalences.

Keep this separate from strict word/sense identity and Chinese composition.
Rules must preserve content words, negation, tense, and subject agreement.
"""
import re
import unicodedata

from .content import tone_pinyin
from .glosses import parse_gloss


def correct_pinyin(text, expected):
    """Keep tones significant; accept numbered tones and flexible word spacing."""
    def key(value):
        value = unicodedata.normalize('NFC', value).casefold()
        value = tone_pinyin(value.replace('u:', 'ü').replace('v', 'ü').replace('0', '5'))
        return ''.join(c for c in value if not c.isspace()
                       and not unicodedata.category(c).startswith('P'))
    return bool(key(text)) and key(text) == key(expected)


def with_word_answers(item):
    """Apply one gloss policy to saved, generated, and newly added word cards."""
    if item.get('kind') != 'word':
        return item
    sources = item.get('answer_sources', item['answers'])
    if not sources:
        return item
    # Recompute inferred aliases from authoritative sources so a future policy
    # correction cannot leave an obsolete generated answer in saved cards.
    answers = list(sources)
    for answer in sources:
        for alias in parse_gloss(answer, chinese=item.get('text', '')).translations:
            if alias and alias not in answers:
                answers.append(alias)
    primary = parse_gloss(item.get('english', sources[0]), chinese=item.get('text', ''))
    if answers == item['answers'] and primary.translations == (primary.raw,) and not primary.notes:
        return item
    updated = dict(item, answers=answers, answer_sources=list(sources),
                   dictionary_gloss=dict(policy_version=1, raw=primary.raw,
                                         translations=list(primary.translations),
                                         notes=list(primary.notes), uncertain=primary.uncertain))
    return updated if updated != item else item


def word_sense_matches(item, sense):
    """Sense identity uses source answers, never inferred grading aliases."""
    key = unicodedata.normalize('NFC', sense.strip()).casefold()
    sources = [item['english'], *item.get('answer_sources', item['answers'])]
    return any(key == unicodedata.normalize('NFC', source.strip()).casefold() for source in sources)


# Only unambiguous contractions: 's and 'd need grammatical context.
CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are",
    "they're": "they are", "i've": "i have", "you've": "you have",
    "we've": "we have", "they've": "they have",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "can't": "can not", "cannot": "can not",
    "couldn't": "could not", "won't": "will not", "wouldn't": "would not",
    "shouldn't": "should not", "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not", "mustn't": "must not",
}
CONTRACTION = re.compile(r"\b(?:" + "|".join(map(re.escape, CONTRACTIONS)) + r")\b")

# Explicit forms avoid unreliable stemming (e.g. studying -> study).
PREFERENCE_ACTIONS = {
    "drinking": "drink", "eating": "eat", "buying": "buy", "reading": "read",
    "studying": "study", "wearing": "wear", "learning": "learn",
    "going": "go", "swimming": "swim", "running": "run", "writing": "write",
    "cooking": "cook", "playing": "play", "listening": "listen",
    "speaking": "speak", "walking": "walk", "working": "work",
}
SUBJECT = r"(?:i|you|he|she|it|we|they)"
PREFERENCE = re.compile(
    r"^(?P<prefix>(?:" + SUBJECT + r" (?:also )?(?:likes?|liked|(?:do|does|did) not like)"
    r"|(?:do|does|did) " + SUBJECT + r" (?:not )?like) )"
    r"(?P<gerund>" + "|".join(PREFERENCE_ACTIONS) + r")\b"
)

# Only split between complete, supported clauses, never inside a noun list.
CLAUSE_BREAK = re.compile(r"(?:,\s*(?:and\s+)?|\s+and\s+)(?=" + SUBJECT + r"\b)")
ADDITIVE_CLAUSE = re.compile(
    r"^(?P<subject>" + SUBJECT + r") (?P<also>also )?"
    r"(?P<verb>have|has|had|like|likes|liked|want|wants|wanted|"
    r"am|is|are|was|were|can|will|do|does|did) (?P<rest>.+)$"
)


def normalize_clauses(text):
    clauses = CLAUSE_BREAK.split(text)
    matches = [ADDITIVE_CLAUSE.fullmatch(clause) for clause in clauses]
    if not all(matches):
        return text
    normalized = []
    for clause, match in zip(clauses, matches):
        subject, verb, rest = match['subject'], match['verb'], match['rest']
        before = bool(match['also'])
        # Also can follow "be" or these modals; don't rewrite "has also eggs".
        after = rest.startswith('also ') and verb in {'am', 'is', 'are', 'was', 'were', 'can', 'will'}
        trailing = rest.endswith(' too')
        if sum((before, after, trailing)) == 1:
            if after:
                rest = rest.removeprefix('also ')
            if trailing:
                rest = rest.removesuffix(' too').removesuffix(',')
            clause = f'{subject} also {verb} {rest}'
        # Apply preference equivalence within each clause after placing "also".
        clause = PREFERENCE.sub(
            lambda m: m['prefix'] + 'to ' + PREFERENCE_ACTIONS[m['gerund']], clause
        )
        normalized.append(clause)
    return ', '.join(normalized)

# Mandarin bare count nouns do not specify English singular/plural number.
# Limit this to reviewed object senses; mass nouns and paired clothing need
# different rules. The Chinese must put the bare noun directly after a verb.
COUNT_OBJECTS = {
    "蘋果": ("an apple", "apples"), "雞蛋": ("an egg", "eggs"),
    "蛋": ("an egg", "eggs"), "書": ("a book", "books"),
    "報紙": ("a newspaper", "newspapers"), "電腦": ("a computer", "computers"),
    "手機": ("a mobile phone", "mobile phones"),
    "電話": ("a telephone", "telephones"), "電視": ("a television", "televisions"),
    "鍵盤": ("a keyboard", "keyboards"), "滑鼠": ("a computer mouse", "computer mice"),
    "票": ("a ticket", "tickets"), "毛衣": ("a sweater", "sweaters"),
    "上衣": ("a top", "tops"), "襯衫": ("a shirt", "shirts"),
    "外套": ("a coat", "coats"),
}


def unspecified_objects(chinese):
    for noun, forms in COUNT_OBJECTS.items():
        # Multiple mentions may refer to objects with different quantities.
        if chinese.count(noun) == 1 and re.search(
            r"(?:吃|買|看|穿|有|喜歡)" + noun + r"(?=$|[。，？！、；,.?!;也和])", chinese
        ):
            yield forms


def shared_indefinite_articles(text, object_forms):
    """An article can govern coordinated nouns: a computer and mobile phone."""
    singulars = [singular for singular, _ in object_forms]
    bare = {re.sub(r'^(?:a|an) ', '', singular): singular for singular in singulars}
    if not singulars:
        return text
    first = '|'.join(map(re.escape, sorted(singulars, key=len, reverse=True)))
    second = '|'.join(map(re.escape, sorted(bare, key=len, reverse=True)))
    pattern = re.compile(r'\b(' + first + r') and (' + second + r')\b')
    # Repeat to cover lists such as "a computer and mobile phone and keyboard".
    while True:
        expanded = pattern.sub(lambda m: m[1] + ' and ' + bare[m[2]], text)
        if expanded == text:
            return text
        text = expanded


def english_phrase_key(text, object_forms=()):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    text = " ".join(text.split())
    # Ending punctuation is optional; clause normalization handles only the
    # supported joining commas below. Other punctuation and possessives remain.
    text = text.rstrip(".!? ")
    text = CONTRACTION.sub(lambda m: CONTRACTIONS[m[0]], text)
    # Restrict this to ordinary preference clauses. In particular, "would like
    # to drink" expresses a wish and must not collapse to "would like drinking".
    text = PREFERENCE.sub(
        lambda m: m['prefix'] + 'to ' + PREFERENCE_ACTIONS[m['gerund']], text
    )
    text = normalize_clauses(text)
    text = shared_indefinite_articles(text, object_forms)
    forms = {form: plural for singular, plural in object_forms for form in (singular, plural)}
    if forms:
        # Match the longest noun phrase first, in one pass: a computer mouse
        # must not become "computers mouse" when computers are also mentioned.
        pattern = r"\b(?:" + "|".join(map(re.escape, sorted(forms, key=len, reverse=True))) + r")\b"
        text = re.sub(pattern, lambda m: forms[m[0]], text)
    return text


def correct_english_phrase(text, accepted, chinese=""):
    object_forms = tuple(unspecified_objects(chinese))
    key = english_phrase_key(text, object_forms)
    return bool(key) and any(key == english_phrase_key(answer, object_forms) for answer in accepted)


ENDING_PUNCTUATION = {'。': '.', '？': '?', '！': '!'}


def correct_chinese_phrase(text, accepted):
    """Match composition exactly, with only the final sentence mark optional."""
    answer = unicodedata.normalize('NFC', text.strip())
    if not answer:
        return False
    for expected in accepted:
        expected = unicodedata.normalize('NFC', expected.strip())
        if answer == expected:
            return True
        if expected[-1:] in ENDING_PUNCTUATION:
            stem = expected[:-1]
            if answer in (stem, stem + ENDING_PUNCTUATION[expected[-1]]):
                return True
    return False
