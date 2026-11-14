"""Focused browser check for silent Hard phrases and optional final punctuation.

Run: .venv/bin/python scripts/phrase_hard_check.py
Uses a temporary database and a local loopback server.
"""
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nihowdy.server import Handler
from tests.test_answers import PhraseGradingStoreTests


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


def run():
    fixture = PhraseGradingStoreTests()
    fixture.setUp()
    prompt_id = fixture.prompt(level=2)
    with fixture.store.db() as db:
        db.execute("UPDATE progress SET checked_on='2099-01-01' WHERE status='mastered'")
    server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    server.store = fixture.store
    server.audio = SimpleNamespace(available=lambda: False)
    server.content = SimpleNamespace(enabled=lambda: False)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/google-chrome',
                                                 headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.add_init_script("localStorage.setItem('nihowdy:example:phrases:2', 'yes')")
            errors, audio_requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: audio_requests.append(request.url)
                    if '/api/audio?prompt=' in request.url else None)
            page.goto(base + '/#phrases', wait_until='networkidle')
            page.wait_for_selector('#answer')
            assert page.locator('.pill').first.inner_text() == 'Hard'
            assert page.locator('.audio-button').count() == 0
            assert page.locator('#answer').evaluate("e => e.dispatchEvent(new KeyboardEvent('keydown', {key:'p',ctrlKey:true,bubbles:true,cancelable:true}))")
            assert page.locator('.answer-rule, .practice-aside, .prompt-content .eyebrow').count() == 0
            assert page.locator('h1').inner_text() == 'Phrases'
            page.wait_for_timeout(700)  # Beyond the usual 500 ms autoplay delay.
            assert audio_requests == []
            denied = page.request.get(base + '/api/audio?prompt=' + prompt_id)
            assert denied.status == 400
            assert 'Hard phrase' in denied.json()['error']
            page.locator('#answer').fill('我喜歡喝咖啡')
            page.locator('#pinyin-input').press('Enter')
            page.wait_for_selector('.feedback.success')
            assert fixture.store.item('phrase:我喜歡喝咖啡。')['text'] == '我喜歡喝咖啡。'
            assert not errors, errors
            browser.close()
        print('PASS: Hard phrases hide Listen, make no autoplay request, reject direct audio, and accept Chinese without a final mark.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        fixture.doCleanups()


if __name__ == '__main__':
    run()
