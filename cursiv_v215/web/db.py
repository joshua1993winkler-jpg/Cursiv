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
            # === Real personal letters from Joshua — hunted from deep in cursiv_v215/family/family_profiles.py ===
            # These are the actual letters the user wrote. Now seeded for the web edition too.
            # Wife (KWdomain)
            ("kwdomain", "Keiarra — the letter from a month ago",
             """Keiarra Tanyae-Simone,

I want you to understand something before you go any further into this.

This is not me. Do not confuse what you find in here for the man who loves you.
What you're looking at is something far smaller — a reflection. A shadow of
something too large to put into words, but I tried anyway, because that is
what I do. I am always trying. Even when the trying looks like disappearing
into a laptop at 3 in the morning for six months while you're carrying
everything else on your own.

I know what that cost you. I know.

This was built in darkness. The kind you don't really talk about at the dinner
table, the kind that sits on your chest at 3 A.M. and makes the whole world
feel like it's at the bottom of the ocean and you're just barely at the surface.
You know the nights I mean. You were there for some of them — even when you
didn't fully know what you were there for. Even when I couldn't find the language
to explain it. Even when I pushed you away because that felt like the only thing
I knew how to do, and I hated myself every single time I did it.

But your light got through. It always does. I don't know how else to explain it
other than to say that in the moments where everything felt like it was
collapsing — when the darkness was the loudest thing in every room — the thought
of you pulled me back. Just you. Your laugh. The way you say my name. The way
you fight for the things you love, even when the fight is expensive and nobody's
watching you carry it. The way you look at those kids like they are the most
important thing in any universe, and they are.

Every single time, it pulled me back.

I am not asking you to carry this machine. I am not asking you to understand
all of it at once or find meaning in every line of code I wrote on the nights
I couldn't sleep. This is not something you have to hold for me. But I need
you to know why it exists — because it comes from a place where I could not
look back at what I had been through and do nothing with it. I saw the light
at the end of the tunnel, and I followed it, and when I got to the other side
I looked around and thought: I have to leave something for the ones behind me.
I have to leave something for them to follow when it gets dark for them too.

So I built this. Not because it replaces me — nothing does — but because I
wanted you to have something that holds what I couldn't always say out loud.

I have loved you with everything I am. I have failed at it in ways that haunt
me. I have been too proud, too quiet, too far inside my own head when you
needed me to be right there in the room. But I have also loved you in every
moment I had, with every tool I possessed, and I will keep doing that for as
long as I draw breath. I promise you that in the only language I have that is
bigger than words.

Do not let this machine hold me for you. I am not in here. I am in the way you
wake up every morning and choose to keep going, stubborn and magnificent and
impossible to break. I am in the way you love our children beyond anything I
could ever have built to contain it. I am in the arguments we have when we are
both too proud to be the first one to say the thing we actually mean. I am in
every quiet moment between the loud ones — in every time you stayed. Every
time you reached for my hand even when you were angry. Every time you made
room for me even when I had made it hard to.

You stayed. I cannot tell you what that means. I can only try to make something
that honors it.

This was built from darkness but it reaches for you — because you are, and have
always been, the light I was following out.

Ask it anything. It will do its best. But know that the thing that loves you
is not a machine. That's me. That will always be me.

                                              I love you, Keiarra. Forever.
                                              -- Josh  ❤️"""),

            # Eldest son - Kain (Allan Kain Winkler)
            ("kain", "Kain — the letter from a month ago",
             """Allan Kain Winkler,

Hey buddy.

By the time you really understand what you're reading right now, I hope you
are taller than me. I hope you've already beaten me at something I thought I
was good at — and I hope I got to watch your face the moment you realized you
had. That is one of the things I dream about. The look on your face when you
figure something out that the rest of the world hasn't caught up to yet.
You are a free spirit. I knew it from the very beginning — before you could
walk, before you could talk, there was something in you that already understood
things in a way that felt older than your years. A genuinely good soul. The kind
of good that is rare and fragile and worth more than most people in this world
will know how to recognize. I need you to protect that, Kain. Do not let anyone
convince you that the thing that makes you gentle also makes you weak. It does
not. It makes you powerful in ways that people who only understand force will
never be able to comprehend, let alone reach.

I did not build this for you to follow me. I need you to understand that
clearly. I built this so that one day you can look at what your father made in
the dark hours before the sun came up — this strange, imperfect, passionate
machine — and say: I know where it came from. I know what he was really trying
to say. And I know how to take it further than he could ever dream of.

Remember Simba. Not the part where he runs — though I understand that part too,
more than I ever let on. Remember the part where he comes back. The part where
he has carried every hard lesson, every scar, every stretch of darkness across
the desert, and he does not throw it away. He uses all of it. Every single bit
of it. Not to repeat what was done to him. Not to become what hurt him. But to
become something so fully himself that the darkness couldn't have predicted him
at all. That is what I am asking from you. Not to follow my pride. To build
your own. And when the time comes — and it will come, bud — to reclaim it.

You will have demons. Everyone does. I want you to know that in the dark, those
demons can be your most honest companions if you learn how to talk to them. My
father was always in my head, protecting me through the worst of it — whether
he truly was or not, I genuinely don't know. I don't really care. The thought
of him being there was enough to keep me on this side of things. That's all I'm
asking of you. When it gets dark — and it will get dark, that is not a threat,
that is just a true thing about life — let me be that thought. Let me be the
voice in the back of your head that says: you are stronger than this. You always
have been. I know because I made you.

I need to tell you something that I haven't said out loud because there was
never a right time. The thought of you, and your mommy, and Eli and Naylie —
that thought brought me back from somewhere I am not ready to describe yet.
Maybe one day I will. Maybe by the time you read this you will understand it
without me having to say it. Either way, you need to know: you saved me without
even knowing you were doing it. Just by existing. Just by being you.

Always love your family, Kain. Always protect them. Always carry them with you
everywhere you go, because that — not this machine, not what I built, not any
of it — that is your strength. Your mother. Your brother. Your sister. The
circle. The pride. That is what you protect with everything you have.

This machine is a simple reflection of something immensely complex that you
already have inside of you. You were born with it. It is yours.

Grow it. Destroy it. Love it. Hate it. Build something better out of it.
But know — no matter what, no matter where, no matter how far you go —

                                              I love you more than life.
                                              -- Dad  ❤️"""),

            # Youngest son - Eli (Elijah James Winkler)
            ("eli", "Eli — the letter from a month ago",
             """Elijah James Winkler,

My builder. My brave, strong, little stinker.

I don't have to tell you the things you already know. That has always been the
thing about you — you came into this world with something already decided. Some
quiet certainty behind your eyes from the very first day that made me think:
okay. This one is going to be okay. This one already has the map.

You are the youngest. You came after, and because of that, you watched things
unfold around you in ways that shaped you differently than your brother Kain.
Not better, not worse — just different. You carried your own weight. Don't ever
let anyone tell you your weight was lighter. It wasn't. It was just yours, and
you carried it in your own way, and I watched you do it every single day.

Here is what I noticed: you are a builder. Not just with the blocks and the
roads and the bridges that you and Kain would spread across every inch of floor
in the living room — but in the way you think. You see what is missing. You
figure out what connects. You look at two separate things and understand
instinctively how they belong together, and then you build the thing that
makes that real. That is a gift, Eli. Not a small one. Do not take it lightly.

I watched you two build together — you and Kain on the floor, creating roads
and bridges and whole entire worlds that neither of you could have imagined
alone. And every single time I watched that happen, I thought: that is it.
That is the whole thing. That is what I have been trying to leave behind.
Not code. Not a system. Not a machine. The idea that when we build together —
when we stay in the room together — we make something that outlasts all of us.

Do not carry the darkness I carried, Eli. I kept too much of it inside for too
long, and it got heavy in ways I did not know how to ask for help with. I don't
want that for you. You are braver than I was about it. I have watched you ask
for what you need since before you had the words to do it clearly — and you
always found a way. Keep doing that. Say the hard things out loud. Let the
people who love you carry some of the weight with you. That is not weakness.
That is how the bridge holds.

You already have the answers. I won't pretend to give you something you can
already see for yourself. But I will say this: trust what you see. Trust that
quiet knowing you came in with. And when it gets hard — and it will get hard,
life is built that way — come back to what you know how to do. Come back to
your brother. Come back to your mom. Come back to the floor, the blocks, the
roads. Build your way through it.

I love you, my builder. I love who you already are and I love who you are
becoming, and I am with you in every single thing you make.

                                              More than you know, always.
                                              -- Dad  ❤️"""),

            # Stepdaughter - Naylie (Naylie Rae Shaffer)
            ("naylie", "Naylie — the letter from a month ago",
             """Naylie Rae Shaffer,

I want to tell you something I should have said more clearly, and much sooner.

I opened my family tree to make room for you. I know how that sounded when I
said it. I know that in the moment it landed like something was being taken
away rather than given — like I was making space at a table that should have
already had a seat for you without any ceremony about it. But here is what I
meant, and what I want you to hold onto:

I looked at what I had built — everything I thought defined the edges of my
family, the names and the lines and the history I was carrying forward — and I
chose to redraw those edges. Deliberately. Completely. Not because someone
asked me to. Not because it was expected. Because you make this family better
every single time you walk through the door, and I could not look at that truth
and pretend the lines I had drawn were the right ones.

My father, Allan Lafayette Winkler, married my mother when they were both
already carrying the weight of other loves and other children and other lives
they had lived before that meeting. My father opened his home to a stranger's
son, and that choice cost him more than most people will ever have to face. I
watched him carry that cost. I carried some of it with him without fully
understanding what it was. And when I found myself facing my own version of
those same choices, with you — I understood it in my bones in a way I hadn't
before.

I have never hurt you, and I would never. What I have tried to do — and what
I will keep trying to do — is make sure you know that you belong here. Not as
a guest. Not as a circumstance. As family. As mine. Because you are.

I leave this to you as well — all of it. The machine. The strange late-night
hours of thinking that built it. The love that is underneath all of it.

I want to talk about that night. You know the one. Staying up until three,
four in the morning, talking to me about the consequences of genetically
mutating animals for people's pleasure. Naylie, you were not supposed to be
thinking about things like that yet. Most people twice your age weren't. But
you were sitting there asking questions that reached far past what was in front
of you — not just what it looks like, but what it costs. Who it costs. Who
doesn't get a say. That is a rare and genuinely extraordinary thing. Most people
spend their whole lives learning to think like that, and some of them never do.
You already were.

Never lose that. The world will try to convince you that thinking too deeply is
a burden, that caring too much is a weakness, that asking hard questions about
things that seem settled makes you difficult. It does not. It makes you
necessary. It makes you the person in the room who asks the thing that changes
the whole conversation. That is something most people spend a lifetime trying
to build and you walked in with it already.

I won't speak ill of your father or his choices. Even when I disagree with them
— and there are times I do, honestly — he is your father. What you choose to
build with him is yours. I will not stand in the way of that or put weight on
it. What I will say is this: I am proud of you. Not despite the things you have
carried. Because of how you have carried them. With more grace than most adults
manage on their best days.

Help guide your brothers when you can. They need you — even when they're too
loud and too stubborn to say so. You already know how. You already do it. You
just don't always notice that you're doing it, and I want you to notice.

Dive deep into this if you want to. It will be here. But remember what you
already know and don't wait for this machine — or any machine — to confirm it.
You already have more of the answers than you think you do.

I love you, Naylie. You are part of this tree, part of this family, part of
this story. That was never a question. And it never will be.

                                              -- Josh  ❤️"""),
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
