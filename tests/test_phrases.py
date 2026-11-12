import unittest

from nihowdy.content import starter_items
from nihowdy.phrases import candidates, eligible


class PhraseEngineTests(unittest.TestCase):
    def setUp(self):
        self.items = {i['id']: i for i in starter_items() if i['kind'] == 'word'}
        self.mastered = set()

    def master(self, *words):
        self.mastered.update(words)

    def extra(self, text, pinyin, english):
        self.items[text] = dict(self.items['我'], id=text, text=text, pinyin=pinyin,
                                english=english, answers=[english], chinese_answers=[text])

    def generated(self):
        return [p for p in candidates(self.items, self.mastered) if p]

    def test_strict_coverage_and_word_count(self):
        self.assertFalse(eligible(['我', '要', '茶'], {'我', '要', '茶'}))
        self.assertTrue(eligible(['我', '要', '喝', '茶'], {'我', '要', '喝', '茶'}))
        self.assertFalse(eligible(list('abcdef'), set('abcd')))
        self.assertFalse(eligible(list('abcde'), set('abcd')))
        self.assertTrue(eligible(list('abcdef'), set('abcde')))
        # Multi-character entries count as words, not two Hanzi or syllables.
        self.assertFalse(eligible(['我', '喜歡', '咖啡'], {'我', '喜歡', '咖啡'}))

    def test_diverse_grammar_and_semantic_object_roles(self):
        self.extra('今天', 'jīn tiān', 'today')
        self.extra('嗎', 'ma', 'question particle')
        self.extra('在', 'zài', 'at')
        self.extra('不', 'bù', 'not')
        self.extra('想', 'xiǎng', 'to want')
        self.extra('和', 'hé', 'and')
        self.master('我', '你', '他', '也', '要', '喜歡', '喝', '吃', '買', '看',
                    '學', '去', '茶', '水', '蘋果', '書', '家', '中文', '電腦', '今天',
                    '在', '不', '想', '和')
        phrases = self.generated()
        by_text = {p['text']: p for p in phrases}
        self.assertEqual(by_text['我喜歡喝茶。']['english'], 'I like drinking tea.')
        self.assertEqual(by_text['他要吃蘋果。']['english'], 'He wants to eat apples.')
        self.assertEqual(by_text['你今天要喝茶嗎？']['english'], 'Do you want to drink tea today?')
        self.assertEqual(by_text['我在家看書。']['english'], 'I am reading a book at home.')
        self.assertEqual(by_text['他不想喝茶。']['english'], 'He does not want to drink tea.')
        self.assertIn('我想學中文。', by_text)
        self.assertGreaterEqual(len({p['phrase_family'] for p in phrases}), 9)
        for p in phrases:
            self.assertTrue(eligible(p['tokens'], self.mastered))
        self.assertFalse(any('喝電腦' in p or '吃茶' in p or '穿蘋果' in p for p in by_text))
        self.assertLess(sum('also' in p['english'] for p in phrases), len(phrases) / 3)
        # The six-token question introduces just 嗎: 5/6 > 80%.
        self.assertEqual(by_text['你今天要喝茶嗎？']['tokens'], ['你', '今天', '要', '喝', '茶', '嗎'])
        self.assertNotIn('你要喝茶嗎？', by_text)  # 4/5 is exactly 80%.

    def test_wrong_reading_and_unknown_content_are_not_used(self):
        self.master('我', '要', '喝', '茶')
        self.assertIn('我要喝茶。', {p['text'] for p in self.generated()})
        self.assertNotIn('我要喝水。', {p['text'] for p in self.generated()})
        self.items['喝']['pinyin'] = 'hè'  # A different reading/sense must not fill drink.
        self.assertEqual(self.generated(), [])

    def test_identity_possession_and_preferences_without_action_mastery(self):
        self.master('我', '你', '是', '有', '也', '好', '人', '喜歡', '水', '茶', '蛋', '電腦')
        phrases = {p['text']: p for p in self.generated()}
        self.assertEqual(phrases['我是好人。']['english'], 'I am a good person.')
        self.assertEqual(phrases['你喜歡好人。']['english'], 'You like good people.')
        self.assertEqual(phrases['我有水，也有茶。']['english'], 'I have water, and I also have tea.')
        self.assertIn('I have water and tea.', phrases['我有水，也有茶。']['answers'])
        self.assertEqual(phrases['我喜歡水，也喜歡茶。']['english'], 'I like water, and I also like tea.')
        self.assertIn('I like water and tea.', phrases['我喜歡水，也喜歡茶。']['answers'])
        self.assertEqual(phrases['我有水，你有茶。']['english'], 'I have water, and you have tea.')
        self.assertEqual(phrases['我有茶，你也有茶。']['english'], 'I have tea, and you have tea too.')
        self.assertIn('我也有電腦。', phrases)
        self.assertNotIn('我是人。', phrases)  # Still requires more than three words.
        self.assertNotIn('我有蛋，也有電腦。', phrases)  # Related object groups only.
        self.assertFalse(any('有好人' in text or '有學生' in text for text in phrases))
        self.assertTrue(all(eligible(p['tokens'], self.mastered) for p in phrases.values()))

    def test_descriptions_and_social_roles(self):
        self.extra('很', 'hěn', 'very')
        self.extra('的', 'de', 'possessive particle')
        self.master('我', '他', '也', '是', '有', '好', '學生', '老師', '朋友', '電腦', '蘋果', '大', '小', '的', '很')
        phrases = {p['text']: p for p in self.generated()}
        self.assertEqual(phrases['他是好學生。']['english'], 'He is a good student.')
        self.assertEqual(phrases['他有好朋友。']['english'], 'He has a good friend.')
        self.assertEqual(phrases['他的電腦很大。']['english'], 'His computer is big.')
        self.assertEqual(phrases['我的蘋果很小。']['english'], 'My apple is small.')
        self.assertFalse(any('是大人' in text or '是小人' in text for text in phrases))



if __name__ == '__main__':
    unittest.main()
