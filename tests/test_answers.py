import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.answers import correct_chinese_phrase, correct_english_phrase
from nihowdy.phrases import ACTIONS, candidates
from nihowdy.store import Store, encode
from nihowdy.vocabulary import VocabularyPolicy


class EnglishPhraseTests(unittest.TestCase):
    def assertEquivalent(self, first, second, chinese=""):
        self.assertTrue(correct_english_phrase(first, [second], chinese))
        self.assertTrue(correct_english_phrase(second, [first], chinese))

    def test_reported_coffee_answer_and_formatting(self):
        self.assertEquivalent("I like to drink coffee", "I like drinking coffee.")
        self.assertEquivalent("  I  LIKE\nTO DRINK coffee! ", "I like drinking coffee.")

    def test_all_generated_preference_verbs(self):
        for _, _, base, gerund, _ in ACTIONS:
            for prefix in ("I like", "She likes", "They also like", "He liked",
                           "We do not like", "Do you like", "Does she like"):
                with self.subTest(base=base, prefix=prefix):
                    self.assertEquivalent(f"{prefix} to {base} something",
                                          f"{prefix} {gerund} something.")

    def test_unambiguous_contractions(self):
        for first, second in (("I don’t like to drink coffee", "I do not like drinking coffee."),
                              ("I'm reading a book", "I am reading a book."),
                              ("We can't eat apples", "We cannot eat apples.")):
            self.assertEquivalent(first, second)

    def test_reported_shared_possession_and_optional_conjunction(self):
        expected = "You have eggs, and he has eggs too."
        for answer in ("You have eggs, he also has eggs", "You have eggs and he also has eggs",
                       "You have eggs, and he also has eggs", "You have eggs, he has eggs too",
                       "You have eggs,he has eggs, too"):
            with self.subTest(answer=answer):
                self.assertEquivalent(answer, expected, "你有蛋，他也有蛋。")

    def test_reported_comparison_without_and(self):
        self.assertEquivalent("I like apples, he likes eggs", "I like apples, and he likes eggs.",
                              "我喜歡蘋果，他喜歡蛋。")

    def test_additive_equivalence_with_other_subjects_and_predicates(self):
        for first, second in (("I have tea, she also has tea", "I have tea, and she has tea too."),
                              ("We also want to buy a book", "We want to buy a book too."),
                              ("I am also a teacher", "I am a teacher too."),
                              ("He can also drink coffee", "He can drink coffee too."),
                              ("I like coffee, she also likes to drink tea",
                               "I like coffee, and she likes drinking tea too.")):
            self.assertEquivalent(first, second)

    def test_additive_matching_preserves_meaning_and_scope(self):
        expected = "You have eggs, and he has eggs too."
        for answer in ("You have eggs, he has eggs", "You also have eggs, he has eggs",
                       "You have eggs, she also has eggs", "You have eggs, he also had eggs",
                       "You have eggs, he also has tea", "You have eggs, he also has no eggs",
                       "You have eggs, he doesn't have eggs", "You have eggs, he also have eggs",
                       "You have eggs, but he also has eggs", "You have eggs because he also has eggs"):
            with self.subTest(answer=answer):
                self.assertFalse(correct_english_phrase(answer, [expected], "你有蛋，他也有蛋。"))
        self.assertFalse(correct_english_phrase("He is also happy", ["He is too happy."]))
        self.assertFalse(correct_english_phrase("I have tea, coffee", ["I have tea and coffee."]))

    def test_meaning_and_grammar_remain_significant(self):
        for answer in ("I do not like drinking coffee", "You like drinking coffee",
                       "I liked drinking coffee", "I like to drink tea", "I want to drink coffee",
                       "I like coffee", "I likes drinking coffee", "I like to drinking coffee",
                       "I like drink coffee", "I like to drink coffe", "I like to drink coffee tomorrow"):
            with self.subTest(answer=answer):
                self.assertFalse(correct_english_phrase(answer, ["I like drinking coffee."]))
        self.assertFalse(correct_english_phrase("I would like to drink coffee",
                                              ["I would like drinking coffee."]))
        self.assertFalse(correct_english_phrase("I stopped to drink coffee", ["I stopped drinking coffee."]))
        self.assertFalse(correct_english_phrase("I like my sisters", ["I like my sister's."]))
        self.assertFalse(correct_english_phrase("I am a teacher", ["I am the teacher."]))
        self.assertFalse(correct_english_phrase("...", [""]))

    def test_reported_apple_answer(self):
        self.assertEquivalent("I also want to eat an apple", "I also want to eat apples.", "我也要吃蘋果。")
        self.assertEquivalent("I like to eat an apple", "I like eating apples.", "我喜歡吃蘋果。")
        self.assertEquivalent("She wants to buy a book", "She wants to buy books.", "她要買書。")
        self.assertEquivalent("I like eggs", "I like an egg.", "我喜歡雞蛋。")
        self.assertEquivalent("I have a computer and a computer mouse", "I have computers and computer mice.",
                              "我有電腦，也有滑鼠。")

    def test_number_rules_require_source_evidence(self):
        for chinese in ("", "我也要吃一顆蘋果。", "我也要吃兩顆蘋果。", "我也要喝蘋果汁。",
                        "我買蘋果，你買兩顆蘋果。"):
            with self.subTest(chinese=chinese):
                self.assertFalse(correct_english_phrase("I also want to eat an apple",
                                                       ["I also want to eat apples."], chinese))
        for answer in ("I also want to eat two apples", "I also want to eat the apple",
                       "I also want to eat apple", "I also want to eat an egg",
                       "I want to eat an apple", "I also do not want to eat an apple"):
            with self.subTest(answer=answer):
                self.assertFalse(correct_english_phrase(answer, ["I also want to eat apples."], "我也要吃蘋果。"))

    def test_explicit_alternative_translations(self):
        self.assertTrue(correct_english_phrase("I enjoy drinking coffee", ["I like drinking coffee.",
                                                                          "I enjoy drinking coffee."]))

    def test_generated_shared_subject_answers_preserve_content(self):
        words = {text: dict(id=text, kind='word', text=text, pinyin=pinyin, topic='food')
                 for text, pinyin in (('他', 'tā'), ('喜歡', 'xǐ huān'), ('有', 'yǒu'),
                                      ('也', 'yě'), ('蘋果', 'píng guǒ'), ('蛋', 'dàn'))}
        phrases = {p['text']: p for p in candidates(words, set(words)) if p}
        for chinese, verb in (('他喜歡蘋果，也喜歡蛋。', 'likes'), ('他有蘋果，也有蛋。', 'has')):
            accepted = phrases[chinese]['answers']
            for answer in (f'He {verb} apples, and he also {verb} eggs',
                           f'He {verb} apples, he {verb} eggs too',
                           f'He {verb} apples and eggs'):
                with self.subTest(chinese=chinese, answer=answer):
                    self.assertTrue(correct_english_phrase(answer, accepted, chinese))
            for answer in (f'He {verb} apples, and she also {verb} eggs',
                           f'He {verb} apples, and he also {verb} tea',
                           f'He {verb} apples, and he does not {"like" if verb == "likes" else "have"} eggs',
                           'He likes apples, and he also has eggs'):
                with self.subTest(chinese=chinese, answer=answer):
                    self.assertFalse(correct_english_phrase(answer, accepted, chinese))


