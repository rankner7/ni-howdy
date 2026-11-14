# ni-howdy

A personal, locally runnable Taiwan Mandarin learning app. Practise Traditional characters with tone-marked Hanyu Pinyin, discover character construction, and build vocabulary around your interests.

## TODOS
 
## Run locally

Requires Python 3.11+ and a modern browser. No Node.js or database server is needed.

```bash
./setup.sh
./run.sh
```

Open **http://localhost:8765**. Setup installs the Python speech dependencies, downloads the approximately 112 MiB PrimeTTS voice, and prepares Taiwan Ministry of Education recordings for supported starter and library characters. Prepared recordings take priority over synthesized audio, including older cached synthesized clips. New supported characters automatically download their recording on first playback and cache it for offline use. The browser plays only the character pronunciation, stopping before the source recording's radical/stroke-count narration. If a matching recording cannot be prepared, the local voice supplies audio instead.

The dictionary and character data are already bundled. The first launch builds a local dictionary index and prints its progress; later launches reuse the index. Wait for **Ni-howdy is ready** before opening the URL. Ctrl+C stops startup or the server cleanly; an interrupted dictionary import rolls back and can be retried by running `./run.sh` again. You do not need to activate the virtual environment manually: `run.sh` uses it automatically.

If you only want to explore before installing speech dependencies, `python3 -m nihowdy.server` starts the app using the Python standard library. Listening practice requires completing speech setup.

```bash
./run.sh --port 9000
./run.sh --data-dir /path/to/my-learning-data
```

The server binds only to `127.0.0.1`. Stop it with Ctrl+C. Your library and progress live in `.data/nihowdy.sqlite`; generated audio and the speech model also live under `.data/`. This directory is ignored by Git. Settings provides JSON backup and restore; the model and audio cache are separate from those backups.

## Learning rules

- **My learning chart:** daily mastered-word totals reconstructed from saved practice results, with milestones at 100, 500, 1,000, 2,500, 5,000, and 8,000 words. Each written word counts once across flashcards, drawing, and dictionary senses. Returning reviews count until demotion; phrases are excluded. History uses the configured timezone and survives JSON backup and restore.
- **Flashcards:** characters + pinyin → characters + audio → audio only. Type the English meaning. The rolling word bin allows up to 30 introduced, unmastered flashcards. New words still enter the library on mastery, but wait for the bin to drop below 30 before introduction. Showing an introduction reserves its slot; acknowledging it does not free the slot. Flashcard mastery or deletion frees a slot. Existing words and returning reviews remain playable even if they bring an older bin above 30; further introductions wait. Drawing and phrase practice have independent progress.
- **Drawing:** assemble components → add missing strokes with English/pinyin → add missing strokes with English → draw the whole entry from English. Complete multi-character words one character at a time. A separate rolling bin allows up to 8 unmastered words, including returning reviews. New slots prefer fewer characters, then fewer total strokes, using Taiwan stroke templates where available. Showing an introduction reserves a slot; mastery or deletion frees it. If an existing backlog exceeds 8, its simplest 8 words stay active while the rest wait with progress preserved.
- **Listening:** audio-only practice drawn from mastered phrases (including pending phrase reviews). Compose the Mandarin phrase using pinyin at level 1, then type only the English translation at level 2. The pinyin keyboard works like phrase composition: Enter or Space selects the first character suggestion and inserts the selected Mandarin characters into the answer. Enter checks the answer only when the composition box is empty. Pinyin accepts tone marks or tone numbers, including 0/5 for neutral tones; tones matter, while spacing and punctuation do not. Listening has independent mastery and daily reviews, with a bin of up to 30 unmastered phrases including returning reviews. Current prompts, reviews, and existing progress take priority over new phrases. Listening mastery frees a slot; phrases outside the bin wait with progress preserved. Play the audio before checking an answer; playback errors do not count as misses.
- **Phrases:** characters + pinyin → characters only → English to Chinese using the built-in pinyin QWERTY composer or your system IME. Submit characters, including punctuation.
- One correct answer advances a difficulty. Three consecutive misses at the same difficulty move down. At the lowest difficulty, a three-miss block increases selection weight instead. Each mode tracks its own progress.
- Passing the hardest level marks that skill as mastered. Each unchecked local calendar day gets one independent 5% review trial. A returning item appears at its hardest level. Reloads never reroll checked dates.
- Opening the information icon immediately records one incorrect attempt. You may finish for feedback, but the prompt cannot then advance you. Reopening the explanation and resubmitting cannot count additional failures.
- Selection is random, weighted toward lower difficulties. Base weights halve at each level; new flashcards have the same weight as Medium flashcards. Unseen items in other modes receive 2× weight, and repeated lowest-level failure blocks receive up to a 4× recovery boost.
- First mastery in either flashcards or drawing selects up to two contextual neighbours, with odds proportional to their observed frequency in Taiwan written text and news. Unattested words are excluded from automatic additions. Each new compound requires mastery of all meaningful parts before it enters either deck. Selected words become eligible next session; unfinished expansions remain pending.
- Phrase practice requires at least 80% of its vocabulary tokens to be mastered in either flashcards or drawing. Function words count, punctuation does not. The library shows prerequisites and can add them to the deck. Pending hard reviews still count as mastered until demotion.

