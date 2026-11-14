import unittest
from unittest.mock import patch
from nihowdy import sentences

RECORD = dict(text='我也喜歡茶。', original='我也喜欢茶。', tokens=['我','也','喜歡','茶'],
              pinyin='wǒ yě xǐ huān chá', answers=['I also like tea.', 'I like tea too.'],
              attribution=['CC-BY 2.0 (France) Attribution: tatoeba.org #1 (A) & #2 (B)'], sentence_id='2')

class SentenceTests(unittest.TestCase):
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
