import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nihowdy.learning import weighted_sample
from nihowdy.store import Store
from nihowdy.vocabulary import VocabularyPolicy, frequency_data


class VocabularyPolicyTests(unittest.TestCase):
    def test_nonlinear_weights_preserve_raw_counts_and_exclude_unattested(self):
        policy=VocabularyPolicy({'common':10000,'rare':1000,'zero':0})
        self.assertEqual(policy.frequency_count('common'),10000)
        self.assertEqual(policy.frequency_count('rare'),1000)
        self.assertAlmostEqual(policy.addition_weight('common') / policy.addition_weight('rare'),
                               10 ** 1.5)
        for word in ('zero','missing'):
            self.assertEqual(policy.frequency_count(word),0)
            self.assertEqual(policy.addition_weight(word),0)

    def test_shared_addition_selector_uses_nonlinear_weights(self):
        # This draw would pick the rare word under linear weighting (90/10),
        # but picks the common word under frequency^1.5 (about 96.4/3.6).
        store=Store.__new__(Store)
        store.vocabulary=VocabularyPolicy({'common':900,'rare':100})
        common=dict(id='common',text='common')
        rare=dict(id='rare',text='rare')
        store._candidate_pool=Mock(return_value=[common,rare])
        store._enroll=Mock()
        store.rng=Mock()
        store.rng.random.return_value=.95
        db=Mock()
        self.assertEqual(store._select_entries(db,{},1,after=3),[common])
        store._enroll.assert_called_once_with(db,'common')

    def test_sampling_odds_follow_actual_weights(self):
        class GridRandom:
            def __init__(self):
                self.index=0
            def random(self):
                result=(self.index+.5)/1000
                self.index+=1
                return result
        rng=GridRandom()
        counts={'common':0,'rare':0}
        for _ in range(1000):
            chosen=weighted_sample([('common',9),('rare',1),('unattested',0)],1,rng)[0]
            counts[chosen]+=1
        self.assertEqual(counts,{'common':900,'rare':100})
        self.assertEqual(len(set(weighted_sample([('a',2),('b',1)],2,random.Random(1)))),2)

    def test_corpus_has_measured_traditional_text_counts(self):
        data=frequency_data()
        self.assertEqual(data['workbook_sha256'],'bfd3b73938e115ae39a44c5e11c97135c09939cf598157cb2fe0b33c4302de75')
        self.assertEqual(data['counts']['茶'],52227)
        self.assertGreater(data['counts']['茶'],data['counts']['有備無患'])
        self.assertEqual(VocabularyPolicy().addition_weight('未收錄的測試用詞'),0)


class VocabularyAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.sqlite'
        # Small explicit fixtures keep admission tests independent of corpus files.
        forms='我 你 也 要 喝 水 茶 好 一 二 三 電腦 電 腦 人 大 毛衣 毛 衣'.split()
        self.items=[dict(id=text,kind='word',text=text,pinyin=text,english=text,
                         answers=[text],chinese_answers=[text],topic='essentials',tokens=[])
                    for text in forms]
        self.hanzi={c:{} for c in ''.join(forms)+'腳趾銀行電話'}
        self.store=self.open_store()

    def open_store(self):
        with patch('nihowdy.store.load_hanzi',return_value=self.hanzi), \
             patch('nihowdy.store.starter_items',return_value=self.items), \
             patch('nihowdy.store.VocabularyPolicy',return_value=VocabularyPolicy({})):
            return Store(self.path,random.Random(8))

    def insert(self,db,text,pinyin,english,topic='essentials'):
        item=dict(self.store._item(db,'茶'),id='test:'+text+':'+pinyin,text=text,
                  pinyin=pinyin,english=english,answers=[english],topic=topic)
        db.execute('INSERT INTO items VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
        return item

    def assert_enrolled(self,item_id,after=0):
        with self.store.db() as db:
            progress=list(db.execute('SELECT * FROM progress WHERE item_id=?',(item_id,)))
        self.assertEqual({p['mode'] for p in progress},{'flashcards','drawing'})
        self.assertTrue(all(p['status']=='active' and p['eligible_after']==after for p in progress))

    def queue_legacy_word(self):
        with self.store.db() as db:
            db.execute("DELETE FROM progress WHERE item_id='電腦'")
            db.execute("UPDATE items SET data=json_set(data,'$.requested',json('true')) WHERE id='電腦'")

    def test_starter_compound_enrolls_without_adding_component_cards(self):
        self.assert_enrolled('電腦')
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM progress WHERE item_id IN ('電','腦')").fetchone()[0],0)

    def test_manual_compound_enters_both_decks_without_mastery(self):
        result=self.store.add({'source':'catalog','id':'毛衣'})
        self.assertFalse(result['queued'])
        self.assertEqual(result['missing_prerequisites'],[])
        self.assert_enrolled('毛衣')
        item=next(i for i in self.store.state()['items'] if i['id']=='毛衣')
        self.assertTrue(item['enrolled'])
        self.assertFalse(item['waiting'])

    def test_automatic_addition_includes_compound_with_unlearned_parts(self):
        self.store.vocabulary=VocabularyPolicy({'大腳趾':10000})
        with self.store.db() as db:
            compound=self.insert(db,'大腳趾','dà jiǎo zhǐ','big toe')
            self.insert(db,'腳趾','jiǎo zhǐ','toe')
            self.assertEqual(self.store._expand(db,self.store._item(db,'好'),1),['大腳趾'])
        self.assert_enrolled(compound['id'])

    def test_interest_addition_includes_compound_without_mastery(self):
        with self.store.db() as db:
            compound=self.insert(db,'電話','diàn huà','telephone',topic='technology')
        self.store.update_settings({'interests':['technology']})
        self.assert_enrolled(compound['id'])

    def test_dictionary_compound_can_be_added_manually_or_generated(self):
        for source in ('manual','generation'):
            with self.subTest(source=source):
                with self.store.db() as db:
                    row_id=db.execute('INSERT INTO dictionary(traditional,pinyin,meanings) VALUES (?,?,?)',
                                      ('銀行','yín háng',json.dumps(['bank']))).lastrowid
                if source=='manual':
                    result=self.store.add({'source':'dictionary','id':row_id})
                    self.assertFalse(result['queued'])
                    item=result['item']
                    self.assert_enrolled(item['id'])
                    # Remove this fixture so the next iteration uses the dictionary pool.
                    with self.store.db() as db:
                        db.execute('DELETE FROM progress WHERE item_id=?',(item['id'],))
                        db.execute('DELETE FROM items WHERE id=?',(item['id'],))
                else:
                    self.store.vocabulary=VocabularyPolicy({'銀行':100})
                    result=self.store.generate_entries({'source':'category','category':'bank','count':1})
                    self.assertEqual([i['text'] for i in result['items']],['銀行'])
                    self.assert_enrolled(result['items'][0]['id'])

    def test_legacy_waiting_word_activates_on_state_startup_and_restore(self):
        for trigger in ('state','startup','restore'):
            with self.subTest(trigger=trigger):
                self.queue_legacy_word()
                if trigger=='state':
                    self.store.state()
                elif trigger=='startup':
                    self.store=self.open_store()
                else:
                    self.store.restore(self.store.backup())
                self.assert_enrolled('電腦')
                self.assertFalse(self.store.item('電腦').get('requested'))

    def test_deleted_waiting_word_stays_deleted_until_undo(self):
        self.queue_legacy_word()
        self.store.delete_entries(['電腦'])
        self.assertFalse(any(i['id']=='電腦' for i in self.store.state()['items']))
        self.store.restore_entries(['電腦'])
        self.store.state()
        self.assert_enrolled('電腦')

    def test_legacy_activation_preserves_existing_progress(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET level=2,attempts=5,failures=1,eligible_after=7 WHERE item_id='電腦'")
            before=[dict(p) for p in db.execute("SELECT * FROM progress WHERE item_id='電腦'")]
            db.execute("UPDATE items SET data=json_set(data,'$.requested',json('true')) WHERE id='電腦'")
        self.store.state()
        with self.store.db() as db:
            self.assertEqual([dict(p) for p in db.execute("SELECT * FROM progress WHERE item_id='電腦'")],before)

    def test_automatic_pool_passes_nonlinear_weights_to_sampler(self):
        self.store.vocabulary=VocabularyPolicy({'人':900,'大':100})
        with self.store.db() as db, patch('nihowdy.store.weighted_sample',wraps=weighted_sample) as sampler:
            result=self.store._expand(db,self.store._item(db,'好'),1)
            self.assertEqual(set(result),{'人','大'})
            self.assertEqual({i['text']:w for i,w in sampler.call_args.args[0]},
                             {'人':900 ** 1.5,'大':100 ** 1.5})


if __name__=='__main__':
    unittest.main()
