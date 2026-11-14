"""Download and prepare reading-specific Taiwan MOE character recordings."""
import hashlib
import fcntl
from functools import lru_cache
import json
import math
from pathlib import Path
import shutil
import subprocess
import unicodedata
from urllib.request import urlopen
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent.parent


def recording_key(item):
    return unicodedata.normalize('NFC',item['text']+'|'+item['pinyin'].strip().lower())


@lru_cache(maxsize=1)
def load_index():
    return json.loads((ROOT/'data/character-audio-index.json').read_text())


def recording_id(item, index):
    if len(item['text'])!=1:
        return None
    from pypinyin.style.bopomofo import converter
    reading=converter.to_bopomofo(unicodedata.normalize('NFC',item['pinyin']).strip().lower())
    # The MOE places the neutral-tone dot before the syllable.
    if reading.endswith('˙'):
        reading='˙'+reading[:-1]
    for prefix in ('', '（語音）', '（讀音）'):
        audio_id=index['readings'].get(item['text']+'.'+prefix+reading)
        if audio_id:
            return audio_id
    return None


def prepare(item, directory, index):
    import miniaudio
    audio_id=recording_id(item,index)
    if not audio_id:
        return None
    target=directory/(audio_id+'.mp3')
    url=index['recording_base']+audio_id+'.mp3'
    if not target.exists():
        if shutil.which('curl'):
            data=subprocess.run(['curl','--fail','--location','--silent','--show-error',
                                 '--connect-timeout','10','--max-time','30',url],
                                check=True,capture_output=True).stdout
        else:
            with urlopen(url,timeout=30) as response:
                data=response.read(3_000_000)
        if not data.startswith((b'ID3',b'\xff')):
            raise ValueError('The source did not return an MP3 recording.')
        temporary=target.with_suffix('.download')
        temporary.write_bytes(data)
        temporary.replace(target)
    try:
        decoded=miniaudio.decode_file(str(target),nchannels=1,sample_rate=16000)
    except miniaudio.MiniaudioError as error:
        raise ValueError('The source recording could not be decoded.') from error
    samples=decoded.samples
    levels=[math.sqrt(sum(v*v for v in samples[i:i+160])/len(samples[i:i+160]))/32768
            for i in range(0,len(samples),160)]
    # Detect the first utterance, requiring a substantial quiet gap before any narration.
    active=[i for i,v in enumerate(levels) if v>max(.006,max(levels)*.04)]
    groups=[]
    for frame in active:
        if not groups or frame-groups[-1][-1]>12:
            groups.append([frame])
        else:
            groups[-1].append(frame)
    if len(groups)<2 or groups[0][0]>.8*100 or not .18 <= (groups[0][-1]-groups[0][0])/100 <= 2:
        raise ValueError('Could not safely identify the isolated character. No recording was enabled for this entry.')
    end=(groups[0][-1]+1)/100+.15
    next_start=groups[1][0]/100
    if next_start-end < .3:
        raise ValueError('Insufficient silence before narration; recording was not enabled.')
    key=recording_key(item)
    return key,dict(file=target.name,start=max(0,groups[0][0]/100-.10),end=round(end,2),
                    text=item['text'],pinyin=item['pinyin'],source_url=url,
                    source_page='https://stroke-order.learningweb.moe.edu.tw/searchW.jsp?WORD='+quote(item['text']),
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    attribution='Ministry of Education, R.O.C. (Taiwan). Original recording unchanged.')


def save_recording(directory, result):
    """Merge with recordings saved by setup or another playback request."""
    manifest=directory/'index.json'
    with (directory/'index.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        entries=json.loads(manifest.read_text()) if manifest.exists() else {}
        entries[result[0]]=result[1]
        temporary=manifest.with_suffix('.tmp')
        temporary.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
        temporary.replace(manifest)

