import os
import psycopg2
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL manquant. Lie le service Postgres au service du bot dans Railway."
        )
    return psycopg2.connect(DATABASE_URL)


def init_db():
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
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id
    ON messages (chat_id, id DESC)
    """)

    conn.commit()
    cur.close()
    conn.close()


def row_to_dict(row):
    if row is None:
        return None

    columns = [
        "chat_id", "username", "first_name", "stage", "client_type",
        "interest_score", "age_confirmed", "message_count",
        "last_message", "summary", "created_at", "updated_at"
    ]
    return dict(zip(columns, row))


def get_or_create_user(chat_id, username="", first_name=""):
    conn = get_conn()
    cur = conn.cursor()
    now = _now()

    cur.execute("""
    INSERT INTO users (
        chat_id, username, first_name, stage, client_type,
        interest_score, age_confirmed, message_count,
        last_message, summary, created_at, updated_at
    )
    VALUES (%s, %s, %s, 'new', 'cold', 0, 0, 0, '', '', %s, %s)
    ON CONFLICT (chat_id) DO NOTHING
    """, (chat_id, username, first_name, now, now))

    conn.commit()
    cur.execute("SELECT * FROM users WHERE chat_id = %s", (chat_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row_to_dict(row)


def update_user(
    chat_id,
    stage=None,
    client_type=None,
    interest_score=None,
    age_confirmed=None,
    last_message=None,
    summary=None,
    username=None,
    first_name=None
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE chat_id = %s FOR UPDATE", (chat_id,))
    user = row_to_dict(cur.fetchone())

    if user is None:
        cur.close()
        conn.close()
        return

    cur.execute("""
    UPDATE users
    SET username = %s,
        first_name = %s,
        stage = %s,
        client_type = %s,
        interest_score = %s,
        age_confirmed = %s,
        message_count = %s,
        last_message = %s,
        summary = %s,
        updated_at = %s
    WHERE chat_id = %s
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
        chat_id
    ))

    conn.commit()
    cur.close()
    conn.close()


def save_message(chat_id, role, content):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO messages (chat_id, role, content, created_at)
    VALUES (%s, %s, %s, %s)
    """, (chat_id, role, content, _now()))
    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(chat_id, limit=20):
    limit = max(1, min(int(limit), 50))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT role, content
    FROM messages
    WHERE chat_id = %s
    ORDER BY id DESC
    LIMIT %s
    """, (chat_id, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
