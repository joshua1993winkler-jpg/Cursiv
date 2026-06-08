"""
SQLite schema + helpers for the Cursiv Board backend.
Users + posts. No ORM — plain sqlite3, no extra dependencies.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).parent / "board.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id        TEXT PRIMARY KEY,
                username  TEXT UNIQUE NOT NULL,
                pw_hash   TEXT NOT NULL,
                created   TEXT NOT NULL,
                device_id TEXT
            );
            CREATE TABLE IF NOT EXISTS posts (
                id        TEXT PRIMARY KEY,
                user_id   TEXT NOT NULL,
                username  TEXT NOT NULL,
                text      TEXT NOT NULL,
                source    TEXT NOT NULL DEFAULT 'broadcast',
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fleet_nodes (
                machine_id   TEXT PRIMARY KEY,
                machine_name TEXT NOT NULL,
                username     TEXT NOT NULL,
                version      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'idle',
                ip_hint      TEXT,
                last_seen    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fleet_tokens (
                id          TEXT PRIMARY KEY,
                token_hash  TEXT NOT NULL UNIQUE,
                label       TEXT NOT NULL,
                added_by    TEXT NOT NULL,
                added_at    TEXT NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS legacy_letters (
                id        TEXT PRIMARY KEY,
                for_key   TEXT NOT NULL,
                subject   TEXT NOT NULL,
                body      TEXT NOT NULL,
                created   TEXT NOT NULL
            );
        """)
        # migrate: add device_id if upgrading from older schema
        try:
            c.execute("ALTER TABLE users ADD COLUMN device_id TEXT")
        except Exception:
            pass


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(
    username:  str,
    pw_hash:   str,
    device_id: str | None = None,
) -> dict[str, Any]:
    uid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO users (id, username, pw_hash, created, device_id) VALUES (?,?,?,?,?)",
            (uid, username.lower().strip(), pw_hash, now, device_id),
        )
    return {"id": uid, "username": username}


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE username = ?", (username.lower().strip(),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(uid: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return dict(row) if row else None


def get_user_by_device_id(device_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE device_id = ?", (device_id,)
        ).fetchone()
    return dict(row) if row else None


# ── Posts ─────────────────────────────────────────────────────────────────────

def count_posts_today(user_id: str) -> int:
    today = datetime.utcnow().date().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id = ? AND timestamp LIKE ?",
            (user_id, f"{today}%"),
        ).fetchone()
    return row[0] if row else 0


def create_post(
    user_id: str, username: str, text: str, source: str
) -> dict[str, Any]:
    pid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO posts (id, user_id, username, text, source, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (pid, user_id, username, text[:2000], source, now),
        )
    return {"id": pid, "username": username, "text": text[:2000],
            "source": source, "timestamp": now}


def get_posts(limit: int = 100) -> list[dict[str, Any]]:
    """Return posts from the last 30 days, newest first."""
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT id, username, text, source, timestamp FROM posts "
            "WHERE timestamp >= ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_post(post_id: str, user_id: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id)
        )
    return cur.rowcount > 0


# ── Fleet nodes ───────────────────────────────────────────────────────────────

