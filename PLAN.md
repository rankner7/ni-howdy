# Ni-howdy implementation plan

Status: implementation authorized in the subsequent conversation. The local app is implemented; see README.md for setup, checks, and current limitations. This document retains the original specification.

## Scope

Build a locally runnable, single-user Mandarin learning webapp. Start with Taiwan Mandarin, Traditional characters, and tone-marked Hanyu Pinyin. Support topic selection, free-text interests, and manually entered vocabulary and phrases. Existing prepared content must remain usable without internet access; initial model/data downloads and new-content preparation may use the internet.

Keep pronunciation region and writing system separate in the data model so Mainland Mandarin and Simplified characters can be added later. Keep learner progress separate from shared language content, with a default local learner, so future accounts do not require redesigning the learning engine. Accounts, hosted deployment, and device synchronization are outside the initial scope.

Confirmed requirements below come from the planning conversation. Numerical shuffle weights, session boundaries, and other explicitly marked defaults are proposals that can be tuned without changing the core rules.

## Screens

| Screen | Purpose |
| --- | --- |
| Start / interests | Choose topics, describe interests, see learning progress, and start a practice session. |
| Flashcards | Three levels of recognition/listening practice with typed English answers. |
| Character drawing | Four levels of component and handwriting practice. |
| Phrases and grammar | Three levels of translation practice, with explanations and worked examples. |
| Library / mastered bin | Inspect vocabulary, sources, accepted answers, and separate progress per mode; filter active, mastered, and returning items. |
| Settings | Review probability (initially 0.05), local model configuration, optional LLM provider, and data backup/restore. |

Every practice screen has an Add example action using the same validation pipeline. Character and word information is available through an information icon during flashcards and drawing. Library browsing and ungraded examples do not count as attempts.

## Practice modes

| Mode | Level | Prompt | Response |
| --- | --- | --- | --- |
| Flashcards | Easy | Characters and pinyin | English meaning |
| Flashcards | Medium | Characters and playable audio; no pinyin | English meaning |
| Flashcards | Hard | Characters only, no sound | English meaning |
| Drawing | Easiest | Component assembly; proposed default: English and pinyin cues | Drag components into their correct positions |
| Drawing | Easy | Character with missing strokes, English and pinyin | Draw the missing strokes |
| Drawing | Medium | Character with missing strokes and English; no pinyin | Draw the missing strokes |
| Drawing | Hard | English only | Draw the full character(s) |
| Phrases | Easy | Characters and pinyin | English translation |
| Phrases | Medium | Characters only | English translation |
| Phrases | Hard | English only | Chinese characters composed using a pinyin QWERTY input method |

- Provide a separate, ungraded worked example when introducing a difficulty. Do not reveal the answer to the next graded prompt as its worked example.
- Drawing grades recognizable shape, not stroke order or direction. Handle mouse, touch, and pen input.
- For multi-character entries, show a progress indicator such as “Character 2 of 3.” Complete characters one at a time. One submitted entry is one scored attempt; all its characters must pass for success. Proposed default: show detailed correctness after entry submission, so repeated per-character retries cannot silently turn an incorrect entry into a pass.
- Characters without a useful, supported decomposition skip component pairing. For a mixed multi-character entry, assess decomposable characters at that level and skip the others. If none qualify, start at Easy.
- Missing-stroke grading must evaluate the user's contribution as well as the completed glyph; an unchanged nearly complete template must not pass.
- Hard prompts must not leak characters or pinyin through headings, accessible labels, filenames displayed in the UI, or the information panel before it is opened. Playback itself is not a hint penalty.
- Pinyin composition shows ordinary candidate characters/words, permits selection and editing, and submits the committed Chinese text with punctuation. It must not narrow candidates using the expected answer. Support the operating system's IME as well as the app's QWERTY composition UI.

## Grading and progression

Track difficulty, consecutive failures, active/mastered/review state, and attempt history independently for each learner, item, and practice mode.

1. One unassisted correct attempt advances one eligible difficulty and resets consecutive failures.
2. Correct at the hardest level enters the mastered bin for that mode and starts a new review cycle.
3. An incorrect attempt stays at the same difficulty and increments its failure streak.
4. Three consecutive failures at a difficulty drop one eligible level and reset the streak.
5. Three consecutive failures at the lowest level keep the item there, reset the streak, and increase its selection weight.
6. A review item returns at the hardest level. One correct answer returns it to the bin. Three consecutive failures demote it into ordinary practice.
7. Failure streaks persist across sessions. Changing difficulty resets the streak.

