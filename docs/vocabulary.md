# Vocabulary additions

Automatic additions use measured word counts from Taiwan's National Academy for Educational Research [COCT general frequency table](https://coct.naer.edu.tw/page.jsp?ID=41), version 1141208. The bundled projection contains 163,701 Traditional Chinese forms and their combined **written-text + news occurrence counts**. Spoken counts are excluded. The data stays local during practice.

## Selection odds

First mastery of a vocabulary item still triggers one expansion event, shared by flashcards and drawing. Up to two words in the mastered word’s category are selected without replacement. Unclassified `custom` words do not trigger automatic additions, because that label groups unrelated subjects. Among eligible candidates:

```text
frequency = written-text occurrences + news occurrences
addition weight = frequency ** 1.5
P(next addition = word) = word weight / sum(remaining eligible weights)
```

A word with ten times the observed count has about 31.6 times the selection weight; one with 100 times the count has 1,000 times the weight. The exponent is set by `ADDITION_FREQUENCY_EXPONENT` in `nihowdy/vocabulary.py`. Displayed occurrence counts still use the raw counts. Multiple dictionary senses of the same written word do not create extra sampling tickets. An unattested word has zero automatic-addition weight; it remains available through manual lookup.

Automatic expansion selects catalog words with the same category and dictionary words whose leading meaning is classified into that category by local keyword rules, then applies frequency weights across the eligible pool.

Everyday essentials is a curated beginner collection across subject categories, not an expansion category. Selecting the collection matches catalog membership; mastering a collection word expands its subject category. The same category definitions supply UI labels, dictionary classification, and category generation. Emotions and personality belong to People & relationships; physical sensations belong to Body & health. A versioned migration reclassifies saved words by their selected meaning (using curated categories for starter entries), including deleted entries, at startup and when importing older backups. It preserves IDs, progress, history, and explicitly named custom subjects. Unsupported meanings remain unclassified.

Manual generation continues to use topic relations and dictionary meanings. It no longer shuffles a small arbitrary dictionary subset first. Adjective matching does not confuse “good” with the noun “goods.” Rare attested vocabulary retains a small chance; frequency bias is not a guarantee that every suggestion will be useful to every learner.

Corpus counts describe written forms, not individual meanings. For new dictionary candidates, automatic generation requires the leading dictionary sense to match the topic; it does not search later senses for a convenient keyword. Annotated or complex leading senses are left for manual selection. Dictionary ordering is a conservative heuristic, not proof of everyday usage. Manual lookup still exposes all dictionary senses.

Reviewed usage notes distinguish 水果 (everyday fruit as food), 果實 (plant fruit or figurative results), and 實 (real/solid/substantial, usually in compounds). The fruit/seed sense of standalone 實 is excluded from automatic suggestions. On startup and backup restore, older automatically generated 實 cards labeled fruit/seed are corrected in place, preserving their IDs and progress; unfinished prompts using the old sense are retired without adding a miss. Explicitly selected manual senses are retained.

If fewer than two candidates qualify, the outstanding expansion remains pending and is reconsidered when the candidate pool changes. The app does not fill the gap with unsupported or unrelated vocabulary. Practice-prompt shuffle weights continue to depend on difficulty, unseen status, and repeated failures; corpus counts control which new vocabulary is added.

## Multi-character words

New words enter the flashcard and drawing decks without requiring mastery of individual characters or smaller word parts. This applies to manual dictionary/catalog additions, interest-based additions, automatic expansion, and explicit generation. For example, 電腦 can be practiced before 電 or 腦, and 大腳趾 before 大 or 腳趾.

Previously requested compounds waiting under the old prerequisite rule are enrolled automatically on startup, backup restore, or the next library/practice refresh. Existing progress is retained, and deleted entries remain deleted. The library no longer offers prerequisite queues or a separate action to add prerequisite words.

Automatically selected and explicitly generated words join the rolling practice shuffle immediately. Manual additions are available immediately. Dictionary validation, supported drawing characters, and phrase mastery coverage still apply.

## Delete and generate entries

The word library provides a **Delete** action for each unmastered entry and checkboxes for deleting up to 100 entries together. An entry mastered in any practice mode, including one awaiting hard review, is protected. A batch containing a protected entry is rejected without deleting the other selections.

Deletion removes the entry from the current library and both vocabulary decks, or cancels its waiting request. Unfinished prompts for that entry are retired without recording an incorrect attempt. Phrases containing deleted vocabulary pause until the word is restored. Historical attempts remain in the all-time statistics.

**Undo** is available in the notification for 15 seconds and restores the previous difficulty, failure streak, and other progress. You can also find a deleted entry through **Add example** and choose **Restore** later. Deletion and saved progress are included in backups.

Deleted words remain eligible for future suggestions. A new mastery event or an explicit generation request may choose them again using the normal frequency and drawing-support rules. Merely refreshing the library does not immediately re-add deleted entries through pending background expansions. Reintroduced words join the practice shuffle immediately.

The separate **Generate entries** button accepts:

- An existing word currently mastered in flashcards or drawing. Mastered word cards also offer **Generate related entries** with that word selected.
- A built-in category, or a short custom category in English, matched against local dictionary meanings.

Choose between 1 and 20 entries per request (default: 2). Generation samples new eligible forms without replacement, using the same frequency^1.5 weights as automatic expansion. It uses the local dictionary and does not call an AI provider. Results list the actual additions; a small or empty eligible pool is reported explicitly. The 163,701 corpus forms are the frequency table's coverage; the usable generation pool also requires dictionary matches and supported drawing characters.

Manual generation is separate from the once-only first-mastery expansion event. It may be repeated and does not consume that automatic event. Newly generated vocabulary is added to flashcards and drawing immediately.

## Rebuild the frequency projection

Download the official workbook from the source page, then run:

```bash
python3 scripts/prepare_frequency.py /path/to/workbook.xlsx
```

The converter checks the source headers, preserves exact Traditional forms with NFC normalization, and projects only word/count pairs. It records the workbook's SHA-256 in the bundled output. The original workbook and corpus sentences are not bundled. Details and attribution are in `data/README.md`.
