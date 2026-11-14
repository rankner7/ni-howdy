import unittest
from unittest.mock import patch
from nihowdy import sentences
from nihowdy.answers import correct_english_phrase

RECORD = dict(text='我也喜歡茶。', original='我也喜欢茶。', tokens=['我','也','喜歡','茶'],
              pinyin='wǒ yě xǐ huān chá', answers=['I also like tea.', 'I like tea too.'],
              attribution=['CC-BY 2.0 (France) Attribution: tatoeba.org #1 (A) & #2 (B)'], sentence_id='2')

class SentenceTests(unittest.TestCase):
    def test_preference_audit_covers_all_matches_and_preserves_imported_answers(self):
        from scripts.audit_preference_translations import audit
        report=audit(sentences.corpus())
        self.assertEqual(report['matches'],38)
        self.assertEqual(report['counts'],{'already_in_export':7,'reviewed_like_added':29,'other_sense':2})
        for row in report['sentences']:
            with self.subTest(sentence=row['sentence_id']):
                self.assertTrue(set(row['imported_answers'])<=set(row['accepted_answers']))
                item=dict(kind='phrase',text=row['text'],english=row['imported_answers'][0],
                          answers=row['imported_answers'])
                updated=sentences.with_reviewed_translation(item)
                self.assertEqual(updated['answers'],row['accepted_answers'])
                self.assertEqual(sentences.with_reviewed_translation(updated),updated)

    def test_apple_preference_accepts_like_and_to_eat(self):
        record=next(r for r in sentences.corpus() if r['sentence_id']=='13167235')
        answers=sentences.translations(record)
        self.assertEqual(answers[0],'We like eating apples.')
        for answer in ['We like eating apples','We like to eat apples','We love eating apples']:
            self.assertTrue(correct_english_phrase(answer,answers,record['text']))
        for wrong in ['They like eating apples','We dislike eating apples','We like eating oranges','We like apples']:
            self.assertFalse(correct_english_phrase(wrong,answers,record['text']))

    def test_review_keeps_intensifiers_tense_and_romantic_context(self):
        by_id={r['sentence_id']:r for r in sentences.corpus()}
        music=sentences.translations(by_id['833780'])
        self.assertEqual(music[0],'He likes music very much.')
        self.assertFalse(correct_english_phrase('He likes music',music,by_id['833780']['text']))
        bananas=sentences.translations(by_id['13539445'])
        self.assertIn('Tom liked bananas.',bananas)
        self.assertIn('Tom loved bananas.',bananas)
        for sentence_id in ['818094','5405489']:
            self.assertEqual(sentences.translations(by_id[sentence_id]),by_id[sentence_id]['answers'])
        self.assertEqual(sentences.translations(dict(text='我愛你。',answers=['I love you.'])),['I love you.'])

    def test_bundled_apple_sentence_accepts_both_direct_translations(self):
        record=next(r for r in sentences.corpus() if r['sentence_id']=='13166880')
        answers=sentences.translations(record)
        self.assertIn('We eat apples.',answers)
        self.assertIn('We ate apples.',answers)
        for answer in ['we eat apples','we ate apples']:
            self.assertTrue(correct_english_phrase(answer,answers,record['text']))
        for wrong in ['They eat apples','We eat oranges','We do not eat apples']:
            self.assertFalse(correct_english_phrase(wrong,answers,record['text']))
        self.assertFalse(correct_english_phrase('We eat apples',['We ate apples.'],'我們昨天吃了蘋果。'))

    def test_train_preference_uses_reviewed_translation_without_losing_source(self):
        record=dict(RECORD,text='他喜歡火車。',tokens=['他','喜歡','火車'],
                    answers=['He loves trains.'])
        items={t:dict(id=t,kind='word',text=t) for t in record['tokens']}
        with patch.object(sentences,'corpus',return_value=[record]):
            phrase,=sentences.candidates(items,set(items))
            self.assertEqual(phrase['english'],'He likes trains.')
            self.assertEqual(phrase['answers'],['He likes trains.','He loves trains.'])
            self.assertTrue(phrase['sources'])
            self.assertEqual(sentences.examples({'text':'火車'})[0]['english'],'He likes trains.')
        self.assertEqual(record['answers'],['He loves trains.'])

    def setUp(self):
        self.items = {t:dict(id=t,kind='word',text=t) for t in RECORD['tokens']}

    def test_mastery_and_catalog_boundaries(self):
        with patch.object(sentences, 'corpus', return_value=[RECORD]):
            self.assertEqual(list(sentences.candidates(self.items, {'我','也','茶'})), [])
            phrase, = sentences.candidates(self.items, set(self.items))
            self.assertEqual(phrase['answers'], RECORD['answers'])
            self.assertEqual(phrase['chinese_answers'], [RECORD['text']])
            self.assertEqual(phrase['original_text'], RECORD['original'])
            self.assertIn('#2 (B)', phrase['sources'][0]['title'])
            self.assertTrue(phrase['sources'][0]['url'].endswith('/2'))
            del self.items['茶']
            self.assertEqual(list(sentences.candidates(self.items, set(self.items))), [])

    def test_examples_use_whole_words_and_keep_attribution(self):
        with patch.object(sentences, 'corpus', return_value=[RECORD]):
            self.assertEqual(sentences.examples({'text':'喜'}), [])
            example, = sentences.examples({'text':'茶'})
            self.assertEqual(example['text'], RECORD['text'])
            self.assertTrue(example['sources'])

    def test_two_word_corpus_phrase_is_eligible_but_one_word_is_not(self):
        short = dict(RECORD, text='喜歡茶。', tokens=['喜歡', '茶'])
        with patch.object(sentences, 'corpus', return_value=[short]):
            self.assertEqual(len(list(sentences.candidates(self.items, set(self.items)))), 1)
        single = dict(RECORD, text='茶。', tokens=['茶'])
        with patch.object(sentences, 'corpus', return_value=[single]):
            self.assertEqual(list(sentences.candidates(self.items, set(self.items))), [])

    def test_bundled_data_has_examples_and_attribution(self):
        self.assertGreater(len(sentences.corpus()), 20000)
        self.assertTrue(sentences.examples({'text':'茶'}))
        self.assertTrue(all(r['answers'] and r['attribution'] for r in sentences.corpus()))