Opening the information icon immediately scores that prompt as one incorrect attempt. Further opens and the final answer on that same prompt do not add failures, erase the failure, or advance the learner. The learner may finish for feedback. Apply any resulting demotion to the next prompt; the current prompt stays available to finish.

Grade English against stored, validated accepted answers. Ignore capitalization; preserve punctuation. Do not use fuzzy similarity, typo tolerance, or live LLM judgment. Proposed normalization: trim surrounding whitespace and normalize Unicode, without removing punctuation or articles. Explicitly store legitimate alternatives such as “computer” and “a computer” when both express the intended sense. These are accepted answers, not approximate matches.

Provide visible spelling and grammar suggestions before submission. Suggestions do not silently edit the answer or disclose the translation. Configure vocabulary responses as fragments rather than treating every noun as an incomplete sentence. Phrase punctuation must follow the displayed task instructions, with accepted variants stored deliberately.

For Chinese phrase answers, use stored validated alternatives; multiple grammatical translations can be correct. For isolated words with multiple meanings, bind each item to a vocabulary sense. For audio-only homophones or English-only ambiguous prompts, either accept all valid prepared alternatives or supply a disambiguating cue compatible with the difficulty. Do not mark a linguistically valid answer wrong because the prompt failed to distinguish it.

## Weighted random selection

Select each next prompt randomly from eligible items within the chosen practice mode. Difficulty reduces weight; unseen and repeatedly missed items receive priority. Mastered items are excluded until daily review selects them.

Proposed initial formula:

```text
level = zero-based position among the item's eligible difficulties
base_weight = 1 / 2^level
unseen_multiplier = 2 if never attempted in this mode, otherwise 1
recovery_multiplier = min(4, 2^lowest_level_failure_blocks)
weight = base_weight * unseen_multiplier * recovery_multiplier
selection_probability = weight / sum(eligible_item_weights)
```

Each block of three consecutive failures at the lowest level increases `lowest_level_failure_blocks` by one. A subsequent unassisted success clears that boost. These weights are adjustable settings in the learning engine, not hard-coded UI logic.

Proposed session rules:

- Avoid repeating the immediately previous item when another eligible item exists. With only one item, repetition is allowed.
- Higher-level items retain nonzero selection probability.
- An advancement changes the item's weight; it does not force that item to be the next prompt.
- Related vocabulary is added immediately to both decks but becomes eligible at the next explicit practice session. Reloading resumes the current session rather than creating one.
- Newly eligible hard reviews participate in the same weighted selection. Once selected for return, they remain pending until mastered again or demoted; ending a session cannot discard them.

## Mastered-bin review

Use independent daily Bernoulli trials with `p = 0.05` per mastered item per mode. The chance of at least one successful selection over `d` unchecked days is:

```text
P(return) = 1 - (1 - 0.05)^d
```

For an item mastered Monday and an app reopened Thursday, draw once for Tuesday, Wednesday, and Thursday, stopping at the first draw below 0.05. The three-day cumulative probability is 14.2625%.

- Store mastery time, review-cycle identity, last checked calendar date, and any return selection.
- Use the learner's persisted local timezone; start with America/New_York in this environment. A “day” means a calendar date, not an elapsed 24-hour interval.
- Check missed dates on startup, session start, and date rollover while open.
- Never reroll a checked date on reload, navigation, or another browser tab. Persist trials/state atomically.
- A successful review starts a new cycle, with its first trial on the following calendar day.
- A returned item receives no further daily trials until remastered.
- Keep pending-review items counted as mastered for phrase eligibility until actual demotion. Recalculate eligibility after demotion.
- There is no background daemon requirement: elapsed days are caught up when the app runs.

## Content preparation and growth

Use a shared vocabulary/sense catalog with topic tags, contextual relations, character links, region-specific readings, English accepted answers, and references.

Manual additions from any learning page follow:

```text
Input -> dictionary/phrase lookup -> sense and reading resolution
      -> validation -> explanation/audio preparation -> ready in deck
```

