import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nihowdy.content import load_hanzi
from nihowdy.learning import weighted_sample
from nihowdy.store import Store
from nihowdy.vocabulary import VocabularyPolicy, frequency_data


class VocabularyPolicyTests(unittest.TestCase):
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

    def test_meaningful_parts_and_suffix_exceptions(self):
        policy=VocabularyPolicy()
        def lookup(text,pinyin):
            return dict(text=text,pinyin=pinyin,english=text,id=text)
        parts=policy.parts({'text':'大腳趾','pinyin':'dà jiǎo zhǐ','kind':'word'},lookup)
        self.assertEqual([(p['text'],p['pinyin']) for p in parts],[('大','dà'),('腳趾','jiǎo zhǐ')])
        self.assertEqual([p['text'] for p in policy.parts({'text':'襪子','pinyin':'wà zi','kind':'word'},lookup)],['襪'])
        self.assertEqual(policy.parts({'text':'咖啡','pinyin':'kā fēi','kind':'word'},lookup),[])

    def test_inference_prefers_attested_longer_words(self):
        counts={'小':500,'腳趾':50,'小腳':1,'趾':1,'腳':20}
        def lookup(text,pinyin):
            return dict(text=text,pinyin=pinyin,english=text,id=text) if text in counts else None
        parts=VocabularyPolicy(counts).parts({'text':'小腳趾','pinyin':'xiǎo jiǎo zhǐ','kind':'word'},lookup)
        self.assertEqual([p['text'] for p in parts],['小','腳趾'])


class VocabularyAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hanzi=load_hanzi()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        with patch('nihowdy.store.load_hanzi',return_value=self.hanzi):
            self.store=Store(Path(self.tmp.name)/'test.sqlite',random.Random(8))

    def tearDown(self):
        self.tmp.cleanup()

    def insert(self,db,text,pinyin,english,topic='essentials'):
        item=dict(self.store._item(db,'茶'),id='test:'+text+':'+pinyin,text=text,
                  pinyin=pinyin,english=english,answers=[english],topic=topic)
        db.execute('INSERT INTO items VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
        return item

    def master(self,db,item,mode='flashcards'):
        db.execute("INSERT OR REPLACE INTO progress(item_id,mode,level,status) VALUES (?,?,2,'review')",(item['id'],mode))

    def test_compound_waits_for_all_parts_across_both_skills(self):
        result=self.store.add({'source':'catalog','id':'電腦'})
        self.assertTrue(result['queued'])
        self.assertEqual({p['text'] for p in result['missing_prerequisites']},{'電','腦'})
        with self.store.db() as db:
            self.master(db,self.store._item(db,'電'))
        state=self.store.state()
        computer=next(i for i in state['items'] if i['id']=='電腦')
        self.assertTrue(computer['waiting'])
        self.assertEqual([p['text'] for p in computer['missing_prerequisites']],['腦'])
        with self.store.db() as db:
            self.master(db,self.store._item(db,'腦'),'drawing')
        computer=next(i for i in self.store.state()['items'] if i['id']=='電腦')
        self.assertTrue(computer['enrolled'])
        self.assertFalse(computer['waiting'])
        self.assertEqual({p['mode'] for p in computer['progress']},{'flashcards','drawing'})

    def test_automatic_addition_excludes_locked_compound(self):
        self.store.vocabulary=VocabularyPolicy({'大腳趾':10000})
        with self.store.db() as db:
            compound=self.insert(db,'大腳趾','dà jiǎo zhǐ','big toe')
            toe=self.insert(db,'腳趾','jiǎo zhǐ','toe')
            source=self.store._item(db,'好')
            self.assertEqual(self.store._expand(db,source,1),[])
            self.master(db,self.store._item(db,'大'))
            self.assertEqual(self.store._fill_expansion(db,source,1,[]),[])
            self.master(db,toe,'drawing')
            self.assertEqual(self.store._fill_expansion(db,source,1,[]),['大腳趾'])

    def test_manual_prerequisite_action_adds_foundations(self):
        with self.store.db() as db:
            self.store._enroll(db,'毛衣')
        result=self.store.add_prerequisites('毛衣')
        self.assertEqual(set(result['added']),{'毛','衣'})
        state=self.store.state()
        for text in ['毛','衣']:
            self.assertTrue(any(i['text']==text and i['enrolled'] for i in state['items']))
        self.assertTrue(next(i for i in state['items'] if i['id']=='毛衣')['waiting'])

    def test_automatic_pool_passes_corpus_counts_to_sampler(self):
        self.store.vocabulary=VocabularyPolicy({'人':900,'大':100})
        with self.store.db() as db, patch('nihowdy.store.weighted_sample',wraps=weighted_sample) as sampler:
            result=self.store._expand(db,self.store._item(db,'好'),1)
            self.assertEqual(set(result),{'人','大'})
            self.assertEqual({i['text']:w for i,w in sampler.call_args.args[0]},{'人':900,'大':100})

    def test_mastery_of_another_reading_does_not_unlock_component(self):
        with self.store.db() as db:
            bank=self.insert(db,'銀行','yín háng','bank')
            silver=self.insert(db,'銀','yín','silver')
            go=self.insert(db,'行','xíng','to go')
            line=self.insert(db,'行','háng','line')
            self.master(db,silver)
            self.master(db,go)
            missing=self.store._missing_prerequisites(db,bank)
            self.assertTrue(any(p['text']=='行' and p['pinyin']=='háng' for p in missing))
            self.master(db,line)
            self.assertEqual(self.store._missing_prerequisites(db,bank),[])


if __name__=='__main__':
    unittest.main()
