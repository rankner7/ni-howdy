import unittest

from nihowdy.answers import with_word_answers, word_sense_matches
from nihowdy.glosses import parse_gloss
from nihowdy.learning import correct_answer


class GlossTests(unittest.TestCase):
    def test_articles_work_for_unlisted_noun_phrases(self):
        for source, bare in [('an observatory', 'observatory'), ('a lighthouse', 'lighthouse'),
                             ('an emergency exit', 'emergency exit'),
                             ('a hand-painted ceramic bowl', 'hand-painted ceramic bowl')]:
            with self.subTest(source=source):
                self.assertIn(bare, parse_gloss(source).translations)

    def test_quantifiers_and_fixed_article_expressions_keep_their_article(self):
        for source in ['a little', 'a little water', 'a few people', 'a lot of books',
                       'a great deal', 'a good many', 'a kind of', 'a priori',
                       'an awful lot', 'the observatory', 'two observatories']:
            with self.subTest(source=source):
                self.assertEqual(parse_gloss(source).translations, (source,))

    def test_usage_labels_examples_and_sound_notes_are_metadata(self):
        cases = [
            ('(onom.) moo (sound made by cow)', 'moo'),
            ('(math.) a sum', 'sum'),
            ('a vessel (used for carrying liquids)', 'vessel'),
            ('(literary) beautiful', 'beautiful'),
            ('(Internet slang) thank you (loanword)', 'thank you'),
            ('UK (abbr. for 英國[Ying1 guo2])', 'UK'),
            ('to meet (e.g. at a station)', 'to meet'),
            ('(joining two nouns) and', 'and'),
            ('a bird (especially a seabird)', 'bird'),
            ('a vessel (used for carrying liquids (such as water))', 'vessel'),
        ]
        for source, plain in cases:
            with self.subTest(source=source):
                gloss = parse_gloss(source)
                self.assertIn(plain, gloss.translations)
                self.assertTrue(gloss.notes)
                self.assertEqual(gloss.raw, source)

    def test_semicolons_separate_source_alternatives_not_parenthetical_examples(self):
        gloss = parse_gloss('(slang) clever; smart; bright (used for people; sometimes animals)')
        self.assertEqual(gloss.translations, ('clever', 'smart', 'bright'))
        self.assertEqual(len(gloss.notes), 2)
        self.assertEqual(parse_gloss('to buy and sell').translations, ('to buy and sell',))
        self.assertEqual(parse_gloss('ready, set, go').translations, ('ready, set, go',))

    def test_uncertain_syntax_and_semantic_qualifiers_fall_back(self):
        for source in ['(not) have', 'moo (not a cow sound)', 'vitamin (B)',
                       'a relative (in-law)', 'a bird (female)', 'go (board game)',
                       'to be (at a place)', 'to (not) go', 'a boat (unfinished',
                       'a boat)', 'to stop; not to continue', 'a boat;',
                       '(onom.) (sound made by a camera shutter)',
                       'variant of 船[chuan2]', 'to say "hello; goodbye"',
                       'to say “hello; goodbye”', 'to say "hello']:
            with self.subTest(source=source):
                gloss = parse_gloss(source)
                self.assertEqual(gloss.translations, (source,))
                self.assertTrue(gloss.uncertain)

    def test_no_typo_fuzzy_plural_or_definite_article_matching(self):
        item = with_word_answers(dict(kind='word', english='an observatory', answers=['an observatory']))
        for wrong in ['observatry', 'observatories', 'the observatory', 'a observatory', 'observatory.']:
            with self.subTest(wrong=wrong):
                self.assertFalse(correct_answer(wrong, item['answers']))

    def test_derived_answers_never_become_source_sense_identity(self):
        original = dict(kind='word', english='a vessel (used for carrying liquids)',
                        answers=['a vessel (used for carrying liquids)', 'a container'])
        item = with_word_answers(original)
        self.assertIn('vessel', item['answers'])
        self.assertTrue(word_sense_matches(item, original['english']))
        self.assertTrue(word_sense_matches(item, 'a container'))
        self.assertFalse(word_sense_matches(item, 'vessel'))
        self.assertFalse(word_sense_matches(item, 'a vessel (used for cooking)'))
        self.assertEqual(with_word_answers(item), item)
        self.assertEqual(original['answers'], [original['english'], 'a container'])
        self.assertEqual(item['dictionary_gloss']['notes'], ['used for carrying liquids'])

    def test_empty_gloss_has_no_empty_answer(self):
        self.assertEqual(parse_gloss('  ').translations, ())

    def test_obsolete_inferred_answers_are_recomputed_from_explicit_sources(self):
        item = dict(kind='word', english='(not) have',
                    answers=['(not) have', 'explicit alternative', 'have'],
                    answer_sources=['(not) have', 'explicit alternative'])
        updated = with_word_answers(item)
        self.assertEqual(updated['answers'], ['(not) have', 'explicit alternative'])
        self.assertNotIn('have', updated['answers'])
        self.assertTrue(updated['dictionary_gloss']['uncertain'])

    def test_chinese_quantity_prevents_dropping_the_indefinite_article(self):
        for text, gloss in [('一個出口', 'an exit'), ('一天', 'a day'), ('一杯茶', 'a cup of tea')]:
            with self.subTest(text=text):
                item = dict(kind='word', text=text, english=gloss, answers=[gloss])
                self.assertEqual(with_word_answers(item), item)
        item = with_word_answers(dict(kind='word', text='三明治', english='a sandwich', answers=['a sandwich']))
        self.assertIn('sandwich', item['answers'])

    def test_audit_handles_multiple_unrelated_entries_and_references(self):
        import json
        from scripts.audit_glosses import audit
        rows = [('塔', '塔', 'tǎ', 'ta', json.dumps(['an observatory', '(slang) smart; clever'])),
                ('有', '有', 'yǒu', 'you', json.dumps(['(not) have']))]
        report = audit(rows, sample_limit=1)
        self.assertEqual(report['counts']['glosses'], 3)
        self.assertEqual(report['counts']['with_derived_answers'], 2)
        self.assertEqual(report['counts']['uncertain'], 1)
