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
