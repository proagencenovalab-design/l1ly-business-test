import os
import psycopg2
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant. Ajoute-le dans Railway Variables.")
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
        client_type TEXT DEFAULT 'unknown',
        interest_score INTEGER DEFAULT 0,
        age_confirmed INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0,
        last_message TEXT,
        summary TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        chat_id TEXT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT
    )
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

    cur.execute("SELECT * FROM users WHERE chat_id = %s", (str(chat_id),))
    row = cur.fetchone()

    now = datetime.utcnow().isoformat()

    if row is None:
        cur.execute("""
        INSERT INTO users (
            chat_id, username, first_name, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s)
        """, (str(chat_id), username, first_name, now, now))

        conn.commit()

        cur.execute("SELECT * FROM users WHERE chat_id = %s", (str(chat_id),))
        row = cur.fetchone()

    cur.close()
    conn.close()
    return row_to_dict(row)


def update_user(chat_id, **kwargs):
    if not kwargs:
        return

    conn = get_conn()
    cur = conn.cursor()

    kwargs["updated_at"] = datetime.utcnow().isoformat()

    fields = ", ".join([f"{key} = %s" for key in kwargs.keys()])
    values = list(kwargs.values())
    values.append(str(chat_id))

    cur.execute(f"""
    UPDATE users
    SET {fields}
    WHERE chat_id = %s
    """, values)

    conn.commit()
    cur.close()
    conn.close()


def save_message(chat_id, role, content):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO messages (chat_id, role, content, created_at)
    VALUES (%s, %s, %s, %s)
    """, (
        str(chat_id),
        role,
        content,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_messages(chat_id, limit=20):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT role, content
    FROM messages
    WHERE chat_id = %s
    ORDER BY id DESC
    LIMIT %s
    """, (
        str(chat_id),
        limit
    ))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {"role": row[0], "content": row[1]}
        for row in rows[::-1]
    ]