English answers match a stored list of legitimate translations. Case and surrounding whitespace are ignored; punctuation and spelling remain significant. Articles are accepted only when explicitly included in the answer list. Spelling and basic grammar feedback appears before submission without editing your answer or changing grading.

## Personal vocabulary and explanations

Everyday essentials includes common pronouns, questions, negation, demonstratives, connectors and polite expressions. Existing libraries receive the expanded collection without resetting progress. They are available to add from the library; collection generation also selects eligible words with observed frequency. The upgrade does not automatically enroll them.

Choose topics or describe interests on the home page. Use **Add example** on any practice page to search the bundled dictionary by Chinese, English, or pinyin and select a specific meaning. Supported words join both vocabulary modes once their meaningful parts are mastered. A requested compound waits in the library with its prerequisites and unlocks automatically when ready. Suitable nouns also receive locally generated phrase templates; the 80% rule still controls when those phrases appear.

Starter entries include cached explanations, character construction, related vocabulary examples, and source links. New dictionary entries receive source-backed construction notes. A fuller LLM explanation can be generated once and stored when an optional provider is configured. Entirely novel phrases stay pending until validation; they never silently enter graded practice.

### Optional content provider

Configure a chat-completions-compatible service through environment variables before starting:

```bash
export NIHOWDY_LLM_URL='http://localhost:1234/v1/chat/completions'
export NIHOWDY_LLM_MODEL='your-model-name'
# Set NIHOWDY_LLM_KEY if your provider requires authentication.
./run.sh
```

The service is called when adding a word that needs a fuller explanation, when you explicitly generate an explanation from the library, or when you choose **Validate pending** for a custom phrase. Explanation results are cached by entry; subsequent practice does not call the provider. Requests contain the requested entry and source material, not your learning history. Citations are restricted to supplied source URLs. Model-generated historical and grammatical claims still need editorial review; a citation is not independent proof of correctness.

