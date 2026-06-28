import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant dans Railway Variables.")
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id TEXT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stage TEXT DEFAULT 'new',
        client_type TEXT DEFAULT 'cold',
        interest_score INTEGER DEFAULT 0,
        age_confirmed INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0,
        last_message TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT,
        preferred_language TEXT DEFAULT '',
        last_intent TEXT DEFAULT '',
        conversation_tone TEXT DEFAULT 'balanced',
        last_offer_message_count INTEGER DEFAULT 0,
        age_gate_count INTEGER DEFAULT 0,
        sexual_profile TEXT DEFAULT '',
        buyer_profile TEXT DEFAULT '',
        fantasies_detected TEXT DEFAULT '',
        objections_detected TEXT DEFAULT '',
        trust_level INTEGER DEFAULT 0,
        last_confusion TEXT DEFAULT ''
    )
    """)

    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_intent TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS conversation_tone TEXT DEFAULT 'balanced'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_offer_message_count INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS age_gate_count INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sexual_profile TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS buyer_profile TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS fantasies_detected TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS objections_detected TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS trust_level INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_confusion TEXT DEFAULT ''")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id ON messages (chat_id, id DESC)")
    cur.execute("DELETE FROM messages WHERE content IS NULL OR BTRIM(content) = ''")

    conn.commit()
    cur.close()
    conn.close()


def row_to_dict(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    columns = [
        "chat_id", "username", "first_name", "stage", "client_type",
        "interest_score", "age_confirmed", "message_count", "last_message",
        "summary", "created_at", "updated_at", "preferred_language", "last_intent",
        "conversation_tone", "last_offer_message_count", "age_gate_count",
        "sexual_profile", "buyer_profile", "fantasies_detected",
        "objections_detected", "trust_level", "last_confusion",
    ]
    return dict(zip(columns, row))


def get_or_create_user(chat_id: str, username: str = "", first_name: str = "") -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    now = _now()
    cur.execute("""
    INSERT INTO users (
        chat_id, username, first_name, stage, client_type, interest_score,
        age_confirmed, message_count, last_message, summary, created_at,
        updated_at, preferred_language, last_intent, conversation_tone
    ) VALUES (%s, %s, %s, 'new', 'cold', 0, 0, 0, '', '', %s, %s, '', '', 'balanced')
    ON CONFLICT (chat_id) DO NOTHING
    """, (chat_id, username, first_name, now, now))
    conn.commit()
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    user = row_to_dict(cur.fetchone())
    cur.close()
    conn.close()
    return user or {}


def update_user(
    chat_id: str,
    stage: Optional[str] = None,
    client_type: Optional[str] = None,
    interest_score: Optional[int] = None,
    age_confirmed: Optional[int] = None,
    last_message: Optional[str] = None,
    summary: Optional[str] = None,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    preferred_language: Optional[str] = None,
    last_intent: Optional[str] = None,
    conversation_tone: Optional[str] = None,
    last_offer_message_count: Optional[int] = None,
    age_gate_count: Optional[int] = None,
    sexual_profile: Optional[str] = None,
    buyer_profile: Optional[str] = None,
    fantasies_detected: Optional[str] = None,
    objections_detected: Optional[str] = None,
    trust_level: Optional[int] = None,
    last_confusion: Optional[str] = None,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE chat_id = %s FOR UPDATE", (chat_id,))
    user = row_to_dict(cur.fetchone())
    if not user:
        cur.close(); conn.close(); return

    cur.execute("""
    UPDATE users SET
        username=%s, first_name=%s, stage=%s, client_type=%s,
        interest_score=%s, age_confirmed=%s, message_count=%s,
        last_message=%s, summary=%s, updated_at=%s,
        preferred_language=%s, last_intent=%s, conversation_tone=%s,
        last_offer_message_count=%s, age_gate_count=%s,
        sexual_profile=%s, buyer_profile=%s, fantasies_detected=%s,
        objections_detected=%s, trust_level=%s, last_confusion=%s
    WHERE chat_id=%s
    """, (
        username if username is not None else user["username"],
        first_name if first_name is not None else user["first_name"],
        stage if stage is not None else user["stage"],
        client_type if client_type is not None else user["client_type"],
        int(interest_score) if interest_score is not None else int(user["interest_score"]),
        int(age_confirmed) if age_confirmed is not None else int(user["age_confirmed"]),
        int(user["message_count"]) + 1,
        last_message if last_message is not None else user["last_message"],
        summary if summary is not None else user["summary"],
        _now(),
        preferred_language if preferred_language is not None else user.get("preferred_language", ""),
        last_intent if last_intent is not None else user.get("last_intent", ""),
        conversation_tone if conversation_tone is not None else user.get("conversation_tone", "balanced"),
        int(last_offer_message_count) if last_offer_message_count is not None else int(user.get("last_offer_message_count") or 0),
        int(age_gate_count) if age_gate_count is not None else int(user.get("age_gate_count") or 0),
        sexual_profile if sexual_profile is not None else user.get("sexual_profile", ""),
        buyer_profile if buyer_profile is not None else user.get("buyer_profile", ""),
        fantasies_detected if fantasies_detected is not None else user.get("fantasies_detected", ""),
        objections_detected if objections_detected is not None else user.get("objections_detected", ""),
        int(trust_level) if trust_level is not None else int(user.get("trust_level") or 0),
        last_confusion if last_confusion is not None else user.get("last_confusion", ""),
        chat_id,
    ))
    conn.commit()
    cur.close()
    conn.close()


def save_message(chat_id: str, role: str, content: str) -> bool:
    content = str(content or "").strip()
    if not content:
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (chat_id, role, content, created_at) VALUES (%s,%s,%s,%s)",
                (chat_id, role, content, _now()))
    conn.commit()
    cur.close(); conn.close()
    return True


def get_recent_messages(chat_id: str, limit: int = 20) -> List[Dict[str, str]]:
    limit = max(1, min(int(limit), 50))
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
    SELECT role, content FROM messages
    WHERE chat_id=%s AND content IS NOT NULL AND BTRIM(content) <> ''
    ORDER BY id DESC LIMIT %s
    """, (chat_id, limit))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"role": role, "content": content} for role, content in reversed(rows)]
