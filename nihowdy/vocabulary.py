"""Corpus-based addition weights and lexical (not radical) prerequisites."""
from functools import lru_cache
import gzip
import json
import math
from pathlib import Path
import unicodedata

DATA=Path(__file__).resolve().parent.parent/'data'


@lru_cache(maxsize=1)
def frequency_data():
    with gzip.open(DATA/'word-frequency.json.gz','rt') as source:
        return json.load(source)


def reading_key(pinyin):
    return ''.join(unicodedata.normalize('NFC',pinyin).lower().split())


# Lexical parts are context dependent. These overrides avoid teaching bound
# suffixes and phonetic loans as unrelated standalone vocabulary.
COMPONENTS={
    '咖啡':[], '沙發':[], '巧克力':[], '葡萄':[], '檸檬':[], '吉他':[],
    '馬拉松':[], '太太':[],
    '你好':['你','好'], '謝謝':['謝'], '喜歡':['喜','歡'],
    '牛奶':['牛','奶'], '米飯':['米','飯'], '麵包':['麵','包'],
    '水果':['水','果'], '蘋果':['果'],
    '電腦':['電','腦'], '電話':['電','話'], '電視':['電','視'],
    '手機':['手','機'], '網路':['網','路'], '鍵盤':['鍵','盤'], '滑鼠':['滑','鼠'],
    '襪子':['襪'], '衣服':['衣','服'], '毛衣':['毛','衣'], '上衣':['上','衣'],
    '襯衫':['襯','衫'], '褲子':['褲'], '鞋子':['鞋'], '外套':['外','套'],
    '火車':['火','車'], '公車':['公','車'], '捷運':['捷','運'], '車站':['車','站'],
    '朋友':['友'], '學生':['學'], '老師':['師'], '中文':['中','文'], '學校':['學','校'],
    '大腳趾':['大','腳趾'], '腳趾':['腳','趾'],
}


class VocabularyPolicy:
    def __init__(self, counts=None):
        self.counts=frequency_data()['counts'] if counts is None else counts

    def addition_weight(self, text):
        return self.counts.get(text,0)

    def parts(self, item, lookup):
        """Return sense/reading-resolved lexical parts, using longest useful words.

        `lookup(text, pinyin)` resolves a component to a known entry. Word parts
        are strictly shorter than the parent, preventing prerequisite cycles.
        """
        text=item['text']
        if item['kind']!='word' or len(text)<2:
            return []
        syllables=item['pinyin'].split()
        if len(syllables)!=len(text):
            # Do not invent a context reading for unusually represented entries.
            return [dict(text=c,pinyin='',english='Reading needs verification',id=None)
                    for c in dict.fromkeys(text)]

        def resolve(part,start):
            pinyin=' '.join(syllables[start:start+len(part)])
            return lookup(part,pinyin) or dict(text=part,pinyin=pinyin,english='Dictionary meaning',id=None)

        override=COMPONENTS.get(text)
        if override is not None:
            result=[]
            for part in override:
                if part==text:
                    continue
                start=text.index(part)
                result.append(resolve(part,start))
            return result

        # Prefer a small number of independently attested words; for example,
        # 大 + 腳趾 rather than 大 + 腳 + 趾. Reading checks prevent homograph errors.
        @lru_cache(maxsize=None)
        def segment(start):
            if start==len(text):
                return []
            choices=[]
            for end in range(start+1,len(text)+1):
                if start==0 and end==len(text):
                    continue
                part=text[start:end]
                pinyin=' '.join(syllables[start:end])
                if not self.addition_weight(part):
                    continue
                entry=lookup(part,pinyin)
                tail=segment(end) if entry else None
                if tail is not None:
                    choices.append([entry]+tail)
            return min(choices,key=lambda ps:(len(ps),-sum(math.log1p(self.addition_weight(p['text'])) for p in ps))) if choices else None

        parts=segment(0)
        if parts is None:
            parts=[]
            for index,char in enumerate(text):
                # Light noun/person suffixes carry no separate vocabulary task.
                if index==len(text)-1 and (char,syllables[index]) in {('子','zi'),('兒','r'),('們','men')}:
                    continue
                parts.append(resolve(char,index))
        seen=set()
        unique=[]
        for part in parts:
            key=(part['text'],reading_key(part['pinyin']))
            if key not in seen:
                seen.add(key)
                unique.append(part)
        return unique