For stronger local spelling and grammar feedback, optionally run [LanguageTool locally](https://dev.languagetool.org/http-server) and set:

```bash
export NIHOWDY_LANGUAGETOOL_URL='http://localhost:8081/v2/check'
./run.sh
```

Without it, the app uses its local spelling lexicon and basic grammar rules. No external language service is needed for prepared-content practice.

## Architecture and current limits

- Python HTTP service + SQLite, with browser-native ES modules and CSS. Learning rules, storage, dictionary content, speech, and optional providers are separate modules.
- Written form (`Hant`) and pronunciation region (`TW`) are separate data fields. Progress includes a default local learner identity, preparing the model for future accounts. Simplified/Mainland content and accounts are not yet exposed in the UI.
- Drawing uses an embedded geometric template matcher, rather than a trained OCR model. Full-character grading tolerates translation and scale, and all drawing grades ignore stroke order/direction. Missing-stroke grading checks the new ink so an unchanged template cannot pass. Tolerance and confusing character pairs will benefit from real handwriting samples.
- The drawing dataset covers 9,574 characters, but follows PRC stroke ordering and has some regional glyph differences. The app does not teach that ordering. New entries outside the supported drawing set remain unavailable for addition.
- Prepared audio uses reading-specific Taiwan MOE recordings. First playback automatically checks the bundled recording index and tries to prepare a supported single character before using synthesis. Unavailable downloads or unsafe narration boundaries fall back to the local voice; a later playback can retry after five minutes. Compound words and phrases use synthesis unless a matching prepared recording is installed. Stored readings control synthesis, including Taiwan readings identified in the dictionary. Pronunciation quality and regional edge cases have not received an independent native-speaker audit.
- Local phrase generation currently uses constrained sentence templates. Novel free-form sentences require the optional model service. Topic and dictionary associations are useful heuristics, not a comprehensive thesaurus.
- Backup/restore includes library, settings, sessions, and history. It replaces the local database contents after confirmation; it does not copy voice binaries or generated audio.

See [PLAN.md](PLAN.md) for the detailed specification, [docs/vocabulary.md](docs/vocabulary.md) for addition weights and compound prerequisites, and [data/README.md](data/README.md) for sources, attribution, and data licenses.

To prepare or refresh character recordings separately after updating dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_recordings.py
```

Preparation includes single-character words in your current library as well as starter characters. New supported characters are also prepared automatically on first playback. To prepare a specific character ahead of time, use `.venv/bin/python scripts/setup_recordings.py --characters 聲`.

Original recordings remain unchanged under `.data/audio/recordings/`, with source URLs, hashes, reading-specific identifiers, and playback boundaries in `index.json`. Preparing a missing recording needs internet access; cached playback and synthesis work offline. If preparation cannot safely separate the character from later narration, it leaves synthesis in use for that entry.

## Checks

The learning and persistence tests run without extra packages:

```bash
python3 -m unittest discover -v
```

For browser checks, install development dependencies and use an existing Chrome installation:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/browser_check.py
```

Set `CHROME_PATH` if Chrome is not at `/usr/bin/google-chrome`. The browser script uses a temporary database, starts and stops its own server, and stores screenshots in ignored `artifacts/`. It checks desktop/mobile layouts, interests, strict flashcard grading, local audio, hint penalties, component assembly, missing strokes, multi-character progress, free drawing, phrase composition, listening playback and both answer levels, dictionary additions, and absence of external browser requests. It never changes your own progress.

## Corpus examples and phrases

Word information prefers real Tatoeba examples, downloaded via ManyThings.org and
bundled for offline use. Each example shows contributor attribution and a source
link. Where there are no corpus matches, local grammar examples remain available.
The phrase page mixes corpus sentences into the local grammar queue when all
vocabulary can be mapped unambiguously to catalog entries, the sentence contains
at least two words, and strictly more than 80% are mastered. Linked English
translations are accepted alternatives. Hard phrase audio remains unavailable.

Chinese has been adapted to Traditional characters and Taiwan vocabulary with
OpenCC; this does not guarantee Taiwan usage. Pinyin and word boundaries are
computed locally and may need correction. See [data details](data/README.md) for
sources, licenses, limitations, and rebuilding the bundled corpus.

Automatic phrase additions fill a shared bin of up to 15 active, unmastered phrases.
Eligible corpus sentences fill available slots first; generated patterns are added
only when there are not enough new corpus sentences to fill the bin. Existing
phrases and progress are retained, and new additions wait if an older backlog is
already at or above 15. Mastery frees a slot; returning reviews do not consume one.
Corpus and templates receive equal total selection weight before
recent-history adjustments; local pattern families share the template weight.
The last eight sentences and the most recent template family receive reduced
weight, and immediate sentence repeats are avoided when alternatives exist.
Short action, possession, preference and identity patterns use mastered content
words. When a corpus sentence also matches a local pattern, the corpus source and
its attribution are preferred.
