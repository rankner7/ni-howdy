"""Interpret dictionary gloss conventions without guessing semantic similarity.

The source gloss remains the sense identity. Translations are answer candidates;
notes describe usage, domain, examples, or pronunciation. Unrecognized syntax
falls back to the original gloss rather than silently discarding meaning.
"""
from dataclasses import dataclass
import re


LABEL = re.compile(
    r'^(?:onom\.|onomatopoeia|fig\.|figuratively|lit\.|literally|colloq\.|colloquial|'
    r'slang|Internet slang|online slang|informal|formal|literary|archaic|obsolete|dialect|regional|humorous|'
    r'vulgar|derogatory|honorific|polite|math\.|math|mathematics|physics|chemistry|'
    r'biology|medicine|computing|sports|music|grammar|noun|verb|adjective|adverb|'
    r'conjunction|preposition|interjection|bound form|n\.|v\.|adj\.|adv\.|prep\.|'
    r'coll\.|loanword|Tw|Taiwan|Hong Kong|botany|zoology|anatomy|law|finance|'
    r'military|theater|cinema)(?:\s|$)', re.I)
EXPLANATION = re.compile(
    r'^(?:sound (?:made by|of)|used (?:for|to|when|as|in)|joining |'
    r'e\.g\.|for example|such as|esp\.|especially|i\.e\.|abbr\. for|'
    r'abbreviation of|Taiwan pr\.)', re.I)
SPECIALIZATION = re.compile(r'^(?:esp\.|especially)\s+(.+)$', re.I)
COMMA_SPECIALIZATION = re.compile(r'^([^,]+),\s*((?:esp\.|especially)\s+[^,]+)$', re.I)
MEANINGFUL_QUALIFIER = re.compile(
    r'\b(?:not|no|never|without|only|except|opposite|negative|negated|male|female)\b|'
    r'\bin[- ]law\b', re.I)
# These are quantifiers and fixed expressions, not ordinary indefinite nouns.
ARTICLE_EXPRESSION = re.compile(
    r'^(?:a (?:little|few|lot|bit|couple|number|great deal|good (?:deal|many)|'
    r'kind of|sort of|type of|priori|posteriori|la\b)|an awful lot)\b', re.I)
INCOMPLETE = re.compile(r'^(?:not|but|rather|instead|except|as opposed to)\b', re.I)
BRACKETS = dict(zip(')]}', '([{'))
COUNTED_WORD = re.compile(
    r'^[一二兩三四五六七八九十百千萬億零〇\d]+'
    r'(?:個|本|條|張|隻|雙|件|位|枚|顆|杯|碗|瓶|公斤|公克|公分|公里|克|'
    r'年|月|天|日|小時|分鐘|次|人)'
)


@dataclass(frozen=True)
class Gloss:
    raw: str
    translations: tuple[str, ...]
    notes: tuple[str, ...] = ()
    uncertain: bool = False


def _parts(text):
    """Split semicolons outside balanced parentheses; never split conjunctions."""
    stack, start, quote = [], 0, None
    parts = []
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in '"“':
            quote = '”' if char == '“' else char
            continue
        if char in '([{':
            stack.append(char)
        elif char in ')]}':
            if not stack or stack.pop() != BRACKETS[char]:
                return None
        elif char == ';' and not stack:
            parts.append(text[start:index].strip())
            start = index + 1
    if stack or quote:
        return None
    parts.append(text[start:].strip())
    if any(not part or INCOMPLETE.match(part) for part in parts[1:]):
        return None
    return parts


def _edge_notes(text):
    """Remove recognized edge notes, retaining unknown/semantic parentheses."""
    spans, depth, start = [], 0, 0
    for index, char in enumerate(text):
        if char == '(':
            if depth == 0:
                start = index
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
    left, right = 0, len(text)
    notes = []
    for start, end in spans:
        note = text[start + 1:end - 1].strip()
        recognized = (LABEL.match(note) or EXPLANATION.match(note)) and not MEANINGFUL_QUALIFIER.search(note)
        if start == left and recognized:
            notes.append(note)
            left = end
            while left < right and text[left].isspace():
                left += 1
    for start, end in reversed(spans):
        if start < left:
            continue
        note = text[start + 1:end - 1].strip()
        recognized = (LABEL.match(note) or EXPLANATION.match(note)) and not MEANINGFUL_QUALIFIER.search(note)
        if end == right and recognized:
            notes.append(note)
            right = start
            while right > left and text[right - 1].isspace():
                right -= 1
    return text[left:right], notes


def parse_gloss(raw, *, chinese=''):
    """Return answer text and notes using dictionary syntax, not word lists."""
    text = ' '.join(raw.split())
    parts = _parts(text)
    # Bracketed readings, references, and malformed glosses need explicit review.
    if not text or parts is None:
        return Gloss(raw, (text,) if text else (), uncertain=True)
    translations, notes = [], []
    uncertain = False
    for part in parts:
        base, qualifiers = _edge_notes(part)
        specialization = COMMA_SPECIALIZATION.fullmatch(base)
        if specialization and not MEANINGFUL_QUALIFIER.search(specialization[2]):
            base = specialization[1].strip()
            qualifiers.append(specialization[2])
        if not base or any(char in base for char in '()[]{}"“”'):
            # For example, "(not) have", "vitamin (B)", or a description with
            # no actual translation must not become a generic/empty answer.
            translations.append(part)
            uncertain = True
            continue
        translations.append(base)
        notes.extend(qualifiers)
        for qualifier in qualifiers:
            specific = SPECIALIZATION.fullmatch(qualifier)
            # A modifier plus the same headword is a safe specialization.
            # Do not turn fragments such as "esp. by train" into translations.
            if (specific and not MEANINGFUL_QUALIFIER.search(qualifier)
                    and re.fullmatch(r"[\w '-]+", specific[1])
                    and specific[1].casefold().endswith(' ' + base.casefold())):
                translations.append(specific[1])
        article = re.match(r'^(?:a|an) (.+)$', base, re.I)
        if article and not ARTICLE_EXPRESSION.match(base) and not COUNTED_WORD.match(chinese):
            translations.append(article[1])
    return Gloss(raw, tuple(dict.fromkeys(translations)), tuple(dict.fromkeys(notes)), uncertain)
