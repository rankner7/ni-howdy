# Bundled language data

- `cedict.txt.gz`: CC-CEDICT downloaded 2026-11-10 from the [MDBG export](https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz). Original dataset, unchanged. License: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Copyright and contributors are recorded in the archive header. This is a dictionary, not a guarantee of Taiwan-specific readings.
- `hanzi.json.gz`: merged dictionary and graphics records from [Make Me a Hanzi](https://github.com/skishore/makemeahanzi), downloaded 2026-11-10. Rebuild with `scripts/prepare_data.py`. Original fields preserved; serialization and packaging changed. Dictionary portions are LGPL v3 or later; geometry is under the Arphic Public License. License texts are in `licenses/`. Dataset stroke order follows PRC conventions; the app neither teaches nor grades that order. Taiwan glyph variants may differ.
- `starter.json`: cached, source-grounded explanations and a small curated Taiwan Mandarin catalog. Character notes quote or summarize Make Me a Hanzi data; retain its attribution and applicable license when reusing those fields. Compound explanations are generated editorial content, not independently verified historical research. Historical assertions should be checked against the cited references.
- `word-frequency.json.gz`: numerical word/count projection from the National Academy for Educational Research (Taiwan), [COCT 通用詞頻表, version 1141208](https://coct.naer.edu.tw/page.jsp?ID=41). Original workbook SHA-256: `bfd3b73938e115ae39a44c5e11c97135c09939cf598157cb2fe0b33c4302de75`. Each weight is the sum of the written-text count (column C) and news count (column I); oral counts and rank columns are unused. The 163,701 exact Traditional forms are normalized to NFC without script conversion. The original workbook, example sentences, and dictionary prose are not redistributed in this projection. Rebuild with `scripts/prepare_frequency.py`; the payload retains the publisher, source URL, measure, and checksum. Counts describe written forms, not individual senses or English definitions.

Optional speech: [PrimeTTS v2.1](https://huggingface.co/Luigi/PrimeTTS), Apache-2.0, downloaded into ignored `.data/models/` by setup. AI-generated Taiwan Mandarin voice. The app supplies stored pinyin readings to avoid silently choosing a different regional reading. Runtime: ONNX Runtime (MIT); pinyin conversion: pypinyin (MIT). Full model and runtime credits remain with their authors.

`character-audio-index.json` preserves the single-character reading/audio-ID pairs from [g0v's MOE concise dictionary audio index](https://github.com/g0v/moedict-data/blob/master/dict-concised.audio.json). Original dictionary content is credited to the Taiwan Ministry of Education. `scripts/setup_recordings.py` uses matching reading identifiers to fetch recordings from the [Ministry's character learning site](https://stroke-order.learningweb.moe.edu.tw/), saving original files unchanged in ignored local storage for personal learning. The repository does not redistribute those audio files. Their source attribution, source page, hash, and playback boundaries are saved in the local manifest. Browser audio playback stops after the initial character pronunciation rather than reading the following narration. Local preparation uses miniaudio (MIT) to detect the quiet boundary.

Local data and indexes are not sent to outside services during practice. Optional content-generation requests contain only the requested entry and its source material.

## Contextual sentences

`sentences.json.gz` contains 27,121 deduplicated Mandarin sentence records from the
2026-02-13 ManyThings.org Chinese–English Tatoeba export (32,028 input pairs).
Source: https://www.manythings.org/anki/cmn-eng.zip
Tatoeba: https://tatoeba.org/ · License: CC BY 2.0 France, as indicated by each
pair's retained attribution. See `licenses/Tatoeba.txt` for the original notice
and archive SHA256. Sentence contributor names, IDs and English alternatives are
retained. The application displays contributor attribution and source links.

Chinese text is adapted using OpenCC `s2twp`; original text is retained. This does
not certify Taiwan usage. Pinyin is generated with pypinyin, and vocabulary
boundaries with jieba followed by Traditional conversion. These can have errors,
particularly ambiguous readings and word senses. Corpus examples are not reviewed
by this project. Text-only data is bundled; no Tatoeba audio is distributed.

To rebuild, download the archive above and install build-only dependencies:
`pypinyin==0.55.0`, `jieba==0.42.1`, `opencc-python-reimplemented==0.1.7`, then run
`.venv/bin/python scripts/build_sentences.py /path/to/cmn-eng.zip`.
Runtime needs only the standard library. Generated data is about 2.5 MiB compressed.
