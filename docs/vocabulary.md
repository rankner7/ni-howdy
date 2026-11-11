# Vocabulary additions

Automatic additions use measured word counts from Taiwan's National Academy for Educational Research [COCT general frequency table](https://coct.naer.edu.tw/page.jsp?ID=41), version 1141208. The bundled projection contains 163,701 Traditional Chinese forms and their combined **written-text + news occurrence counts**. Spoken counts are excluded. The data stays local during practice.

## Selection odds

First mastery of a vocabulary item still triggers one expansion event, shared by flashcards and drawing. Up to two contextual neighbours are selected without replacement. Among eligible candidates:

```text
addition weight = written-text occurrences + news occurrences
P(next addition = word) = word weight / sum(remaining eligible weights)
```

A word with ten times the observed count has ten times the selection weight. This is a word-frequency measure, not a dictionary rank, a fabricated popularity score, or the frequency of an English translation. Multiple dictionary senses of the same written word do not create extra sampling tickets. An unattested word has zero automatic-addition weight; it remains available through manual lookup.

Context still matters. The app uses topic relations and dictionary meanings to prepare the candidate pool, then applies frequency weights across the complete eligible pool. It no longer shuffles a small arbitrary dictionary subset first. Adjective matching does not confuse “good” with the noun “goods.” Rare attested vocabulary retains a small chance; frequency bias is not a guarantee that every suggestion will be useful to every learner.

If fewer than two candidates qualify, the outstanding expansion remains pending and is reconsidered as more prerequisites are mastered. The app does not fill the gap with unsupported or unrelated vocabulary. Practice-prompt shuffle weights continue to depend on difficulty, unseen status, and repeated failures; corpus counts control which new vocabulary is added.

## Compound prerequisites

A new compound enters the flashcard and drawing decks only after **all meaningful lexical parts** have been mastered in either vocabulary skill. Pending hard reviews count as mastery, consistent with the phrase rule. Mastery is checked against both written form and contextual reading, so learning 行 xíng does not satisfy a requirement for 行 háng.

Examples:

| Compound | Prerequisites |
| --- | --- |
| 大腳趾, big toe | 大, big; 腳趾, toe |
| 電腦, computer | 電, electricity; 腦, brain |
| 毛衣, sweater | 毛, hair/wool; 衣, clothing |
| 襪子, socks | 襪; the light noun suffix 子 is excluded |
| 咖啡, coffee | Treated as a phonetic loan, without unrelated character prerequisites |

The policy includes contextual decompositions for the starter catalog and common exceptions. For other words, it prefers a small number of dictionary-attested word parts with corpus evidence, using the word's reading. When no complete word segmentation is available, it falls back to individual character parts and excludes recognized light suffixes. This is a local lexical heuristic, not a complete linguistic analysis; curated exceptions can be extended in `nihowdy/vocabulary.py`.

An explicit request for a locked compound is saved as **waiting**, without inserting that compound into either practice deck. The library shows the missing parts and offers **Add prerequisite words**. The compound unlocks automatically once all those parts are mastered. A prerequisite can itself be a compound with its own prerequisites.

Existing learning records are retained. These admission checks govern newly enrolled words; they do not erase past progress or withdraw an already-enrolled compound when a component is later demoted. Automatically selected words become eligible in the next practice session as before. Manually queued words unlock when their prerequisites are satisfied.

## Delete and generate entries

The word library provides a **Delete** action for each unmastered entry and checkboxes for deleting up to 100 entries together. An entry mastered in any practice mode, including one awaiting hard review, is protected. A batch containing a protected entry is rejected without deleting the other selections.

Deletion removes the entry from the current library and both vocabulary decks, or cancels its waiting request. Unfinished prompts for that entry are retired without recording an incorrect attempt. Phrases containing deleted vocabulary pause until the word is restored. Historical attempts remain in the all-time statistics.

**Undo** is available in the notification for 15 seconds and restores the previous difficulty, failure streak, and other progress. You can also find a deleted entry through **Add example** and choose **Restore** later. Deletion and saved progress are included in backups.

Deleted words remain eligible for future suggestions. A new mastery event or an explicit generation request may choose them again using the normal frequency and prerequisite rules. Merely refreshing the library does not immediately re-add deleted entries through pending background expansions. Reintroduced words join the next practice session.

The separate **Generate entries** button accepts:

- An existing word currently mastered in flashcards or drawing. Mastered word cards also offer **Generate related entries** with that word selected.
- A built-in category, or a short custom category in English, matched against local dictionary meanings.

Choose between 1 and 20 entries per request (default: 2). Generation samples new eligible forms without replacement, using the same corpus counts and compound prerequisites as automatic expansion. It uses the local dictionary and does not call an AI provider. Results list the actual additions; a small or empty eligible pool is reported explicitly. The 163,701 corpus forms are the frequency table's coverage; the usable generation pool also requires dictionary matches, supported drawing characters, and satisfied prerequisites.

Manual generation is separate from the once-only first-mastery expansion event. It may be repeated and does not consume that automatic event. Newly generated vocabulary is added to flashcards and drawing for the next session.

## Rebuild the frequency projection

Download the official workbook from the source page, then run:

```bash
python3 scripts/prepare_frequency.py /path/to/workbook.xlsx
```

The converter checks the source headers, preserves exact Traditional forms with NFC normalization, and projects only word/count pairs. It records the workbook's SHA-256 in the bundled output. The original workbook and corpus sentences are not bundled. Details and attribution are in `data/README.md`.
