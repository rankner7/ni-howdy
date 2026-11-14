"""Starter enrollment and upgrade preservation against real local storage."""
import json
import tempfile
import unittest
from pathlib import Path

from nihowdy.content import core_starter_items, load_hanzi
from nihowdy.store import Store


CORE_WORDS = set('''我 你 他 她 我們 你們 人 朋友 老師 學生
你好 謝謝 請 對不起 再見 誰 這 那 這裡 那裡
是 有 在 不 沒有 的 了 嗎 呢 也 都 很 和 什麼 哪裡 怎麼 為什麼 多少 個 杯
要 想 喜歡 可以 會 懂 吃 喝 去 來 回 買 用 看 聽 說 學習 工作 知道 幫忙
水 茶 咖啡 飯 麵 菜 水果 錢 手機 東西 家 學校 商店 餐廳 廁所 車站 捷運 公車 中文 名字
今天 明天 現在 時候 一 二 三 十 兩 塊 好 大 小 多 少 熱 冷 早 晚 忙'''.split())


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'test.sqlite'
        self.store = Store(self.path)

    def test_fresh_install_enrolls_exactly_the_agreed_100_in_both_modes(self):
        core = core_starter_items()
        self.assertEqual(len(core), 100)
        self.assertEqual({i['text'] for i in core}, CORE_WORDS)
        hanzi = load_hanzi()
        for item in core:
            self.assertTrue(all(c in hanzi for c in item['text']), item['text'])
            self.assertTrue(item['answers'])
            self.assertTrue(item['characters'])
            self.assertTrue(item['sources'])
        with self.store.db() as db:
            for mode in ('flashcards', 'drawing'):
                self.assertEqual({r[0] for r in db.execute(
                    'SELECT item_id FROM progress WHERE mode=?', (mode,))}, CORE_WORDS)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM progress WHERE status!='active' OR attempts!=0").fetchone()[0], 0)
        self.assertEqual(self.store.state()['stats']['mastered'], 0)

    def test_upgrade_and_explicit_enrollment_preserve_saved_identity_and_progress(self):
        with self.store.db() as db:
            db.execute("DELETE FROM progress WHERE item_id NOT IN ('我','茶')")
            db.execute("UPDATE progress SET status='mastered',attempts=7,level=2,mastered_on='2026-11-01',checked_on='2099-01-01' WHERE item_id='茶' AND mode='flashcards'")
            tea = dict(self.store._item(db, '茶'), id='saved:tea')
            db.execute('DELETE FROM items WHERE id IN (?,?)', ('茶', '廁所'))
            db.execute('INSERT INTO items VALUES (?,?)', (tea['id'], json.dumps(tea)))
            db.execute("UPDATE progress SET item_id='saved:tea' WHERE item_id='茶'")
            db.execute("DELETE FROM settings WHERE key='core_starter_catalog_version'")
        before = self.store.backup()['tables']['progress']
        self.store = Store(self.path)
        self.assertEqual(self.store.backup()['tables']['progress'], before)
        self.assertEqual(self.store.item('廁所')['text'], '廁所')
        with self.store.db() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM items WHERE id='茶'").fetchone())
        added = self.store.enroll_core_starter()
        self.assertEqual(len(added), 98)
        after = self.store.backup()['tables']['progress']
        self.assertTrue(all(row in after for row in before))
        state = self.store.state()
        self.assertEqual({i['text'] for i in state['items'] if i['enrolled']}, CORE_WORDS)
        self.assertEqual(self.store.enroll_core_starter(), [])
        self.assertEqual(self.store.backup()['tables']['progress'], after)

    def test_explicit_enrollment_restores_deleted_progress_and_stays_deleted_on_restart(self):
        with self.store.db() as db:
            db.execute("UPDATE progress SET attempts=3,level=1 WHERE item_id='水' AND mode='flashcards'")
        before = [p for p in self.store.backup()['tables']['progress'] if p['item_id'] == '水']
        self.store.delete_entries(['水'])
        self.store = Store(self.path)
        with self.store.db() as db:
            self.assertTrue(self.store._item(db, '水', include_deleted=True)['deleted'])
        self.assertEqual(self.store.enroll_core_starter(), ['水'])
        after = [p for p in self.store.backup()['tables']['progress'] if p['item_id'] == '水']
        self.assertEqual(sorted(before, key=lambda p: p['mode']), sorted(after, key=lambda p: p['mode']))