class ChinesePhraseTests(unittest.TestCase):
    def test_final_sentence_mark_is_optional_but_content_is_not(self):
        for source, answer in [('我喜歡喝咖啡。', '我喜歡喝咖啡'),
                               ('你有蛋嗎？', '你有蛋嗎'),
                               ('太好了！', '太好了'),
                               ('我喜歡喝咖啡。', '我喜歡喝咖啡.'),
                               ('你有蛋嗎？', '你有蛋嗎?'),
                               ('太好了！', '太好了!')]:
            with self.subTest(source=source, answer=answer):
                self.assertTrue(correct_chinese_phrase(answer, [source]))
                self.assertTrue(correct_chinese_phrase(source, [source]))

    def test_wrong_ending_and_internal_punctuation_still_fail(self):
        accepted = ['你有蛋，他也有蛋。']
        for answer in ('你有蛋他也有蛋', '你有蛋、他也有蛋', '你有蛋，他也有雞蛋',
                       '你有蛋，他也有蛋？', '你有蛋，他也有蛋。。', '', '。'):
            with self.subTest(answer=answer):
                self.assertFalse(correct_chinese_phrase(answer, accepted))


class PhraseGradingStoreTests(unittest.TestCase):
    """Exercise persisted grading using a small catalog, without bundled data."""
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "test.sqlite"
        words = [("我", "wǒ", "I"), ("喜歡", "xǐ huān", "like"), ("喝", "hē", "drink"),
                 ("咖啡", "kā fēi", "coffee"), ("也", "yě", "also"), ("要", "yào", "want"),
                 ("吃", "chī", "eat"), ("蘋果", "píng guǒ", "apple"),
                 ("你", "nǐ", "you"), ("他", "tā", "he"), ("有", "yǒu", "have"),
                 ("蛋", "dàn", "eggs"), ("火車", "huǒ chē", "train")]
        items = {text: dict(id=text, text=text, pinyin=pinyin, english=english,
                           answers=[english], chinese_answers=[text], kind="word", topic="food")
                 for text, pinyin, english in words}
        # Seed before construction so Store does not load the bundled catalog.
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE items(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            db.executemany("INSERT INTO items VALUES (?,?)", [(i, encode(item)) for i, item in items.items()])
        with patch("nihowdy.store.load_hanzi", return_value={}), \
             patch("nihowdy.store.VocabularyPolicy", return_value=VocabularyPolicy(counts={})):
            self.store = Store(path)
        with self.store.db() as db:
            for item in items:
                db.execute("INSERT INTO progress(item_id,mode,level,status) VALUES (?,'flashcards',2,'mastered')", (item,))
            for phrase in candidates(items, set(items)):
                if phrase:
                    db.execute("INSERT INTO items VALUES (?,?)", (phrase['id'], encode(phrase)))
                    self.store._enroll(db, phrase['id'])

    def prompt(self, sentence="我喜歡喝咖啡。", level=0, mode="phrases"):
        item_id = "phrase:" + sentence if mode == "phrases" else sentence
        with self.store.db() as db:
            session = self.store._session(db)
            db.execute("UPDATE progress SET level=? WHERE item_id=? AND mode=?", (level, item_id, mode))
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES ('test',?,?,?,?,?)",
                       (session, item_id, mode, level, '{}'))
        return "test"

    def test_coffee_advances_once_and_caches_result(self):
        prompt = self.prompt()
        result = self.store.answer(prompt, {"text": "I like to drink coffee"})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)
        self.assertEqual(self.store.answer(prompt, {"text": "wrong"}), result)
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 1)

    def test_saved_corpus_train_preference_accepts_likes(self):
        item=dict(id='phrase:他喜歡火車。',kind='phrase',text='他喜歡火車。',
                  pinyin='tā xǐ huān huǒ chē',english='He loves trains.',
                  answers=['He loves trains.'],chinese_answers=['他喜歡火車。'],
                  tokens=['他','喜歡','火車'],topic='custom',phrase_engine='tatoeba-v1')
        with self.store.db() as db:
            db.execute('INSERT INTO items VALUES (?,?)',(item['id'],encode(item)))
            self.store._enroll(db,item['id'])
            self.assertEqual(self.store._items(db)[item['id']]['english'],'He likes trains.')
        result=self.store.answer(self.prompt(item['text']),{'text':'He likes trains'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'],1)
        self.assertEqual(result['item']['english'],'He likes trains.')
        self.assertIn('He loves trains.',result['item']['answers'])
        for wrong in ('She likes trains','He dislikes trains','He likes cars'):
            self.assertFalse(correct_english_phrase(wrong,result['item']['answers'],item['text']))

    def test_apple_advances_at_medium(self):
        result = self.store.answer(self.prompt("我也要吃蘋果。", level=1), {"text": "I also want to eat an apple"})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 2)

    def test_shared_possession_answer_advances(self):
        result = self.store.answer(self.prompt("你有蛋，他也有蛋。"),
                                   {"text": "You have eggs, he also has eggs"})
        self.assertEqual(result['item']['english'], "You have eggs, and he has eggs too.")
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)

    def test_comparison_without_and_advances(self):
        result = self.store.answer(self.prompt("我喜歡蘋果，他喜歡蛋。", level=1),
                                   {"text": "I like apples, he likes eggs"})
        self.assertEqual(result['item']['english'], "I like apples, and he likes eggs.")
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 2)

    def test_reported_shared_preference_answer_advances(self):
        result = self.store.answer(self.prompt('他喜歡蘋果，也喜歡蛋。'),
                                   {'text': 'He likes apples, and he also likes eggs'})
        self.assertEqual(result['item']['english'], 'He likes apples, and he also likes eggs.')
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 1)

    def test_compact_shared_preference_answer_still_advances(self):
        result = self.store.answer(self.prompt('他喜歡蘋果，也喜歡蛋。', level=1),
                                   {'text': 'He likes apples and eggs'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['level'], 2)

    def test_existing_prompt_refreshes_legacy_translation_without_resetting_progress(self):
        prompt = self.prompt('他喜歡蘋果，也喜歡蛋。', level=1)
        item_id = 'phrase:他喜歡蘋果，也喜歡蛋。'
        with self.store.db() as db:
            item = self.store._item(db, item_id)
            item.update(english='He likes apples and eggs.',
                        answers=['He likes apples and eggs.', 'He enjoys apples and eggs.'],
                        explanation='Old explanation')
            db.execute('UPDATE items SET data=? WHERE id=?', (encode(item), item_id))
            db.execute("UPDATE progress SET attempts=4,failures=1 WHERE item_id=?", (item_id,))
            before = dict(db.execute('SELECT * FROM progress WHERE item_id=?', (item_id,)).fetchone())
        # An outstanding prompt should use the new answers on submission.
        result = self.store.answer(prompt, {'text': 'He likes apples, and he likes eggs too'})
        self.assertTrue(result['correct'])
        self.assertEqual(result['item']['english'], 'He likes apples, and he also likes eggs.')
        self.assertIn('He enjoys apples and eggs.', result['item']['answers'])
        self.assertEqual(result['progress']['level'], before['level'] + 1)
        self.assertEqual(result['progress']['attempts'], before['attempts'] + 1)

    def test_translation_refresh_preserves_mastered_history_and_custom_content(self):
        item_id = 'phrase:他喜歡蘋果，也喜歡蛋。'
        with self.store.db() as db:
            item = self.store._item(db, item_id)
            item.update(english='He likes apples and eggs.', answers=['He likes apples and eggs.'])
            db.execute('UPDATE items SET data=? WHERE id=?', (encode(item), item_id))
            db.execute("UPDATE progress SET level=2,status='mastered',attempts=6 WHERE item_id=?", (item_id,))
            before = dict(db.execute('SELECT * FROM progress WHERE item_id=?', (item_id,)).fetchone())
            self.store._phrase_options(db)
            self.assertEqual(dict(db.execute('SELECT * FROM progress WHERE item_id=?', (item_id,)).fetchone()), before)
            self.assertEqual(self.store._item(db, item_id)['english'], 'He likes apples, and he also likes eggs.')
            item['explanation_origin'] = 'Model-checked grammar with local vocabulary validation'
            db.execute('UPDATE items SET data=? WHERE id=?', (encode(item), item_id))
            self.store._phrase_options(db)
            self.assertEqual(self.store._item(db, item_id), item)

    def test_hint_still_counts_one_miss(self):
        prompt = self.prompt()
        self.store.info(prompt)
        result = self.store.answer(prompt, {"text": "I like to drink coffee"})
        self.assertFalse(result['correct'])
        self.assertTrue(result['answer_correct'])
        self.assertEqual(result['progress']['attempts'], 1)

    def test_wrong_translation_records_miss(self):
        result = self.store.answer(self.prompt(), {"text": "I do not like to drink coffee"})
        self.assertFalse(result['correct'])
        self.assertEqual(result['progress']['failures'], 1)

    def test_hard_chinese_composition_accepts_no_ending_punctuation(self):
        result = self.store.answer(self.prompt(level=2), {"text": "我喜歡喝咖啡"})
        self.assertTrue(result['correct'])
        self.assertEqual(result['progress']['status'], 'mastered')

    def test_hard_chinese_composition_keeps_internal_punctuation(self):
        result = self.store.answer(self.prompt('你有蛋，他也有蛋。', level=2),
                                   {'text': '你有蛋他也有蛋'})
        self.assertFalse(result['correct'])

    def test_hard_phrase_audio_is_unavailable_even_after_answering(self):
        prompt = self.prompt(level=2)
        with self.assertRaisesRegex(ValueError, 'Audio is unavailable'):
            self.store.audio_item(prompt)
        self.store.answer(prompt, {'text': '我喜歡喝咖啡'})
        with self.assertRaisesRegex(ValueError, 'Audio is unavailable'):
            self.store.audio_item(prompt)

    def test_easy_phrase_audio_remains_available(self):
        self.assertEqual(self.store.audio_item(self.prompt(level=0))['text'], '我喜歡喝咖啡。')

    def test_medium_phrase_audio_remains_available(self):
        self.assertEqual(self.store.audio_item(self.prompt(level=1))['text'], '我喜歡喝咖啡。')

    def test_flashcards_keep_existing_policy(self):
        result = self.store.answer(self.prompt("咖啡", mode="flashcards"), {"text": "coffee."})
        self.assertFalse(result['correct'])