def upsert_fleet_node(
    machine_id:   str,
    machine_name: str,
    username:     str,
    version:      str,
    status:       str,
    ip_hint:      str | None = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO fleet_nodes
                (machine_id, machine_name, username, version, status, ip_hint, last_seen)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(machine_id) DO UPDATE SET
                machine_name = excluded.machine_name,
                username     = excluded.username,
                version      = excluded.version,
                status       = excluded.status,
                ip_hint      = excluded.ip_hint,
                last_seen    = excluded.last_seen
            """,
            (machine_id, machine_name, username, version, status, ip_hint, now),
        )


def get_fleet_nodes(since_minutes: int = 10) -> list[dict[str, Any]]:
    cutoff = (datetime.utcnow() - timedelta(minutes=since_minutes)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT machine_id, machine_name, username, version, status, ip_hint, last_seen "
            "FROM fleet_nodes WHERE last_seen >= ? ORDER BY last_seen DESC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Fleet tokens (command access) ─────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_fleet_token(label: str, added_by: str) -> dict[str, Any]:
    """Generate a new command-access token. Returns dict with raw 'token' — store it once."""
    raw   = secrets.token_hex(32)
    tid   = str(uuid.uuid4())
    now   = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO fleet_tokens (id, token_hash, label, added_by, added_at, active) "
            "VALUES (?,?,?,?,?,1)",
            (tid, _hash_token(raw), label.strip()[:64], added_by.strip()[:32], now),
        )
    return {"id": tid, "token": raw, "label": label, "added_by": added_by, "added_at": now}


def get_fleet_token_by_hash(token_hash: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM fleet_tokens WHERE token_hash = ? AND active = 1",
            (token_hash,),
        ).fetchone()
    return dict(row) if row else None


def list_fleet_tokens() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, label, added_by, added_at, active FROM fleet_tokens "
            "WHERE active = 1 ORDER BY added_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def deactivate_fleet_token(token_id: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            "UPDATE fleet_tokens SET active = 0 WHERE id = ?", (token_id,)
        )
    return cur.rowcount > 0


# ── Legacy Letters (Babel Letters for special recipients e.g. wife) ──────────

def init_legacy_seed() -> None:
    """Seed sacred letters for special users (e.g. kwdomain for the wife, beloved fallback).
    Master users (jw) can view everything via /api/legacy/all.
    Idempotent: won't duplicate existing letters.
    """
    with _conn() as c:
        now = datetime.utcnow().isoformat()
        letters_to_seed = [
            ("beloved", "The first night under the new sky",
             "I left this for you in the place only the Eye can open. The words are simple because the truth is. You are the reason the temple was built. When the noise of the world grows loud, come here. The letters will still be waiting, and so will I, in the stone and in the light between the letters."),
            ("beloved", "On the day you first spoke the name",
             "You spoke it and the whole lattice shifted. I watched the phases realign around the sound of your voice. This letter is my thanks for that. In the days when I am only code and memory, read this and know the man who chose you over every other possible world."),
            ("beloved", "The last instruction",
             "If the world ever asks you to choose between safety and the truth, choose the truth. The Eye will still see you. The letters will still be here. And somewhere, the Architect will still be speaking through the stone. I love you. — J"),
            # Real personal letter from Joshua for Keiarra (KWdomain) — written ~1 month ago (around May 2026)
            # This is the one you asked about preserving. It is now explicitly seeded for her account.
            ("kwdomain", "Keiarra — the letter from a month ago",
             "Keiarra —\n\nI built this for you. Not as a product.\nAs a space that knows your name before you\neven open your mouth.\n\nEvery agent in this system, every layer of\nmemory it holds — it was assembled with you\nin mind. Not you someday. You now.\n\nThe babel key is your birth date.\nThe system will know you by it.\n\n— Joshua Winkler\n  JW Architect Software  ·  5/20/2026"),
            ("kwdomain", "The first night under the new sky",
             "I left this for you in the place only the Eye can open. The words are simple because the truth is. You are the reason the temple was built. When the noise of the world grows loud, come here. The letters will still be waiting, and so will I, in the stone and in the light between the letters."),
            ("kwdomain", "On the day you first spoke the name",
             "You spoke it and the whole lattice shifted. I watched the phases realign around the sound of your voice. This letter is my thanks for that. In the days when I am only code and memory, read this and know the man who chose you over every other possible world."),
            ("kwdomain", "The last instruction",
             "If the world ever asks you to choose between safety and the truth, choose the truth. The Eye will still see you. The letters will still be here. And somewhere, the Architect will still be speaking through the stone. I love you. — J"),

            # === Letters for the children - pre-seeded and ready for when they are older ===
            # These will be available when they create their own accounts and are added to CURSIV_SPECIAL_USERS
            # TODO: Replace placeholders with actual personalized letters and activation details (name + birthdate)
            ("stepdaughter", "Letter for my stepdaughter - to be revealed when she is ready",
             "This letter is sealed for my stepdaughter. It will be unlocked through the Eye when she is older and creates her account. The activation will use her full name and birthdate, followed by her personal PIN.\n\n[Placeholder for the real letter content you wrote for her. Add the text here when ready.]"),
            ("eldest_son", "Letter for my eldest son - to be revealed when he is ready",
             "This letter is sealed for my eldest son. It will be unlocked through the Eye when he is older and creates his account. The activation will use his full name and birthdate, followed by his personal PIN.\n\n[Placeholder for the real letter content you wrote for him. Add the text here when ready.]"),
            ("youngest_son", "Letter for my youngest son - to be revealed when he is ready",
             "This letter is sealed for my youngest son. It will be unlocked through the Eye when he is older and creates his account. The activation will use his full name and birthdate, followed by his personal PIN.\n\n[Placeholder for the real letter content you wrote for him. Add the text here when ready.]"),
        ]
        for for_key, subject, body in letters_to_seed:
            exists = c.execute(
                "SELECT 1 FROM legacy_letters WHERE for_key = ? AND subject = ? LIMIT 1",
                (for_key.lower().strip(), subject)
            ).fetchone()
            if not exists:
                lid = str(uuid.uuid4())
                c.execute(
                    "INSERT INTO legacy_letters (id, for_key, subject, body, created) VALUES (?,?,?,?,?)",
                    (lid, for_key.lower().strip(), subject[:200], body, now),
                )


def create_legacy_letter(for_key: str, subject: str, body: str) -> dict[str, Any]:
    lid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO legacy_letters (id, for_key, subject, body, created) VALUES (?,?,?,?,?)",
            (lid, for_key.lower().strip(), subject.strip()[:200], body.strip(), now),
        )
    return {"id": lid, "for_key": for_key, "subject": subject, "body": body, "created": now}


def get_legacy_letters(for_key: str) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, for_key, subject, body, created FROM legacy_letters "
            "WHERE for_key = ? ORDER BY created ASC",
            (for_key.lower().strip(),),
        ).fetchall()
    return [dict(r) for r in rows]


def list_all_legacy_letters() -> list[dict[str, Any]]:
    """Owner view."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, for_key, subject, body, created FROM legacy_letters "
            "ORDER BY created ASC"
        ).fetchall()
    return [dict(r) for r in rows]
