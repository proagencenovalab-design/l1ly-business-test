import sqlite3
from datetime import datetime

DB_PATH = "lily_memory.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
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

    conn.commit()
    conn.close()


def get_or_create_user(chat_id, username="", first_name=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (str(chat_id),))
    row = cursor.fetchone()

    now = datetime.utcnow().isoformat()

    if not row:
        cursor.execute("""
        INSERT INTO users (
            chat_id, username, first_name, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """, (str(chat_id), username, first_name, now, now))
        conn.commit()

    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (str(chat_id),))
    row = cursor.fetchone()
    conn.close()

    return row_to_dict(row)


def update_user(chat_id, **kwargs):
    if not kwargs:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    kwargs["updated_at"] = datetime.utcnow().isoformat()

    fields = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values())
    values.append(str(chat_id))

    cursor.execute(f"""
    UPDATE users
    SET {fields}
    WHERE chat_id = ?
    """, values)

    conn.commit()
    conn.close()


def row_to_dict(row):
    columns = [
        "chat_id",
        "username",
        "first_name",
        "stage",
        "client_type",
        "interest_score",
        "age_confirmed",
        "message_count",
        "last_message",
        "summary",
        "created_at",
        "updated_at"
    ]

    return dict(zip(columns, row))