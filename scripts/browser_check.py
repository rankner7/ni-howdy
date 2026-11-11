"""Isolated end-to-end checks using an installed Chrome and Playwright.

Run: .venv/bin/python scripts/browser_check.py
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nihowdy.store import Store


def run():
    with tempfile.TemporaryDirectory(prefix='ni-howdy-browser-') as directory:
        db_path=Path(directory)/'nihowdy.sqlite'
        store=Store(db_path)
        store.import_dictionary()
        (Path(directory)/'models').symlink_to(ROOT/'.data/models', target_is_directory=True)
        (Path(directory)/'audio').mkdir()
        (Path(directory)/'audio/recordings').symlink_to(ROOT/'.data/audio/recordings', target_is_directory=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        log=(ROOT/'artifacts/browser-server.log').open('w')
        server=subprocess.Popen([sys.executable,'-m','nihowdy.server','--port',str(port),'--data-dir',directory],cwd=ROOT,stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(base+'/api/state',timeout=1)
                    break
                except (OSError,TimeoutError):
                    time.sleep(.1)
            else:
                raise AssertionError('Local server did not start.')
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(executable_path=os.environ.get('CHROME_PATH','/usr/bin/google-chrome'), headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
                errors=[]
                external_requests=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:external_requests.append(request.url) if not request.url.startswith((base+'/', 'blob:', 'data:')) else None)
                page.goto(base,wait_until='networkidle')
                assert 'Small steps.' in page.locator('h1').inner_text()
                page.screenshot(path=str(ROOT/'artifacts/home-desktop.png'),full_page=True)
                page.get_by_role('button',name='Personalise my topics').click()
                page.locator('#interest-text').fill('Coffee and computers')
                page.get_by_role('button',name='Save my interests').click()
                page.wait_for_selector('dialog',state='hidden')

                def configure(word,mode,level):
                    with store.db() as db:
                        db.execute('DELETE FROM progress')
                        store._enroll(db,word)
                        # Admission is tested through the library flow below;
                        # isolate each practice mode with an already-admitted item.
                        db.execute('INSERT OR IGNORE INTO progress(item_id,mode,level) VALUES (?,?,?)',(word,mode,level))
                        db.execute('DELETE FROM progress WHERE mode!=?',(mode,))
                        db.execute('UPDATE progress SET level=?,status=\'active\'',(level,))
                        db.execute('UPDATE prompts SET finished=1')

                def navigate(mode):
                    page.goto(base+'/#'+mode,wait_until='networkidle')
                    page.reload(wait_until='networkidle')
                    page.wait_for_timeout(250)
                    if page.locator('dialog[open]').count():
                        page.get_by_role('button',name='Got it. Let’s practise').click()

                configure('電腦','flashcards',0)
                navigate('flashcards')
                assert page.locator('.prompt-hanzi').inner_text()=='電腦'
                page.locator('#answer').fill('Computer')
                page.get_by_role('button',name='Check answer').click()
                page.wait_for_selector('.feedback.success')
                page.get_by_role('button',name='Next prompt').click()
                page.wait_for_timeout(250)
                if page.locator('dialog[open]').count():page.get_by_role('button',name='Got it. Let’s practise').click()
                assert page.locator('.prompt-content .pinyin').count()==0
                page.get_by_role('button',name='Play Mandarin pronunciation').click()
                page.locator('.audio-status').filter(has_text='locally generated').wait_for(timeout=30000)
                page.screenshot(path=str(ROOT/'artifacts/flashcards-desktop.png'),full_page=True)
                # Case ignored, punctuation remains significant.
                page.locator('#answer').fill('computer.')
                page.get_by_role('button',name='Check answer').click()
                page.wait_for_selector('.feedback.retry')

                for character in ['我','好']:
                    configure(character,'flashcards',2)
                    navigate('flashcards')
                    page.evaluate("""() => {
                        window.scheduledAudio = [];
                        const start = AudioBufferSourceNode.prototype.start;
                        AudioBufferSourceNode.prototype.start = function(...args) {
                            window.scheduledAudio.push({args, fullDuration:this.buffer.duration});
                            return start.apply(this,args);
                        };
                    }""")
                    page.get_by_role('button',name='Play Mandarin pronunciation').click()
                    page.locator('.audio-status').filter(has_text='Ministry of Education recording').wait_for(timeout=10000)
                    scheduled=page.evaluate('window.scheduledAudio')
                    assert len(scheduled)==1 and .3 < scheduled[0]['args'][2] < 1
                    assert scheduled[0]['fullDuration'] > 5  # Never play the following narration.

                configure('電腦','flashcards',2)
                navigate('flashcards')
                assert page.locator('.prompt-hanzi').count()==0
                assert page.locator('.prompt-content .pinyin').count()==0
                page.get_by_role('button',name='Show explanation and count one incorrect attempt').click()
                page.wait_for_selector('dialog[open] .entry-heading')
                page.get_by_role('button',name='Close dialog').click()
                page.locator('#answer').fill('computer')
                page.get_by_role('button',name='Check answer').click()
                page.wait_for_selector('.feedback.retry')
                assert 'remains one incorrect attempt' in page.locator('.feedback').inner_text()

                configure('好','drawing',0)
                navigate('drawing')
                page.wait_for_selector('.component-piece')
                page.screenshot(path=str(ROOT/'artifacts/components-desktop.png'),full_page=True)
                with store.db() as db:
                    payload=json.loads(db.execute("SELECT payload FROM prompts WHERE mode='drawing' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
                for i,component in enumerate(payload['drawing'][0]['components']):
                    page.locator('[data-piece="'+component['id']+'"]').click()
                    page.locator('[data-slot="'+str(i)+'"]').click()
                page.get_by_role('button',name='Check entry').click()
                page.wait_for_selector('.feedback.success')

                # Empty missing-stroke templates must fail as a whole word.
                configure('電腦','drawing',1)
                navigate('drawing')
                page.get_by_role('button',name='Save character & continue').click()
                assert 'Character 2 of 2' in page.locator('.drawing-progress').inner_text()
                page.get_by_role('button',name='Check entry').click()
                page.wait_for_selector('.feedback.retry')
                page.get_by_role('button',name='Next prompt').click()
                page.wait_for_selector('canvas')
                with store.db() as db:
                    plan=json.loads(db.execute("SELECT payload FROM prompts WHERE mode='drawing' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
                for index,character in enumerate(plan['drawing']):
                    box=page.locator('canvas').bounding_box()
                    for stroke_index in character['missing']:
                        points=[[x,900-y] for x,y in store.hanzi[character['character']]['medians'][stroke_index]]
                        page.mouse.move(box['x']+points[0][0]/1024*box['width'],box['y']+points[0][1]/1024*box['height'])
                        page.mouse.down()
                        for x,y in points[1:]:page.mouse.move(box['x']+x/1024*box['width'],box['y']+y/1024*box['height'],steps=3)
                        page.mouse.up()
                    page.get_by_role('button',name='Check entry' if index==len(plan['drawing'])-1 else 'Save character & continue').click()
                page.wait_for_selector('.feedback.success')

                configure('一','drawing',3)
                navigate('drawing')
                page.wait_for_selector('canvas')
                box=page.locator('canvas').bounding_box()
                # A reference-shaped stroke, deliberately drawn backwards.
                for stroke in reversed(store.hanzi['一']['medians']):
                    points=[[x,900-y] for x,y in reversed(stroke)]
                    page.mouse.move(box['x']+points[0][0]/1024*box['width'],box['y']+points[0][1]/1024*box['height'])
                    page.mouse.down()
                    for x,y in points[1:]:page.mouse.move(box['x']+x/1024*box['width'],box['y']+y/1024*box['height'],steps=5)
                    page.mouse.up()
                page.get_by_role('button',name='Check entry').click()
                page.wait_for_selector('.feedback.success')

                phrase='phrase:我也要喝茶。'
                configure(phrase,'phrases',2)
                with store.db() as db:
                    for word,mode in [('我','flashcards'),('也','drawing'),('要','flashcards'),('喝','drawing')]:
                        store._enroll(db,word)
                        db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode=?",(word,mode))
                navigate('phrases')
                page.wait_for_selector('#pinyin-input')
                for pinyin,char in [('wo','我'),('ye','也'),('yao','要'),('he','喝'),('cha','茶')]:
                    page.locator('#pinyin-input').fill(pinyin)
                    page.locator('#candidates button').filter(has=page.locator('span',has_text=char)).first.click()
                page.get_by_role('button',name='。',exact=True).click()
                assert page.locator('#answer').input_value()=='我也要喝茶。'
                page.screenshot(path=str(ROOT/'artifacts/phrases-desktop.png'),full_page=True)
                page.get_by_role('button',name='Check answer').click()
                page.wait_for_selector('.feedback.success')

                navigate('library')
                # Explicit requests for compounds wait for all meaningful parts.
                page.get_by_role('button',name='Add an example').click()
                page.locator('#entry-search').fill('毛衣')
                page.wait_for_selector('.add-result')
                page.locator('.add-result').first.click()
                page.locator('.add-result').filter(has_text='Waiting for prerequisites').first.wait_for()
                page.get_by_role('button',name='Close dialog').click()
                navigate('library')
                sweater=page.locator('.word-card').filter(has=page.locator('.word-glyph',has_text=re.compile('^毛衣$')))
                assert 'Waiting to join your deck' in sweater.inner_text()
                sweater.get_by_role('button',name='Add prerequisite words').click()
                page.wait_for_timeout(250)
                assert page.locator('.word-card').filter(has=page.locator('.word-glyph',has_text=re.compile('^毛衣$'))).get_by_role('button',name='Waiting for prerequisites').is_disabled()
                with store.db() as db:
                    for row in db.execute('SELECT id,data FROM items').fetchall():
                        item=json.loads(row['data'])
                        if item['text'] in ['毛','衣']:
                            mode='flashcards' if item['text']=='毛' else 'drawing'
                            db.execute("UPDATE progress SET status='review' WHERE item_id=? AND mode=?",(row['id'],mode))
                navigate('library')
                sweater=page.locator('.word-card').filter(has=page.locator('.word-glyph',has_text=re.compile('^毛衣$')))
                assert sweater.locator('.word-progress>span').count()==2
                assert sweater.locator('.word-prerequisites').count()==0

                page.get_by_role('button',name='Add an example').click()
                page.locator('#entry-search').fill('coffee')
                page.wait_for_selector('.add-result')
                page.locator('.add-result').first.click()
                page.locator('.add-result').filter(has_text='Added').first.wait_for()
                page.get_by_role('button',name='Close dialog').click()

                # Generate from a category, then from a specific mastered word.
                page.locator('.generate-entries').click()
                page.locator('#generator-category').select_option('food')
                page.locator('#generator-count').fill('2')
                page.locator('.generator-submit').click()
                page.wait_for_selector('.generated-list article')
                assert page.locator('.generated-list article').count()==2
                assert '163,701' in page.locator('dialog').inner_text()
                page.get_by_role('button',name='Close dialog').click()
                page.wait_for_selector('.word-card')
                drink=page.locator('.word-card').filter(has=page.locator('.word-glyph',has_text=re.compile('^喝$')))
                drink.locator('.generate-related').click()
                page.wait_for_selector('dialog[open] #generator-source')
                assert page.locator('#generator-source').input_value()=='word'
                assert page.locator('#generator-word').input_value()=='喝'
                page.locator('#generator-count').fill('1')
                page.locator('.generator-submit').click()
                page.wait_for_selector('.generated-list article')
                page.get_by_role('button',name='Close dialog').click()
                page.wait_for_selector('.word-card')

                coffee=page.locator('.word-card').filter(has=page.locator('.word-glyph',has_text=re.compile('^咖啡$')))
                coffee.locator('.delete-entry').click()
                coffee.wait_for(state='detached')
                page.locator('#toast .toast-action').click()
                coffee.wait_for()
                # Batch deletion and undo operate only on unmastered selections.
                boxes=page.locator('.select-entry')
                assert boxes.count()>=2
                boxes.nth(0).check()
                boxes.nth(1).check()
                assert '2' in page.locator('.delete-selected').inner_text()
                page.locator('.delete-selected').click()
                page.locator('#toast').filter(has_text='Deleted 2').wait_for()
                page.locator('#toast .toast-action').click()
                page.wait_for_selector('.select-entry')
                protected=page.request.post(base+'/api/delete-entries',data={'ids':['喝']})
                assert protected.status==400

                page.set_viewport_size({'width':390,'height':844})
                navigate('home')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ROOT/'artifacts/home-mobile.png'),full_page=True)
                navigate('library')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ROOT/'artifacts/library-mobile.png'),full_page=True)
                assert not errors, errors
                assert not external_requests, external_requests
                browser.close()
                print('PASS: desktop/mobile, interests, flashcards/audio/grading, hint penalty, components, missing strokes, multi-character progress, free drawing, phrase IME, dictionary additions, category/mastered-word generation, deletion/Undo, and no external browser requests.')
        finally:
            server.terminate()
            server.wait(timeout=10)
            log.close()


if __name__=='__main__':
    (ROOT/'artifacts').mkdir(exist_ok=True)
    run()
