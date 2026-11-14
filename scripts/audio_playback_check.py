"""Check recorded-audio autoplay recovery in Chrome without changing learner data."""
import io
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import wave

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def run():
    output=io.BytesIO()
    with wave.open(output,'wb') as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16000)
        clip.writeframes(b'\0\0'*16000)
    recording=output.getvalue()
    prompt={'id':'recorded-xue','text':'學','pinyin':'xué','level':0,
            'levels':['Easy','Medium','Hard'],'level_name':'Easy','failures':0}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(ROOT/'web'),**kwargs)

        def log_message(self,*args):
            pass

        def send_body(self,body,content_type,headers=None):
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            for key,value in (headers or {}).items():
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            self.send_body(json.dumps(prompt).encode(),'application/json')

        def do_GET(self):
            if self.path=='/':
                self.send_body(b'''<main id="main" data-route="flashcards"></main>
                    <script type="module">
                    import {practice} from './practice.js';
                    practice('flashcards',{services:{audio:true}},async()=>{},()=>{});
                    </script>''','text/html')
            elif self.path.startswith('/api/audio?'):
                self.send_body(recording,'audio/wav',{'X-Audio-Start':'0','X-Audio-End':'0.69'})
            else:
                super().do_GET()

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(
                executable_path=os.environ.get('CHROME_PATH','/usr/bin/google-chrome'),
                headless=True,args=['--no-sandbox','--autoplay-policy=document-user-activation-required'])
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script('''
                window.audioContexts=[];
                const NativeAudioContext=window.AudioContext;
                window.AudioContext=class extends NativeAudioContext {
                    constructor(...args){super(...args);this.suspend();window.audioContexts.push(this);}
                    // Model browsers that leave resume() pending until a user gesture.
                    resume(){
                        if(!this.autoplayAttempted){this.autoplayAttempted=true;return new Promise(()=>{});}
                        return super.resume();
                    }
                };
            ''')
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function("() => window.audioContexts.length===1")
            page.wait_for_function("() => !document.querySelector('.audio-button').disabled",timeout=5000)
            assert 'Select the audio button' in page.locator('.audio-status').inner_text(),page.evaluate("({status:document.querySelector('.audio-status').textContent,error:document.querySelector('#practice-error').textContent,state:window.audioContexts[0].state})")
            assert page.evaluate("window.audioContexts[0].state")=='suspended'
            page.locator('.audio-button').click()
            page.wait_for_function("() => !document.querySelector('.audio-button').disabled")
            assert page.evaluate("window.audioContexts[0].state")=='running'
            assert page.locator('.audio-status').inner_text()==''
            assert page.locator('#practice-error').inner_text()==''
            page.locator('.audio-button').click()
            page.wait_for_function("() => !document.querySelector('.audio-button').disabled")
            assert not errors,errors
            browser.close()
            print('PASS: blocked recorded-audio autoplay releases the button; clicking starts playback and replay works.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__=='__main__':
    run()