- Accept Chinese, English, or pinyin input. Require sense selection where lookup is ambiguous.
- Validate spelling, Traditional forms, Taiwan usage/pronunciation, translation, and available drawing data. A dictionary match validates a word, not an arbitrary sentence's grammar.
- Prefer existing verified phrases and constrained grammar templates for phrase validation. Novel phrases may need a one-time online model check plus lexical/template checks. Unsupported or uncertain content stays pending with an actionable explanation; do not label model confidence as proof of correctness.
- Show pending work and retry failed preparation without duplicating content or charging repeated successful generations. API/model errors never count as learner errors.
- On the first mastery of a word in either flashcards or drawing, trigger exactly one expansion event for that word/sense across both modes. Later mastery and review do not trigger another event.
- Randomly choose two distinct, contextually related vocabulary entries from validated candidates, excluding existing and pending entries. Add both to flashcards and drawing. Prepare a small related-candidate pool before mastery so additions can be immediate, including offline where prepared assets exist.
- Contextual relations use semantic/topic tags, not merely shared characters: socks can lead to a T-shirt and sweater. Shared-character relations are useful separately for explanation panels.
- If fewer than two valid candidates are ready, preserve an outstanding expansion job, add available candidates, and finish when preparation becomes possible. Never invent unsupported words to satisfy a count.
- Duplicate safeguards apply to equivalent vocabulary entries while retaining distinct senses and regional variants.

## Phrase generation

- A vocabulary item counts as mastered when its current flashcard OR drawing progress is mastered or pending a hard review.
- Proposed counting convention: segment phrases into stored vocabulary tokens; count occurrences, including grammar/function words, and exclude punctuation. A multi-character word counts as one token. Do not substitute mastery of a component character for mastery of an unrelated compound.
- Require more than three vocabulary tokens and `mastered_token_count / total_token_count > 0.8`. Four out of five is exactly 80% and is rejected; five out of six is accepted. Multi-character vocabulary items count as one word.
- Generate locally during phrase practice using mastered subjects, actions, and semantically suitable objects. Diversify identities, descriptions, possession, shared possession, comparisons, plans, preferences, questions, time expressions, locations, negation, coordination, and destinations as supported vocabulary permits. Balance grammar families to avoid a single prolific pattern dominating. Cache optional model-validated custom phrases after local checks. Store tokenization, accepted translations, and a short grammar explanation.
- Provide playable local audio for the complete phrase at every difficulty, including Hard and answer feedback. Cache generated speech across sessions; listening alone never records an attempt or a hint.
- Recheck the ratio when admitting a phrase to practice. If prerequisite mastery reaches 80% or below, retain phrase progress but pause its eligibility until coverage recovers.
- When insufficient vocabulary is mastered, direct the learner back to vocabulary practice. Do not bypass the threshold to populate the page. An ungraded introductory example remains possible.
- Apply the length and coverage rules to manually added phrases as well. Unsupported custom phrases remain pending privately.
- Keep phrase records, generated history, and mastery in internal storage, including backups, to prevent duplicates after restart or restore. Treat punctuation/spacing variants as one sentence. Preserve existing progression and scheduled reviews.
- Do not list phrases in the word library, mastered bin, search, or recent activity. Only active phrase practice, its explanations/feedback, and worked examples show sentences.

## Explanations and sources

Generate a character explanation once when that character is first added, reuse it in every word that contains it, and generate each word's composition/context note once. Store source URLs, source excerpts or reference identifiers, retrieval dates, generation model/version, and validation state.

Explain modern word construction, component roles, related words, and historical etymology where supported. Distinguish historical evidence from a mnemonic or an uncertain interpretation. Retrieve real source material before generation and check cited support; a model-produced link alone is insufficient. If history is unsupported, provide sourced construction information instead of inventing an etymology. Regeneration requires an explicit edit/refresh or changed source version.

For example, 電腦 can explain the compound “electricity + brain” and link related vocabulary such as 電話 without claiming that each modern component combination is itself a historical origin story.

## Local architecture proposal

Use a browser UI, a local application service, a relational database file, and a local asset/model directory. The UI handles composition, canvases, playback, and feedback. The service owns progression transactions, daily trials, generation jobs, dictionary search, and model adapters. Keep optional external-provider credentials in local service configuration, never browser bundles or tracked files.

Select concrete framework versions after the feasibility work. A typed frontend and a local service capable of calling native inference libraries are appropriate; avoid committing to browser-only inference before measuring it. Keep progression, grading, scheduling, and content validation as modules independent of the UI or chosen model runtime.

Principal records:

