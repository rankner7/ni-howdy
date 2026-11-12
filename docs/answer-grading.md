# Dictionary answers and grading

Dictionary definitions contain both translations and editorial information.
`nihowdy/glosses.py` interprets those conventions once, for every word, rather
than keeping lists of special answers for individual Chinese entries.

The policy applies when reading existing cards and when adding dictionary cards.
Generated vocabulary and restored backups use the same policy through the store.
It does not require a network service or an additional language model.

## Source, answers, and notes

The original `english` gloss remains visible and retains the selected sense.
When a gloss produces additional answers, the item also records:

- `answer_sources`: the original explicit answers, used for sense identity.
- `dictionary_gloss`: the original gloss, parsed translations, recognized notes,
  a policy version, and an uncertainty flag.
- `answers`: original answers plus derived translations, used for grading.

These fields are stored in the existing item JSON and survive backup and restore.
They do not change item IDs, pronunciation, scheduling, or attempt history.
Reading an old card can derive answers without rewriting its stored record.
Derived answers are recomputed from `answer_sources`, so a policy correction can
remove an obsolete inferred alias without removing an explicit source answer.

Dictionary search and duplicate detection compare original source senses.
An inferred answer such as “vessel” must not merge cards with different annotated
senses or readings. Pronunciation notes are handled by the dictionary importer
and scoped to their source senses, independently of English answer grading.

## Supported conventions

| Source gloss | Additional accepted answers |
| --- | --- |
| `an observatory` | `observatory` |
| `a hand-painted ceramic bowl` | `hand-painted ceramic bowl` |
| `moo (sound made by cow)` | `moo` |
| `(literary) beautiful` | `beautiful` |
| `(slang) clever; smart` | `clever`, `smart` |
| `a vessel (used for carrying liquids)` | `a vessel`, `vessel` |

Semicolons split alternatives only outside balanced parentheses, brackets and
quotations. Commas and conjunctions are not assumed to introduce synonyms.
Recognized usage labels, domains, sound explanations, examples and pronunciation
notes are metadata. A note with nested parentheses stays intact.

An initial `a` or `an` in an ordinary dictionary noun gloss is optional. Articles
remain required in quantifiers and fixed constructions such as `a little`,
`a few`, `a lot of`, and `a priori`. Recognized counted Chinese expressions such
as 一個出口 and 一杯茶 also retain their indefinite article. Definite articles,
explicit numbers and singular/plural forms are not discarded.

Negation and meaning-bearing qualifiers are retained. Unknown parenthetical
conventions, malformed brackets, quoted expressions and references fall back to
their original text. For example, `(not) have`, `vitamin (B)`, and
`to be (at a place)` do not become “have”, “vitamin”, or “to be”. The parser
does not infer synonyms, use fuzzy spelling matches, or guess arbitrary semantic
equivalence. Such alternatives require explicit source answers.

Sentence translation has its own clause-aware equivalence rules in
`nihowdy/answers.py`. Dictionary gloss parsing does not run on sentences or on
Chinese composition. Strict `correct_answer` remains available for source and
literal comparisons.

## Verification and extending the policy

Run the regression suite with `python3 -m unittest discover -v`.
`tests/test_glosses.py` exercises categories of syntax using unrelated vocabulary
and counterexamples. Store tests cover existing/new cards, sense identity,
pronunciation, restart, backup/restore and progress preservation.

Run the read-only corpus audit with:

```bash
python3 scripts/audit_glosses.py --output artifacts/gloss-audit.json
```

It checks every bundled dictionary gloss for nonempty, stable translations and
reports how many gain answers, contain notes or require review. Deterministic
reservoir samples span the dictionary rather than just its first entries.
These checks find structural problems; the samples still need human review for
semantic accuracy.

Extend the grammar by documenting a dictionary convention and adding positive
and negative examples from unrelated entries. Keep ambiguous cases unchanged
until the source provides enough structure to distinguish them reliably.
