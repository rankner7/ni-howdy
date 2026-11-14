"""Check shared phrase/listening pinyin keyboard behavior without learner data."""
import io
import json
import os
import threading
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def run():
    output = io.BytesIO()
    with wave.open(output, 'wb') as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16000)
        clip.writeframes(b'\0\0' * 16000)
    answers = []
    options = {'ta': [{'text': '他', 'pinyin': 'tā'}, {'text': '她', 'pinyin': 'tā'}],
               'wo': [{'text': '我', 'pinyin': 'wǒ'}]}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

        def log_message(self, *args):
            pass

        def send_body(self, body, content_type='application/json'):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/':
                mode = parse_qs(parsed.query).get('mode', ['listening'])[0]
                self.send_body(f'''<main id="main" data-route="{mode}"></main>
                    <script type="module">
                    import {{practice}} from './practice.js';
                    practice('{mode}',{{services:{{audio:true}}}},async()=>{{}},()=>{{}});
                    </script>'''.encode(), 'text/html')
            elif parsed.path == '/api/ime':
                query = parse_qs(parsed.query).get('q', [''])[0]
                self.send_body(json.dumps({'candidates': options.get(query, [])}).encode())
            elif parsed.path == '/api/audio':
                self.send_body(output.getvalue(), 'audio/wav')
            else:
                super().do_GET()

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/api/prompt':
                mode = data['mode']
                result = dict(id=mode, mode=mode, level=0 if mode=='listening' else 2,
                              level_name='Pinyin' if mode=='listening' else 'Hard',
                              levels=['Pinyin', 'English'] if mode=='listening' else ['Easy','Medium','Hard'],
                              failures=0)
            else:
                answers.append(data)
                result = dict(correct=True, message='Correct', details=[], added=[],
                              item=dict(text='他我', pinyin='tā wǒ', answers=['test']))
            self.send_body(json.dumps(result).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ.get('CHROME_PATH', '/usr/bin/google-chrome'),
                headless=True, args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for mode in ('listening', 'phrases'):
                page.goto(f'http://127.0.0.1:{server.server_port}/?mode={mode}')
                composition = page.locator('#pinyin-input')
                composition.wait_for()
                if mode == 'listening':
                    page.locator('.audio-button').click()
                    page.wait_for_function("() => !document.querySelector('.audio-button').disabled")
                before = len(answers)
                # Enter must resolve even a lookup that has not finished yet.
                composition.fill('ta')
                composition.press('Enter')
                page.wait_for_function("() => document.querySelector('#answer').value.length>0")
                assert page.locator('#answer').input_value() == '他'
                assert composition.input_value() == ''
                assert len(answers) == before
                # Unknown input stays in the composer and never submits.
                composition.fill('unknown')
                composition.press('Enter')
                page.get_by_text('No candidates.', exact=False).wait_for()
                assert len(answers) == before
                page.locator('#ime-clear').click()
                composition.fill('ta')
                page.locator('#candidates button').first.wait_for()
                composition.press('2')
                assert composition.input_value() == ''
                assert page.locator('#answer').input_value() == '他她'
                composition.fill('wo')
                composition.press('Space')
                page.wait_for_function("() => document.querySelector('#pinyin-input').value==='' ")
                assert len(answers) == before
                composition.press('Enter')
                page.wait_for_selector('.feedback.success')
                assert len(answers) == before+1
                assert answers[-1]['text'] == '他她我'
            assert not errors, errors
            browser.close()
            print('PASS: phrase and listening composers select with Enter/Space/numbers; only empty Enter submits; unknown input never submits.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    run()
