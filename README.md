# ni-howdy

A personal, locally runnable Taiwan Mandarin learning app. Practise Traditional characters with tone-marked Hanyu Pinyin, discover character construction, and build vocabulary around your interests.

## Run locally

Requires Python 3.11+ and a modern browser. No Node.js or database server is needed.

```bash
./setup.sh
./run.sh
```

Open **http://localhost:8765**. Setup installs the Python speech dependencies, downloads the approximately 112 MiB PrimeTTS voice, and prepares Taiwan Ministry of Education recordings for supported starter characters. Prepared character recordings take priority over synthesized audio. The browser plays only the character pronunciation, stopping before the source recording's radical/stroke-count narration. All playback remains offline.

The dictionary and character data are already bundled. The first launch builds a local dictionary index and prints its progress; later launches reuse the index. Wait for **Ni-howdy is ready** before opening the URL. Ctrl+C stops startup or the server cleanly; an interrupted dictionary import rolls back and can be retried by running `./run.sh` again. You do not need to activate the virtual environment manually: `run.sh` uses it automatically.

If you only want to explore before installing speech dependencies, `python3 -m nihowdy.server` starts the app using the Python standard library. Listening practice requires completing speech setup.

```bash
./run.sh --port 9000
./run.sh --data-dir /path/to/my-learning-data
```

The server binds only to `127.0.0.1`. Stop it with Ctrl+C. Your library and progress live in `.data/nihowdy.sqlite`; generated audio and the speech model also live under `.data/`. This directory is ignored by Git. Settings provides JSON backup and restore; the model and audio cache are separate from those backups.

## Learning rules

- **Flashcards:** characters + pinyin → characters + audio → audio only. Type the English meaning.
- **Drawing:** assemble components → add missing strokes with English/pinyin → add missing strokes with English → draw the whole entry from English. Complete multi-character words one character at a time.
- **Phrases:** characters + pinyin → characters only → English to Chinese using the built-in pinyin QWERTY composer or your system IME. Submit characters, including punctuation.
- One correct answer advances a difficulty. Three consecutive misses at the same difficulty move down. At the lowest difficulty, a three-miss block increases selection weight instead. Each mode tracks its own progress.
- Passing the hardest level moves that skill into the mastered bin. Each unchecked local calendar day gets one independent 5% review trial. A returning item appears at its hardest level. Reloads never reroll checked dates.
- Opening the information icon immediately records one incorrect attempt. You may finish for feedback, but the prompt cannot then advance you. Reopening the explanation and resubmitting cannot count additional failures.
- Selection is random, weighted toward lower difficulties and unseen items. Base weights halve at each level; unseen items receive 2× weight, and repeated lowest-level failure blocks receive up to a 4× recovery boost.
- First mastery in either flashcards or drawing selects up to two contextual neighbours, with odds proportional to their observed frequency in Taiwan written text and news. Unattested words are excluded from automatic additions. Each new compound requires mastery of all meaningful parts before it enters either deck. Selected words become eligible next session; unfinished expansions remain pending.
- Phrase practice generates sentences from mastered subjects, actions, and suitable objects. Each phrase must contain **more than three vocabulary words** and **strictly more than 80% known words**, mastered in either flashcards or drawing. Function words count, punctuation does not, and a multi-character word counts once. Four out of five is insufficient; five out of six qualifies. Pending hard reviews still count as mastered until demotion.

English answers match a stored list of legitimate translations. Case and surrounding whitespace are ignored; punctuation and spelling remain significant. Articles are accepted only when explicitly included in the answer list. Spelling and basic grammar feedback appears before submission without editing your answer or changing grading.

## Personal vocabulary and explanations

Choose topics or describe interests on the home page. Use **Add example** on any practice page to search the bundled dictionary by Chinese, English, or pinyin and select a specific meaning. The word library also supports individual/batch deletion of unmastered entries with Undo, and a separate **Generate entries** action using a mastered word or category. Deleted words remain eligible for future suggestions. Supported words join both vocabulary modes once their meaningful parts are mastered. A requested compound waits in the library with its prerequisites and unlocks automatically when ready. Phrase practice prepares a small queue using varied local patterns: plans, preferences, questions, time expressions, locations, negation, coordination, and destinations. Available patterns depend on your mastered vocabulary and the catalog’s supported lexical roles. Automatic generation works offline without an AI provider.

Starter entries include cached explanations, character construction, related vocabulary examples, and source links. New dictionary entries receive source-backed construction notes. A fuller LLM explanation can be generated once and stored when an optional provider is configured. Generated and mastered phrases stay in internal storage for progression, scheduled reviews, and duplicate prevention; they are absent from the word library, mastered bin, and search results. Punctuation and spacing variants count as the same sentence. Existing phrase history is retained, while short or unsupported older automatic templates are paused.

For a custom phrase, use **Add example → Validate and add phrase** when the optional provider is configured. It must pass naturalness, vocabulary, length, and mastery checks before admission. Without a provider, you can save it privately and submit the same text again after configuration. Pending phrases have no public listing.

### Optional content provider

Configure a chat-completions-compatible service through environment variables before starting:

```bash
export NIHOWDY_LLM_URL='http://localhost:1234/v1/chat/completions'
export NIHOWDY_LLM_MODEL='your-model-name'
# Set NIHOWDY_LLM_KEY if your provider requires authentication.
./run.sh
```

The service is called when adding a word that needs a fuller explanation, when you explicitly generate an explanation from the library, or when you choose **Validate and add phrase** for a custom phrase. Explanation results are cached by entry; subsequent practice does not call the provider. Requests contain the requested entry and source material, not your learning history. Citations are restricted to supplied source URLs. Model-generated historical and grammatical claims still need editorial review; a citation is not independent proof of correctness.

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
- Prepared single-character audio uses reading-specific Taiwan MOE recordings, including 我 (wǒ) and 好 (hǎo). Other entries use an AI-generated Taiwan Mandarin voice. Stored readings control synthesis, including Taiwan readings identified in the dictionary. Isolated-character synthesis can be unclear; preparation prefers the reference recordings and bypasses older synthesized clips automatically. Pronunciation quality and regional edge cases have not received an independent native-speaker audit.
- Local phrase generation uses curated word roles and varied constrained grammar patterns, so its vocabulary coverage and sentence variety are bounded. Novel free-form sentences require the optional model service. Topic and dictionary associations are useful heuristics, not a comprehensive thesaurus.
- Backup/restore includes library, settings, sessions, and history. It replaces the local database contents after confirmation; it does not copy voice binaries or generated audio.

See [PLAN.md](PLAN.md) for the detailed specification, [docs/vocabulary.md](docs/vocabulary.md) for addition weights and compound prerequisites, and [data/README.md](data/README.md) for sources, attribution, and data licenses.

To prepare or refresh character recordings separately after updating dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_recordings.py
```

Original recordings remain unchanged under `.data/audio/recordings/`, with source URLs, hashes, reading-specific identifiers, and playback boundaries in `index.json`. Setup needs internet access; practice does not. If preparation cannot safely separate the character from later narration, it leaves synthesis in use for that entry and reports the skipped recording.

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

Set `CHROME_PATH` if Chrome is not at `/usr/bin/google-chrome`. The browser script uses a temporary database, starts and stops its own server, and stores screenshots in ignored `artifacts/`. It checks desktop/mobile layouts, interests, strict flashcard grading, local audio, hint penalties, component assembly, missing strokes, multi-character progress, free drawing, phrase composition, dictionary additions, and absence of external browser requests. It never changes your own progress.
