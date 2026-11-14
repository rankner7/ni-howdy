"""Prepare Taiwan MOE character recordings for personal offline practice.

Original files remain unchanged. Playback stops after the character, before the
following radical/stroke-count narration. No external requests occur at playback.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

from nihowdy.recordings import load_index, prepare, recording_key, save_recording


def recording_items(data_dir, characters=None):
    items=json.loads((ROOT/'data/starter.json').read_text())
    database=Path(data_dir)/'nihowdy.sqlite'
    if database.exists():
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as connection:
            items.extend(json.loads(row[0]) for row in connection.execute('SELECT data FROM items'))
    readings={}
    for item in items:
        if item['kind']=='word' and len(item['text'])==1 and (not characters or item['text'] in characters):
            key=recording_key(item)
            readings[key]=item
    return list(readings.values())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default=str(ROOT/'.data'))
    parser.add_argument('--characters',help='Optional subset of starter or library characters, e.g. 我好聲')
    args=parser.parse_args()
    directory=Path(args.data_dir)/'audio/recordings'
    directory.mkdir(parents=True,exist_ok=True)
    manifest=directory/'index.json'
    index=load_index()
    items=recording_items(args.data_dir,args.characters)
    def task(item):
        try:
            result=prepare(item,directory,index)
            return result,None
        except Exception as error:
            return None,f"{item['text']}: {error}"
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result,error in pool.map(task,items):
            if result:
                save_recording(directory,result)
                print(f"Prepared {result[1]['text']} ({result[1]['pinyin']}) from Taiwan MOE recording.",flush=True)
            elif error:
                print('Skipped '+error,flush=True)
    entries=json.loads(manifest.read_text()) if manifest.exists() else {}
    print(f'{len(entries)} reading-specific recordings are ready offline.',flush=True)


if __name__=='__main__':
    main()
