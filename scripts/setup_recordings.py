"""Prepare Taiwan MOE character recordings for personal offline practice.

Original files remain unchanged. Playback stops after the character, before the
following radical/stroke-count narration. No external requests occur at playback.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata
from urllib.request import urlopen
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def prepare(item, directory, index):
    import miniaudio
    from pypinyin.style.bopomofo import converter
    if len(item['text'])!=1:
        return None
    reading=converter.to_bopomofo(item['pinyin'])
    audio_id=index['readings'].get(item['text']+'.'+reading)
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
    decoded=miniaudio.decode_file(str(target),nchannels=1,sample_rate=16000)
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
        raise ValueError('Could not safely identify the isolated character. Keeping synthesis for this entry.')
    end=(groups[0][-1]+1)/100+.15
    next_start=groups[1][0]/100
    if next_start-end < .3:
        raise ValueError('Insufficient silence before narration; recording was not enabled.')
    key=unicodedata.normalize('NFC',item['text']+'|'+item['pinyin'].strip().lower())
    return key,dict(file=target.name,start=max(0,groups[0][0]/100-.10),end=round(end,2),
                    text=item['text'],pinyin=item['pinyin'],source_url=url,
                    source_page='https://stroke-order.learningweb.moe.edu.tw/searchW.jsp?WORD='+quote(item['text']),
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    attribution='Ministry of Education, R.O.C. (Taiwan). Original recording unchanged.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default=str(ROOT/'.data'))
    parser.add_argument('--characters',help='Optional subset of starter characters, e.g. 我好')
    args=parser.parse_args()
    directory=Path(args.data_dir)/'audio/recordings'
    directory.mkdir(parents=True,exist_ok=True)
    manifest=directory/'index.json'
    entries=json.loads(manifest.read_text()) if manifest.exists() else {}
    index=json.loads((ROOT/'data/character-audio-index.json').read_text())
    items=[i for i in json.loads((ROOT/'data/starter.json').read_text()) if i['kind']=='word' and len(i['text'])==1 and (not args.characters or i['text'] in args.characters)]
    def task(item):
        try:
            result=prepare(item,directory,index)
            return result,None
        except Exception as error:
            return None,f"{item['text']}: {error}"
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result,error in pool.map(task,items):
            if result:
                entries[result[0]]=result[1]
                temporary=manifest.with_suffix('.tmp')
                temporary.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
                temporary.replace(manifest)
                print(f"Prepared {result[1]['text']} ({result[1]['pinyin']}) from Taiwan MOE recording.",flush=True)
            elif error:
                print('Skipped '+error,flush=True)
    temporary=manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(manifest)
    print(f'{len(entries)} reading-specific recordings are ready offline.',flush=True)


if __name__=='__main__':
    main()
