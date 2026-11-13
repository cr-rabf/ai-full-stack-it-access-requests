"""Single-host durable attempts, OS ownership locks and atomic export generations."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .exports import SourceDocument
from .review import intake


ROOT = Path(__file__).resolve().parents[1]


def processing_settings(provider):
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return {
        "provider": provider.provenance() if hasattr(provider, "provenance") else {"provider": "mock"},
        "response_source": getattr(provider, "response_source", "mock"),
        "prompt_sha256": digest(getattr(provider, "prompt_path", ROOT / "access_requests/extraction_prompt.txt")),
        "schema_sha256": digest(getattr(provider, "schema_path", ROOT / "snapshot.schema.json")),
        "policy_sha256": digest(getattr(provider, "policy_path", ROOT / "materials/office-policy.md")),
        "routing_sha256": digest(ROOT / "access_requests/review.py"),
    }


class FileLock:
    def __init__(self, path, *, blocking=False):
        self.handle = Path(path).open("a+b")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BaseException:
            self.handle.close()
            raise

    def close(self):
        if not self.handle.closed:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()


@dataclass
class Attempt:
    attempt_id: int
    token: str
    document: SourceDocument
    settings: dict
    record: dict
    reused: bool = False
    lock: FileLock | None = None

    def close(self):
        if self.lock:
            self.lock.close()


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.locks = self.path.with_suffix(self.path.suffix + ".locks")
        self.locks.mkdir(exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL,
                document_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, raw BLOB NOT NULL,
                settings TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS by_document ON attempts(document_id, id)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    def begin(self, document, settings, *, retry=False):
        token = uuid.uuid4().hex
        lock = FileLock(self.locks / token)
        encoded = json.dumps(settings, sort_keys=True)
        try:
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT * FROM attempts WHERE document_id=? ORDER BY id DESC LIMIT 1",
                                      (document.document_id,)).fetchone()
                if (not retry and previous and previous["source_sha256"] == document.source_sha256
                        and previous["settings"] == encoded):
                    db.commit()
                    lock.close()
                    return Attempt(previous["id"], previous["token"], document, settings,
                                   json.loads(previous["result"]), reused=True)
                record = {
                    "document_id": document.document_id, "source_sha256": document.source_sha256,
                    "status": "pending", "owner": "IT Service Desk", "next_action": "resume-extraction",
                    "extraction": None, "error": None, "response_source": settings["response_source"],
                    "processing_settings": settings,
                }
                cursor = db.execute("""INSERT INTO attempts
                    (token, document_id, source_sha256, raw, settings, state, result)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                    (token, document.document_id, document.source_sha256, document.raw_bytes, encoded, "{}"))
                record["attempt_id"] = cursor.lastrowid
                db.execute("UPDATE attempts SET result=? WHERE id=?", (json.dumps(record), cursor.lastrowid))
                db.commit()
                return Attempt(cursor.lastrowid, token, document, settings, record, lock=lock)
        except BaseException:
            lock.close()
            raise

    def complete(self, attempt, result):
        if attempt.reused or attempt.lock is None:
            raise ValueError("Only the owning attempt can publish completion")
        if (result["document_id"] != attempt.document.document_id
                or result["source_sha256"] != attempt.document.source_sha256):
            raise ValueError("Completion source does not match its attempt")
        record = dict(result, attempt_id=attempt.attempt_id, processing_settings=attempt.settings)
        try:
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute("UPDATE attempts SET state='completed', result=? WHERE id=? AND token=? AND state='pending'",
                                    (json.dumps(record), attempt.attempt_id, attempt.token))
                if cursor.rowcount != 1:
                    raise ValueError("Attempt has already completed")
                db.commit()
            return record
        finally:
            attempt.close()

    def process(self, document, provider, *, retry=False):
        attempt = self.begin(document, processing_settings(provider), retry=retry)
        if attempt.reused:
            return attempt.record
        try:
            result, = intake([document], provider)
            return self.complete(attempt, result)
        finally:
            attempt.close()

    def current(self):
        with self.connection() as db:
            return self._current(db)

    @staticmethod
    def _current(db):
        return [json.loads(row[0]) for row in db.execute("""SELECT result FROM attempts
            WHERE id IN (SELECT MAX(id) FROM attempts GROUP BY document_id) ORDER BY document_id""")]

    def history(self, document_id=None):
        with self.connection() as db:
            if document_id is None:
                rows = db.execute("SELECT result FROM attempts ORDER BY id")
            else:
                rows = db.execute("SELECT result FROM attempts WHERE document_id=? ORDER BY id", (document_id,))
            return [json.loads(row[0]) for row in rows]

    def pending(self):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT result FROM attempts WHERE state='pending' ORDER BY id")]

    def claim(self, attempt_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM attempts WHERE id=? AND state='pending'", (attempt_id,)).fetchone()
        if row is None:
            return None
        try:
            lock = FileLock(self.locks / row["token"])
        except BlockingIOError:
            return None
        # Recheck after locking: another resumer may have completed since the read.
        with self.connection() as db:
            if db.execute("SELECT state FROM attempts WHERE id=?", (attempt_id,)).fetchone()[0] != "pending":
                lock.close()
                return None
        raw = row["raw"]
        source = json.loads(raw.decode("utf-8"))
        document = SourceDocument(row["document_id"], raw, row["source_sha256"], source["message"],
                                  {k: v for k, v in source.items() if k != "message"})
        return Attempt(row["id"], row["token"], document, json.loads(row["settings"]),
                       json.loads(row["result"]), lock=lock)

    def export(self, destination, *, fault=None):
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        lock = FileLock(destination / ".publication.lock", blocking=True)
        try:
            with self.connection() as db:
                db.execute("BEGIN")
                records = self._current(db)
                history = [json.loads(r[0]) for r in db.execute("SELECT result FROM attempts ORDER BY id")]
                db.commit()
            generation_id = uuid.uuid4().hex
            generation = destination / "generations" / generation_id
            generation.mkdir(parents=True)
            records = [dict(record, generation_id=generation_id) for record in records]
            self._write(generation / "extractions.jsonl", "".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
            if fault:
                fault("after_extractions")
            queue = [{k: r[k] for k in ("document_id", "attempt_id", "source_sha256", "generation_id",
                                       "status", "owner", "next_action", "error")} for r in records]
            self._write(generation / "queue.json", json.dumps(queue, indent=2) + "\n")
            self._write(generation / "history.jsonl", "".join(json.dumps(r, sort_keys=True) + "\n" for r in history))
            self._sync_directory(generation)
            self._sync_directory(generation.parent)
            for name in ("queue.json", "extractions.jsonl", "history.jsonl"):
                link = destination / name
                if not os.path.lexists(link):
                    link.symlink_to(Path("current") / name)
            temporary = destination / f".current-{generation_id}"
            temporary.symlink_to(Path("generations") / generation_id, target_is_directory=True)
            os.replace(temporary, destination / "current")
            self._sync_directory(destination)
            return generation
        finally:
            lock.close()

    @staticmethod
    def _write(path, text):
        with path.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _sync_directory(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
