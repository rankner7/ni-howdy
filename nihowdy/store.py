"""Transactional local persistence and practice orchestration."""
import hashlib
import json
import random
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from itertools import islice
from time import monotonic
from zoneinfo import ZoneInfo

from .content import (component_groups, construction, dictionary_rows, infer_topic, load_hanzi,
                      plain_pinyin, sources_for, starter_items)
from .learning import (LEVELS, correct_answer, phrase_coverage, review_trials,
                       shape_score, transition, weight, weighted_choice, weighted_sample)
from .vocabulary import VocabularyPolicy, reading_key


def encode(value):
    return json.dumps(value, ensure_ascii=False)


class Store:
    def __init__(self, path, rng=None, now=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rng = rng or random.Random()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.hanzi = load_hanzi()
        self.vocabulary = VocabularyPolicy()
        self._neighbor_cache = {}
        self._parts_cache = {}
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS progress(
                    item_id TEXT, mode TEXT, learner TEXT DEFAULT 'local', level INTEGER,
                    failures INTEGER DEFAULT 0, boost INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active', mastered_on TEXT, checked_on TEXT,
                    cycle INTEGER DEFAULT 0, eligible_after INTEGER DEFAULT 0,
                    PRIMARY KEY(item_id,mode,learner));
                CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    active INTEGER DEFAULT 1, created_at TEXT);
                CREATE TABLE IF NOT EXISTS prompts(id TEXT PRIMARY KEY, session_id INTEGER,
                    item_id TEXT, mode TEXT, level INTEGER, payload TEXT, scored INTEGER DEFAULT 0,
                    hint INTEGER DEFAULT 0, finished INTEGER DEFAULT 0, result TEXT);
                CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, prompt_id TEXT UNIQUE,
                    item_id TEXT, mode TEXT, correct INTEGER, hint INTEGER, created_at TEXT);
                CREATE TABLE IF NOT EXISTS trials(item_id TEXT, mode TEXT, cycle INTEGER,
                    day TEXT, draw REAL, selected INTEGER, PRIMARY KEY(item_id,mode,cycle,day));
                CREATE TABLE IF NOT EXISTS expansions(item_id TEXT PRIMARY KEY, added TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY, text TEXT, message TEXT);
                CREATE TABLE IF NOT EXISTS dictionary(id INTEGER PRIMARY KEY, traditional TEXT,
                    simplified TEXT, pinyin TEXT, plain TEXT, meanings TEXT);
                CREATE INDEX IF NOT EXISTS dict_form ON dictionary(traditional);
                CREATE INDEX IF NOT EXISTS dict_pinyin ON dictionary(plain);
            """)
            for key, value in {"probability": .05, "timezone": "America/New_York", "interests": [],
                               "interest_text": "", "onboarded": False, "schema": 1}.items():
                db.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (key, encode(value)))
            if not db.execute("SELECT 1 FROM items LIMIT 1").fetchone():
                for item in starter_items():
                    db.execute("INSERT INTO items VALUES (?,?)", (item["id"], encode(item)))
                for word in ["我", "你", "也", "要", "喝", "水", "茶", "好", "一", "二", "三", "電腦"]:
                    if not self._enroll(db, word):
                        self._add_prerequisites(db,self._item(db,word))
                for item in self._items(db).values():
                    if item["kind"] == "phrase":
                        self._enroll(db, item["id"])

    @contextmanager
    def db(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            try:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def import_dictionary(self, progress=None):
        report = progress or (lambda message: None)
        started = monotonic()
        with self.db() as db:
            version = db.execute("SELECT value FROM settings WHERE key='dictionary_version'").fetchone()
            if not db.execute("SELECT 1 FROM dictionary LIMIT 1").fetchone() or not version or version[0] != '2':
                report("Building the local dictionary index (first launch or data update)…")
                db.execute("DELETE FROM dictionary")
                rows = iter(dictionary_rows())
                count = 0
                while batch := list(islice(rows, 5000)):
                    db.executemany("INSERT INTO dictionary(traditional,simplified,pinyin,plain,meanings) VALUES (?,?,?,?,?)", batch)
                    count += len(batch)
                    report(f"  Indexed {count:,} entries ({monotonic()-started:.1f}s)…")
                db.execute("INSERT OR REPLACE INTO settings VALUES ('dictionary_version','2')")
            else:
                count = db.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0]
                report(f"Using the existing dictionary index ({count:,} entries).")
        report(f"Dictionary ready in {monotonic()-started:.1f}s.")
        self._parts_cache.clear()
        self._neighbor_cache.clear()

    def _settings(self, db):
        return {r["key"]: json.loads(r["value"]) for r in db.execute("SELECT * FROM settings")}

    def _today(self, db):
        return self.now().astimezone(ZoneInfo(self._settings(db)["timezone"])).date().isoformat()

    def _items(self, db):
        return {r["id"]: json.loads(r["data"]) for r in db.execute("SELECT * FROM items")}

    def _item(self, db, item_id):
        row = db.execute("SELECT data FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ValueError("This entry no longer exists.")
        return json.loads(row["data"])

    def lowest(self, item, mode):
        return 1 if mode == "drawing" and not any(component_groups(c, self.hanzi) for c in item["text"]) else 0

    def _enroll(self, db, item_id, after=0):
        item = self._item(db, item_id)
        if item['kind']=='word' and not db.execute('SELECT 1 FROM progress WHERE item_id=?',(item_id,)).fetchone():
            missing=self._missing_prerequisites(db,item)
            if missing:
                item['requested']=True
                db.execute('UPDATE items SET data=? WHERE id=?',(encode(item),item_id))
                return False
        modes = ["phrases"] if item["kind"] == "phrase" else ["flashcards", "drawing"]
        for mode in modes:
            if mode == "drawing" and not all(c in self.hanzi for c in item["text"]):
                continue
            db.execute("INSERT OR IGNORE INTO progress(item_id,mode,level,eligible_after) VALUES (?,?,?,?)",
                       (item_id, mode, self.lowest(item, mode), after))
        if item["kind"] == "word":
            self._generate_template(db, item, after)
        return True

    def _lexeme(self, db, text, pinyin):
        for row in db.execute("SELECT data FROM items WHERE json_extract(data,'$.text')=? AND json_extract(data,'$.kind')='word'",(text,)):
            item=json.loads(row[0])
            if reading_key(item['pinyin'])==reading_key(pinyin):
                return dict(text=text,pinyin=item['pinyin'],english=item['english'],id=item['id'])
        for row in db.execute('SELECT * FROM dictionary WHERE traditional=? ORDER BY id',(text,)):
            if reading_key(row['pinyin'])==reading_key(pinyin):
                return dict(text=text,pinyin=row['pinyin'],english=json.loads(row['meanings'])[0],
                            id=None,dictionary_id=row['id'])
        if len(text)==1 and text in self.hanzi:
            data=self.hanzi[text]
            readings=data.get('pinyin') or []
            if isinstance(readings,str):
                readings=readings.split(',')
            if any(reading_key(p)==reading_key(pinyin) for p in readings) and data.get('definition'):
                return dict(text=text,pinyin=pinyin,english=data['definition'].split(';')[0],id=None)
        return None

    def _missing_prerequisites(self, db, item):
        if item['kind']!='word' or len(item['text'])<2:
            return []
        mastered=set()
        for row in db.execute("SELECT DISTINCT i.data FROM items i JOIN progress p ON p.item_id=i.id WHERE p.mode IN ('flashcards','drawing') AND p.status IN ('mastered','review')"):
            entry=json.loads(row[0])
            mastered.add((entry['text'],reading_key(entry['pinyin'])))
        key=(item['text'],item['pinyin'])
        if key not in self._parts_cache:
            self._parts_cache[key]=self.vocabulary.parts(item,lambda text,pinyin:self._lexeme(db,text,pinyin))
        parts=self._parts_cache[key]
        return [p for p in parts if (p['text'],reading_key(p['pinyin'])) not in mastered]

    def _activate_waiting(self, db):
        for item in list(self._items(db).values()):
            if item.get('requested') and not db.execute('SELECT 1 FROM progress WHERE item_id=?',(item['id'],)).fetchone():
                if not self._missing_prerequisites(db,item):
                    self._enroll(db,item['id'])

    def _addition_result(self, db, item, enrolled):
        missing=[] if enrolled else self._missing_prerequisites(db,item)
        return {'item':item,'queued':not enrolled,'missing_prerequisites':missing,
                'message':'Added to your practice library.' if enrolled else
                          'Waiting for mastery of: '+', '.join(p['text']+' ('+p['english']+')' for p in missing)+'.'}

    def add_prerequisites(self, item_id):
        with self.db() as db:
            return self._add_prerequisites(db,self._item(db,item_id))

    def _add_prerequisites(self, db, parent):
        added=[]
        for part in self._missing_prerequisites(db,parent):
            current=self._lexeme(db,part['text'],part['pinyin'])
            if not current:
                continue
            if current.get('id'):
                item=self._item(db,current['id'])
            elif current.get('dictionary_id'):
                row=db.execute('SELECT * FROM dictionary WHERE id=?',(current['dictionary_id'],)).fetchone()
                item=self._dictionary_item(db,row,current['english'])
            else:
                text=current['text']
                item=dict(id=text+':component:'+reading_key(current['pinyin']),kind='word',text=text,
                          pinyin=current['pinyin'],english=current['english'],answers=[current['english']],
                          chinese_answers=[text],topic=parent['topic'],tokens=[],region='TW',script='Hant',status='ready',
                          explanation='A meaningful part of '+parent['text']+'.',
                          explanation_origin='Source-backed character construction',
                          characters=construction(text,self.hanzi),sources=sources_for(text))
                db.execute('INSERT OR IGNORE INTO items VALUES (?,?)',(item['id'],encode(item)))
            self._enroll(db,item['id'])
            added.append(item['text'])
        return {'added':added,'message':'Added prerequisite vocabulary: '+', '.join(added)+'.'}

    def _generate_template(self, db, item, after):
        """Cache a productive sentence template for suitable concrete nouns."""
        if item["topic"] not in ("food", "clothing", "technology") or item["text"] in ("喝", "吃", "電", "腦", "手", "網路"):
            return
        meaning = item["english"]
        if len(meaning) > 40 or meaning.startswith("to ") or "(" in meaning or ";" in meaning:
            return
        noun = next((a for a in item["answers"] if a.startswith(("a ", "an "))), meaning)
        tokens = ["我", "也", "要", "買", item["id"]]
        text = "我也要買" + item["text"] + "。"
        pinyin = "wǒ yě yào mǎi " + item["pinyin"]
        english = "I also want to buy " + noun + "."
        phrase = dict(id="phrase:"+text, kind="phrase", text=text, pinyin=pinyin,
                      english=english, answers=[english], chinese_answers=[text], tokens=tokens,
                      topic=item["topic"], region="TW", script="Hant", status="ready", characters=[],
                      explanation="Subject + 也 (also) + 要 (want) + 買 (buy) + object. 也 comes before the verb phrase.",
                      explanation_origin="Generated locally from a constrained grammar template",
                      sources=item["sources"])
        db.execute("INSERT OR IGNORE INTO items VALUES (?,?)", (phrase["id"], encode(phrase)))
        self._enroll(db, phrase["id"], after)

    def _mastered(self, db):
        return {r[0] for r in db.execute("SELECT item_id FROM progress WHERE mode IN ('flashcards','drawing') AND status IN ('mastered','review')")}

    def _reviews(self, db):
        today = self._today(db)
        probability = self._settings(db)["probability"]
        for p in db.execute("SELECT * FROM progress WHERE status='mastered'").fetchall():
            trials = review_trials(p["checked_on"], today, probability, self.rng)
            for day, draw, selected in trials:
                db.execute("INSERT INTO trials VALUES (?,?,?,?,?,?)", (p["item_id"], p["mode"], p["cycle"], day, draw, selected))
                db.execute("UPDATE progress SET checked_on=?, status=? WHERE item_id=? AND mode=?",
                           (day, "review" if selected else "mastered", p["item_id"], p["mode"]))

    def _session(self, db):
        row = db.execute("SELECT id FROM sessions WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            return row[0]
        return db.execute("INSERT INTO sessions(created_at) VALUES (?)", (self.now().isoformat(),)).lastrowid

    def new_session(self):
        with self.db() as db:
            db.execute("UPDATE sessions SET active=0")
            self._reviews(db)
            session = self._session(db)
        return {"session": session}

    def state(self):
        with self.db() as db:
            self._reviews(db)
            self._activate_waiting(db)
            mastered = self._mastered(db)
            session = self._session(db)
            for row in db.execute("SELECT item_id,added FROM expansions").fetchall():
                if len(json.loads(row["added"])) < 2:
                    self._fill_expansion(db, self._item(db, row["item_id"]), session, json.loads(row["added"]))
            items = self._items(db)
            progress = [dict(r) for r in db.execute("SELECT * FROM progress")]
            enrolled = {p["item_id"] for p in progress}
            for item in items.values():
                item["enrolled"] = item["id"] in enrolled
                item["progress"] = [p for p in progress if p["item_id"] == item["id"]]
                if item['kind']=='word':
                    item['frequency_count']=self.vocabulary.addition_weight(item['text'])
                    item['missing_prerequisites']=[] if item['enrolled'] else self._missing_prerequisites(db,item)
                    item['waiting']=bool(item.get('requested') and not item['enrolled'])
                if item["kind"] == "phrase":
                    item["coverage"] = phrase_coverage(item["tokens"], mastered)
                    item["missing"] = [t for t in dict.fromkeys(item["tokens"]) if t not in mastered]
            count = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            correct = db.execute("SELECT COUNT(*) FROM attempts WHERE correct=1").fetchone()[0]
            recent = [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT 8")]
            pending = [dict(r) for r in db.execute("SELECT * FROM pending")]
            unfinished = [dict(item_id=r["item_id"], remaining=2-len(json.loads(r["added"])))
                          for r in db.execute("SELECT * FROM expansions") if len(json.loads(r["added"])) < 2]
            return {"settings": self._settings(db), "items": list(items.values()), "session": session,
                    "stats": {"attempts": count, "correct": correct, "mastered": len(mastered),
                              "reviews": sum(p["status"] == "review" for p in progress),
                              "active": sum(p["status"] == "active" for p in progress)},
                    "recent": recent, "pending": pending, "pending_expansions": unfinished}

    def update_settings(self, values):
        allowed = {"probability", "timezone", "interests", "interest_text", "onboarded"}
        if set(values) - allowed:
            raise ValueError("Unknown setting.")
        if "probability" in values and (not isinstance(values["probability"], (int, float)) or not 0 <= values["probability"] <= 1):
            raise ValueError("Review probability must be between 0 and 1.")
        if "timezone" in values:
            try:
                ZoneInfo(values["timezone"])
            except Exception as exc:
                raise ValueError("Choose a valid timezone.") from exc
        if "interests" in values and (not isinstance(values["interests"], list) or not all(isinstance(t, str) for t in values["interests"])):
            raise ValueError("Interests must be a list of topics.")
        if "interest_text" in values and (not isinstance(values["interest_text"], str) or len(values["interest_text"]) > 2000):
            raise ValueError("Keep interests under 2,000 characters.")
        with self.db() as db:
            for key, value in values.items():
                db.execute("UPDATE settings SET value=? WHERE key=?", (encode(value), key))
            if "interests" in values or "interest_text" in values:
                settings = self._settings(db)
                text = settings["interest_text"].casefold()
                for item in self._items(db).values():
                    if item["kind"] != "word":
                        continue
                    if item["topic"] in settings["interests"] or (text and any(a.casefold() in text for a in item["answers"] if len(a) > 3)):
                        if self._missing_prerequisites(db,item):
                            continue
                        # A small opening deck leaves room for mastery-triggered expansion.
                        existing = db.execute("SELECT COUNT(*) FROM progress p JOIN items i ON i.id=p.item_id WHERE p.mode='flashcards' AND json_extract(i.data,'$.topic')=?", (item["topic"],)).fetchone()[0]
                        if existing < 4:
                            self._enroll(db, item["id"])
        return {"saved": True}

    def _drawing_plan(self, item, level):
        result = []
        for index, ch in enumerate(item["text"]):
            data = self.hanzi[ch]
            groups = component_groups(ch, self.hanzi)
            if level == 0 and not groups:
                continue
            n = len(data["strokes"])
            missing = sorted(self.rng.sample(range(n), max(1, min(3, n // 3)))) if level in (1, 2) else list(range(n))
            components = []
            if level == 0:
                for group in groups:
                    points = [p for s in group for p in data["medians"][s]]
                    components.append({"id": uuid.uuid4().hex[:8], "strokes": [data["strokes"][s] for s in group],
                                       "center": [sum(p[0] for p in points)/len(points), 900-sum(p[1] for p in points)/len(points)]})
            result.append({"index": index, "character": ch, "missing": missing,
                           "template": [s for j, s in enumerate(data["strokes"]) if j not in missing],
                           "components": components})
        return result

    def next_prompt(self, mode):
        if mode not in LEVELS:
            raise ValueError("Choose a practice mode.")
        with self.db() as db:
            self._reviews(db)
            self._activate_waiting(db)
            session = self._session(db)
            outstanding = db.execute("SELECT * FROM prompts WHERE session_id=? AND mode=? AND finished=0 ORDER BY rowid DESC LIMIT 1", (session, mode)).fetchone()
            if outstanding:
                return self._public_prompt(db, outstanding)
            mastered = self._mastered(db)
            candidates = []
            for row in db.execute("SELECT * FROM progress WHERE mode=? AND status!='mastered' AND eligible_after<?", (mode, session)):
                item = self._item(db, row["item_id"])
                if mode == "phrases" and phrase_coverage(item["tokens"], mastered) < .8:
                    continue
                candidates.append((row["item_id"], weight(dict(row), self.lowest(item, mode))))
            previous = db.execute("SELECT item_id FROM prompts WHERE session_id=? AND mode=? ORDER BY rowid DESC LIMIT 1", (session, mode)).fetchone()
            if previous and len(candidates) > 1:
                candidates = [c for c in candidates if c[0] != previous[0]]
            selected = weighted_choice(candidates, self.rng)
            if selected is None:
                return {"empty": True, "mode": mode, "message": "No eligible phrases yet. Master at least 80% of a phrase's words in flashcards or drawing." if mode == "phrases" else "Your eligible deck is complete. Start a new session for newly added words, or come back for daily reviews."}
            item = self._item(db, selected)
            progress = db.execute("SELECT * FROM progress WHERE item_id=? AND mode=?", (selected, mode)).fetchone()
            plan = {"drawing": self._drawing_plan(item, progress["level"])} if mode == "drawing" else {}
            prompt_id = uuid.uuid4().hex
            db.execute("INSERT INTO prompts(id,session_id,item_id,mode,level,payload) VALUES (?,?,?,?,?,?)",
                       (prompt_id, session, selected, mode, progress["level"], encode(plan)))
            return self._public_prompt(db, db.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone())

    def _public_prompt(self, db, row):
        item = self._item(db, row["item_id"])
        mode, level = row["mode"], row["level"]
        p = db.execute("SELECT * FROM progress WHERE item_id=? AND mode=?", (row["item_id"], mode)).fetchone()
        out = {"id": row["id"], "mode": mode, "level": level, "level_name": LEVELS[mode][level],
               "levels": LEVELS[mode], "hint": bool(row["hint"]), "review": p["status"] == "review",
               "failures": p["failures"], "topic": item["topic"], "session": row["session_id"],
               "finished": bool(row["finished"])}
        if mode == "drawing" or (mode == "phrases" and level == 2):
            out["english"] = item["english"]
        if (mode == "flashcards" and level < 2) or (mode == "phrases" and level < 2):
            out["text"] = item["text"]
        if (mode in ("flashcards", "phrases") and level == 0) or (mode == "drawing" and level <= 1):
            out["pinyin"] = item["pinyin"]
        if mode == "drawing":
            out["characters"] = [{"index": d["index"], "template": d["template"],
                                   "slots": [{"id": c["id"], "center": c["center"]} for c in d["components"]],
                                   "components": [{"id": c["id"], "strokes": c["strokes"]} for c in sorted(d["components"], key=lambda x:x["id"])]}
                                  for d in json.loads(row["payload"])["drawing"]]
            out["total_characters"] = len(item["text"])
        if row["result"]:
            out["result"] = json.loads(row["result"])
        return out

    def _prompt(self, db, prompt_id):
        row = db.execute("SELECT p.* FROM prompts p JOIN sessions s ON s.id=p.session_id WHERE p.id=? AND s.active=1", (prompt_id,)).fetchone()
        if not row:
            raise ValueError("This practice session has ended. Start a new prompt.")
        return row

    def _expand(self, db, item, session):
        if item["kind"] != "word":
            return []
        row = db.execute("SELECT added FROM expansions WHERE item_id=?", (item["id"],)).fetchone()
        if row:
            return []
        db.execute("INSERT INTO expansions VALUES (?, '[]')", (item["id"],))
        return self._fill_expansion(db, item, session, [])

    def _fill_expansion(self, db, item, session, existing):
        enrolled = {r[0] for r in db.execute("SELECT DISTINCT item_id FROM progress")}
        enrolled_forms={self._item(db,item_id)['text'] for item_id in enrolled}
        candidates = [i for i in self._items(db).values() if i["kind"] == "word" and
                      ((item["topic"] != "custom" and i["topic"] == item["topic"]) or item["id"] in i.get("related_to", [])) and i['text'] not in enrolled_forms and
                      self.vocabulary.addition_weight(i['text'])>0 and
                      all(c in self.hanzi for c in i["text"]) and not self._missing_prerequisites(db,i)]
        candidates.extend(self._dictionary_neighbors(db, item, enrolled | {i["id"] for i in candidates}))
        unique={}
        for entry in candidates:
            if entry['text'] not in enrolled_forms:
                unique.setdefault(entry['text'],entry)
        added=weighted_sample([(entry,self.vocabulary.addition_weight(entry['text'])) for entry in unique.values()],2-len(existing),self.rng)
        for entry in added:
            db.execute('INSERT OR IGNORE INTO items VALUES (?,?)',(entry['id'],encode(entry)))
            self._enroll(db, entry["id"], after=session)
        db.execute("UPDATE expansions SET added=? WHERE item_id=?", (encode(existing+[i["id"] for i in added]), item["id"]))
        return [i["text"] for i in added]

    def _dictionary_neighbors(self, db, item, exclude):
        """Prepare contextual candidates locally when the curated topic pool runs low."""
        terms = {
            "clothing":["shirt","sweater","socks","jacket","clothing","shoes"],
            "technology":["computer","keyboard","telephone","software","printer"],
            "food":["tea","coffee","milk","fruit","bread","rice"],
            "travel":["train","bus","ticket","station","transport"],
            "people":["student","teacher","school","friend","family"],
            "essentials":["person","good","small","big"],
        }.get(item["topic"], [w for w in re.findall(r"[a-z]+",item["english"].lower()) if len(w)>3][:2])
        if not terms:
            return []
        existing_forms = {i["text"] for i in self._items(db).values()}
        cache_key=tuple(terms)
        if cache_key not in self._neighbor_cache:
            self._neighbor_cache[cache_key]=[dict(row) for row in db.execute("SELECT * FROM dictionary WHERE length(traditional)<=4 AND (" +
                          " OR ".join("meanings LIKE ?" for _ in terms) + ") ORDER BY id", ["%"+t+"%" for t in terms])]
        rows=self._neighbor_cache[cache_key]
        prepared=[]
        for row in rows:
            form=row["traditional"]
            if form in existing_forms or not self.vocabulary.addition_weight(form) or not all(c in self.hanzi for c in form):
                continue
            meanings=json.loads(row["meanings"])
            sense=next((s for s in meanings if len(s)<=40 and s[:1].islower() and not re.search(r"[()\[\];]",s) and
                        any(re.search(r"\b"+re.escape(t)+(r"\b" if t in {'good','big','small'} else r"s?\b"),s) for t in terms)),None)
            if not sense:
                continue
            entry=dict(id=form+":"+hashlib.sha256((row["pinyin"]+sense).encode()).hexdigest()[:8],
                       kind="word",text=form,pinyin=row["pinyin"],english=sense,answers=[sense],
                       chinese_answers=[form],topic=item["topic"],tokens=[],region="TW",script="Hant",status="ready",
                       related_to=[item["id"]],explanation="Related vocabulary selected from local dictionary meanings. Explore its character construction below.",
                       explanation_origin="Dictionary-backed construction; fuller explanation available with an optional provider",
                       characters=construction(form,self.hanzi),sources=sources_for(form))
            if entry["id"] in exclude or self._missing_prerequisites(db,entry):
                continue
            prepared.append(entry);existing_forms.add(form)
        return prepared

    def _score(self, db, prompt, correct, hint=False):
        item = self._item(db, prompt["item_id"])
        old = dict(db.execute("SELECT * FROM progress WHERE item_id=? AND mode=?", (item["id"], prompt["mode"])).fetchone())
        updated = transition(old, correct, self.lowest(item, prompt["mode"]), len(LEVELS[prompt["mode"]])-1, self._today(db))
        if updated["status"] == "mastered":
            updated["cycle"] += 1
        columns = ["level", "failures", "boost", "attempts", "status", "mastered_on", "checked_on", "cycle"]
        db.execute("UPDATE progress SET " + ",".join(c+"=?" for c in columns) + " WHERE item_id=? AND mode=?",
                   [updated[c] for c in columns] + [item["id"], prompt["mode"]])
        db.execute("INSERT INTO attempts(prompt_id,item_id,mode,correct,hint,created_at) VALUES (?,?,?,?,?,?)",
                   (prompt["id"], item["id"], prompt["mode"], correct, hint, self.now().isoformat()))
        self._activate_waiting(db)
        added = self._expand(db, item, prompt["session_id"]) if updated["status"] == "mastered" else []
        db.execute("UPDATE prompts SET scored=1, hint=? WHERE id=?", (hint, prompt["id"]))
        if updated["status"] == "mastered":
            message = "Mastered! This item is resting in your bin."
        elif updated["level"] > old["level"]:
            message = f"Moving up to {LEVELS[prompt['mode']][updated['level']]} next time."
        elif updated["level"] < old["level"]:
            message = "Three consecutive misses. Moving down one level."
        elif updated["boost"] > old["boost"]:
            message = "We'll practise this more often. Its selection weight has increased."
        else:
            message = f"{updated['failures']} of 3 consecutive misses at this level."
        return {"correct": correct, "hint": hint, "message": message, "progress": updated, "added": added}

    def info(self, prompt_id):
        with self.db() as db:
            prompt = self._prompt(db, prompt_id)
            if not prompt["scored"]:
                result = self._score(db, prompt, False, hint=True)
                db.execute("UPDATE prompts SET result=? WHERE id=?", (encode(result), prompt_id))
            return {"item": self._item(db, prompt["item_id"]), "penalty": not prompt["finished"]}

    def answer(self, prompt_id, answer):
        with self.db() as db:
            prompt = self._prompt(db, prompt_id)
            if prompt["finished"]:
                return json.loads(prompt["result"])
            item = self._item(db, prompt["item_id"])
            details = []
            if prompt["mode"] == "drawing":
                plans = json.loads(prompt["payload"])["drawing"]
                drawings = answer.get("drawings", [])
                if len(drawings) != len(plans):
                    raise ValueError("Complete each character before submitting the entry.")
                for drawing, plan in zip(drawings, plans):
                    if prompt["level"] == 0:
                        expected = [c["id"] for c in plan["components"]]
                        details.append({"correct": drawing.get("placements") == expected})
                    else:
                        strokes = drawing.get("strokes", [])
                        if not isinstance(strokes, list) or len(strokes) > 80 or any(not isinstance(s, list) or len(s) > 1000 for s in strokes):
                            raise ValueError("Drawing is too large. Clear it and try again.")
                        for s in strokes:
                            for point in s:
                                if not isinstance(point, list) or len(point) != 2 or any(not isinstance(v, (int, float)) or not -100 <= v <= 1124 for v in point):
                                    raise ValueError("Invalid drawing coordinates.")
                        data = self.hanzi[plan["character"]]
                        reference = [[[x, 900-y] for x, y in data["medians"][j]] for j in plan["missing"]]
                        details.append(shape_score(strokes, reference, normalize=prompt["level"]==3))
                correct = all(d["correct"] for d in details)
            else:
                text = answer.get("text", "")
                if not isinstance(text, str) or len(text) > 2000:
                    raise ValueError("Enter a short text answer.")
                accepted = item["chinese_answers"] if prompt["mode"] == "phrases" and prompt["level"] == 2 else list(item["answers"])
                if prompt["mode"] == "flashcards" and prompt["level"] == 2:
                    # Identical audio readings must accept every known homophone sense.
                    for other in self._items(db).values():
                        if other["kind"] == "word" and other["pinyin"] == item["pinyin"]:
                            accepted.extend(other["answers"])
                correct = correct_answer(text, accepted)
            if prompt["scored"]:
                result = json.loads(prompt["result"])
                result.update(answer_correct=correct, message="Information was opened, so this remains one incorrect attempt. " + result["message"])
            else:
                result = self._score(db, prompt, correct)
            result.update(item=item, details=details)
            db.execute("UPDATE prompts SET finished=1,result=? WHERE id=?", (encode(result), prompt_id))
            return result

    def audio_item(self, prompt_id):
        with self.db() as db:
            prompt = self._prompt(db, prompt_id)
            return self._item(db, prompt["item_id"])

    def item(self, item_id):
        with self.db() as db:
            return self._item(db, item_id)

    def search(self, query):
        query = query.strip()[:100]
        if not query:
            return []
        with self.db() as db:
            known = [dict(i, source="catalog") for i in self._items(db).values() if query.casefold() in
                     (i["text"]+" "+i["english"]+" "+plain_pinyin(i["pinyin"])).casefold()]
            # Literal LIKE escaping avoids wildcards expanding a user query.
            pattern = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            rows = db.execute("SELECT * FROM dictionary WHERE traditional=? OR simplified=? OR plain=? OR meanings LIKE ? ESCAPE '\\' ORDER BY length(traditional),id LIMIT 30",
                              (query, query, plain_pinyin(query), "%"+pattern+"%"))
            catalog_matches = tuple(known)
            for r in rows:
                meanings = [meaning for meaning in json.loads(r["meanings"]) if not any(
                    item["text"] == r["traditional"] and item["pinyin"] == r["pinyin"] and
                    correct_answer(meaning, item["answers"]) for item in catalog_matches)]
                if meanings:
                    known.append({"id": r["id"], "source": "dictionary", "text": r["traditional"],
                                  "pinyin": r["pinyin"], "english": meanings[0],
                                  "meanings": meanings, "kind": "word"})
            return known[:35]

    def ime(self, query):
        query = plain_pinyin(query[:80])
        if not query:
            return []
        with self.db() as db:
            seen, result = set(), []
            for i in self._items(db).values():
                if i["kind"] == "word" and plain_pinyin(i["pinyin"]) == query:
                    seen.add(i["text"])
                    result.append({"text": i["text"], "pinyin": i["pinyin"]})
            for r in db.execute("SELECT traditional,pinyin FROM dictionary WHERE plain=? ORDER BY length(traditional),id LIMIT 100", (query,)):
                if r[0] not in seen:
                    result.append({"text": r[0], "pinyin": r[1]})
                    seen.add(r[0])
            return result[:50]

    def add(self, values):
        with self.db() as db:
            if values.get("source") == "catalog":
                item = self._item(db, values["id"])
                enrolled=self._enroll(db, item["id"])
                return self._addition_result(db,item,enrolled)
            if values.get("source") != "dictionary":
                text = str(values.get("text", "")).strip()[:500]
                if not text:
                    raise ValueError("Enter a word or phrase to validate.")
                pending_id = hashlib.sha256(text.encode()).hexdigest()[:20]
                message = "No validated match yet. Configure the optional explanation service and use Validate pending, or choose a dictionary match. This entry is not in your graded deck."
                db.execute("INSERT OR IGNORE INTO pending VALUES (?,?,?)", (pending_id, text, message))
                return {"pending": True, "id": pending_id, "message": message}
            row = db.execute("SELECT * FROM dictionary WHERE id=?", (values.get("id"),)).fetchone()
            if not row:
                raise ValueError("Choose a dictionary result first.")
            meanings = json.loads(row["meanings"])
            sense = values.get("meaning", meanings[0])
            if sense not in meanings:
                raise ValueError("Choose a validated dictionary meaning.")
            item=self._dictionary_item(db,row,sense)
            enrolled=self._enroll(db,item['id'])
            return self._addition_result(db,item,enrolled)

    def _dictionary_item(self, db, row, sense):
        for existing in self._items(db).values():
            if existing['text']==row['traditional'] and reading_key(existing['pinyin'])==reading_key(row['pinyin']) and correct_answer(sense,existing['answers']):
                return existing
        form=row['traditional']
        if not all(c in self.hanzi for c in form):
            raise ValueError('This entry has characters outside the local drawing dataset. Choose another entry for now.')
        item_id=form+':'+hashlib.sha256((row['pinyin']+sense).encode()).hexdigest()[:8]
        item=dict(id=item_id,kind='word',text=form,pinyin=row['pinyin'],english=sense,
                  answers=[sense],chinese_answers=[form],topic=infer_topic([sense]),
                  tokens=[],region='TW',script='Hant',status='ready',
                  explanation='Local dictionary entry. Character construction is shown below. Generate a sourced explanation to add a fuller contextual note.',
                  explanation_origin='Dictionary-backed construction; LLM explanation not generated yet',
                  characters=construction(form,self.hanzi),sources=sources_for(form))
        db.execute('INSERT OR IGNORE INTO items VALUES (?,?)',(item_id,encode(item)))
        return item

    def backup(self):
        with self.db() as db:
            tables = ["settings", "items", "progress", "sessions", "prompts", "attempts", "trials", "expansions", "pending"]
            return {"format": "ni-howdy", "version": 1,
                    "tables": {t: [dict(r) for r in db.execute("SELECT * FROM "+t)] for t in tables}}

    def restore(self, backup):
        if backup.get("format") != "ni-howdy" or backup.get("version") != 1:
            raise ValueError("Choose a Ni-howdy version 1 backup.")
        allowed = ["settings", "items", "progress", "sessions", "prompts", "attempts", "trials", "expansions", "pending"]
        if set(backup.get("tables", {})) != set(allowed):
            raise ValueError("Backup is incomplete.")
        with self.db() as db:
            for table in allowed:
                columns = [r[1] for r in db.execute("PRAGMA table_info("+table+")")]
                rows = backup["tables"][table]
                if not isinstance(rows, list) or any(set(row) != set(columns) for row in rows):
                    raise ValueError("Invalid backup records.")
                db.execute("DELETE FROM "+table)
                db.executemany("INSERT INTO "+table+"("+",".join(columns)+") VALUES ("+",".join("?" for _ in columns)+")",
                               [[row[c] for c in columns] for row in rows])
            settings = self._settings(db)
            if not 0 <= settings["probability"] <= 1:
                raise ValueError("Invalid review probability in backup.")
            ZoneInfo(settings["timezone"])
            self._items(db)  # Validate JSON before committing the replacement.
        return {"restored": True}