| Record | Information |
| --- | --- |
| Learner/settings | Local profile, interests, timezone, review probability |
| Vocabulary/sense | Meaning identity, topics, accepted answers, relationships |
| Written form/reading | Traditional/Simplified form, region, pinyin, audio |
| Character | Components, geometry, supported recognition model |
| Phrase | Text, vocabulary tokens, grammar template, accepted translations |
| Explanation/source | Cached explanation, references, provenance |
| Practice progress | Learner + item + mode, difficulty, streak, recovery weight, mastery state |
| Attempt/session | Prompt instance, response, hint penalty, result, active-session eligibility |
| Review cycle/trial | Mastery date, checked dates, persisted selections |
| Expansion/preparation job | Once-only trigger, candidate selections, preparation status |

Audio, recognition, grammar checking, pinyin input, dictionaries, and explanation generation each use replaceable adapters. Cache assets by content and provider/model version. Include backup and restore for learning data; model binaries can be restored separately.

## Candidate data and local tools

These are researched candidates, not selected or tested dependencies.

- [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) supplies downloadable Chinese-English entries, pinyin, and both writing systems. Use a versioned dataset import and retain source attribution; it is not a complete contextual thesaurus.
- [Taiwan MOE dictionary data via g0v](https://github.com/g0v/moedict-data) is a candidate Taiwan-specific reference. Keep original dictionary text separate from app-authored explanations and preserve the dataset's provenance and license requirements.
- [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) provides character decompositions and vector stroke data for Traditional and Simplified characters. It explicitly follows PRC stroke order, so it cannot be presented as Taiwan stroke-order instruction. This app does not grade order; Taiwan glyph suitability and coverage still need inspection.
- [Tegaki](https://tegaki.github.io/) lists downloadable Traditional Chinese handwriting models for Zinnia. Its age and stroke-based inputs make it a candidate to evaluate, not evidence that it satisfies order-independent shape grading. Compare with image-based recognition if reordered/reversed strokes fail.
- [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/index.html) documents local Chinese TTS model options. Generic Chinese support does not establish Taiwan pronunciation quality. Audition vocabulary, polyphonic words, and phrases; cache approved audio.
- [Rime's pinyin configuration](https://github.com/rime/librime/blob/master/data/minimal/luna_pinyin.schema.yaml) includes Traditional and Taiwan form options. Evaluate its engine/data for local QWERTY composition integration and packaging.
- [LanguageTool's local HTTP server](https://dev.languagetool.org/http-server) supports local spelling/grammar checks with basic rules; its cloud-only AI rules are outside the offline plan.

## Implementation stages and acceptance checks

1. **Feasibility and content sample.** Prepare a small, representative Taiwan Mandarin set spanning simple/complex characters, compounds, ambiguous meanings, and topic relations. Verify glyph coverage, component mappings, local recognizer behavior, audio quality, pinyin composition, and actual installation/model sizes. Record the chosen dependencies and measured limitations before building around them. If Taiwan audio or order-independent recognition cannot meet requirements, resolve that limitation explicitly rather than substituting a cloud grader or strict stroke matching silently.
2. **Data and learning engine.** Implement catalog imports, local persistence, progression, attempt accounting, weighted selection, daily review, and once-only expansion. Deterministic tests use an injected clock and random generator for reproducible outcomes.
3. **Flashcards and library.** Build interests, manual validation, cached explanations/audio, strict accepted-answer grading, spelling/grammar feedback, mastery views, and related-word additions.
4. **Drawing.** Add component placement, missing-stroke prompts, free drawing, multi-character progress, local recognition, and unsupported-character handling.
5. **Phrases and grammar.** Add token mastery coverage, validated templates, cached phrase preparation, grammar explanations, and pinyin-to-character composition.
6. **Local release.** Provide a repeatable launch/setup flow, model/data preparation, backup/restore, and end-to-end validation of complete learning cycles. Confirm prepared content works with network access disabled.

Required behavioral checks include: one success advances; failures 1 and 2 retain level while failure 3 demotes; lowest-level failures boost selection; info access produces exactly one failed attempt; reload preserves streaks and sessions; punctuation changes fail unless explicitly accepted while case changes pass; two mastery modes trigger only one expansion; review dates cannot reroll; missing days are caught up; the 80% boundary includes function words; stroke reordering alone does not fail a recognizable glyph; unchanged missing-stroke templates fail; and infrastructure failures do not alter learner progress.

Implementation uses a Python/SQLite local service and browser-native modules. The repository includes dictionary data, character geometry, and a curated starter catalog; setup installs a local Taiwan Mandarin speech model. No account system or hosted deployment is included. Current implementation details and verification commands are recorded in README.md.
