"""Audit dictionary answer derivation without modifying the library or progress.

Run: python3 scripts/audit_glosses.py --output artifacts/gloss-audit.json
"""
import argparse
from collections import Counter
import json
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nihowdy.content import dictionary_rows
from nihowdy.glosses import parse_gloss


def audit(rows, sample_limit=20):
    counts = Counter()
    samples = {'derived': [], 'uncertain': []}
    seen = Counter()
    rng = random.Random(0)
    for text, _, reading, _, encoded in rows:
        counts['entries'] += 1
        for raw in json.loads(encoded):
            counts['glosses'] += 1
            gloss = parse_gloss(raw, chinese=text)
            if not gloss.translations or any(not value.strip() for value in gloss.translations):
                raise ValueError(f'Empty translation for {text} / {raw}')
            # Every derived form must remain stable when interpreted again.
            for translation in gloss.translations:
                if translation not in parse_gloss(translation, chinese=text).translations:
                    raise ValueError(f'Unstable translation for {text} / {raw}')
            derived = [value for value in gloss.translations if value != raw]
            counts['with_derived_answers'] += bool(derived)
            counts['with_notes'] += bool(gloss.notes)
            counts['uncertain'] += gloss.uncertain
            category = 'uncertain' if gloss.uncertain else 'derived' if derived else None
            if category:
                seen[category] += 1
                sample = dict(text=text, pinyin=reading, source=raw,
                              translations=gloss.translations, notes=gloss.notes)
                if len(samples[category]) < sample_limit:
                    samples[category].append(sample)
                else:
                    index = rng.randrange(seen[category])
                    if index < sample_limit:
                        samples[category][index] = sample
    return dict(counts=dict(counts), samples=samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(dictionary_rows())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['counts'], indent=2))


if __name__ == '__main__':
    main()
