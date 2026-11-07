import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime


class History:
    def __init__(self, path):
        self.path = path
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(
                    id INTEGER PRIMARY KEY, created TEXT NOT NULL,
                    root TEXT NOT NULL, root_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS moves(
                    id INTEGER PRIMARY KEY, session INTEGER NOT NULL REFERENCES sessions,
                    entry TEXT NOT NULL, target TEXT NOT NULL, digest TEXT,
                    state TEXT NOT NULL DEFAULT 'planned', note TEXT NOT NULL DEFAULT '');
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def begin(self, snapshot, moves):
        with self.connection() as db:
            session = db.execute("INSERT INTO sessions(created,root,root_id) VALUES (?,?,?)",
                                 (datetime.now().astimezone().isoformat(timespec="seconds"),
                                  str(snapshot.root), json.dumps(snapshot.root_id))).lastrowid
            db.executemany("INSERT INTO moves(session,entry,target) VALUES (?,?,?)",
                           ((session, json.dumps(asdict(m.entry)), m.target) for m in moves))
        return session

    def rows(self, session):
        with self.connection() as db:
            return db.execute("SELECT * FROM moves WHERE session=? ORDER BY id", (session,)).fetchall()

    def set_state(self, row_id, state, note="", digest=None):
        with self.connection() as db:
            db.execute("UPDATE moves SET state=?,note=?,digest=COALESCE(?,digest) WHERE id=?",
                       (state, note, digest, row_id))

    def sessions(self):
        with self.connection() as db:
            return [dict(r) for r in db.execute("""
                SELECT s.*, COUNT(m.id) AS total,
                  SUM(m.state IN ('moved','restoring','restored')) AS moved,
                  SUM(m.state='restored') AS restored,
                  SUM(m.state='moved') AS available,
                  SUM(m.state IN ('moving','restoring','planned')) AS pending,
                  SUM(m.state='moved' AND m.note!='') AS undo_errors
                FROM sessions s JOIN moves m ON s.id=m.session
                GROUP BY s.id ORDER BY s.id DESC""")]

    def latest_undo(self):
        return next((s for s in self.sessions() if s["available"]), None)


def status(s):
    if s["pending"]:
        return "Needs review"
    if s["moved"] and s["restored"] == s["moved"]:
        return "Undone" if s["moved"] == s["total"] else "Partial session · moves undone"
    if s["restored"] or s["undo_errors"]:
        return "Undo incomplete"
    if s["moved"] == s["total"]:
        return "Success"
    return "Partial success" if s["moved"] else "Failed"

