"""Audit bundled 喜歡/love matches; original translations stay unchanged.

Run: .venv/bin/python scripts/audit_preference_translations.py
Prints JSON with source IDs, attribution, imported answers, and reviewed answers.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from nihowdy.sentences import corpus, translations

LOVE = re.compile(r'\b(?:love|loves|loved|loving)\b',re.I)
LIKE = re.compile(r'\b(?:like|likes|liked|liking)\b',re.I)
OTHER_SENSES = {
    '818094': 'Love describes love stories; the preference verb is already like.',
    '5405489': '喜歡上 and in love express developing romantic feelings; keep this contextual translation.',
}


def audit(records):
    rows=[]
    for record in records:
        if '喜歡' not in record['text'] or not any(LOVE.search(a) for a in record['answers']):
            continue
        answers=translations(record)
        other=OTHER_SENSES.get(record['sentence_id'])
        imported_like=any(LIKE.search(a) for a in record['answers'])
        status=('other_sense' if other else 'already_in_export' if imported_like else
                'reviewed_like_added' if any(LIKE.search(a) for a in answers) else 'needs_review')
        rows.append(dict(sentence_id=record['sentence_id'],text=record['text'],
                         source_url='https://tatoeba.org/en/sentences/show/'+record['sentence_id'],
                         attribution=record['attribution'],imported_answers=record['answers'],
                         accepted_answers=answers,status=status,note=other or 'Reviewed as an ordinary preference.'))
    return dict(corpus_records=len(records),matches=len(rows),
                counts=dict(Counter(row['status'] for row in rows)),sentences=rows)


if __name__=='__main__':
    print(json.dumps(audit(corpus()),ensure_ascii=False,indent=2))
