"""
Database helper for CareAtZero.

Responsible for creating the local SQLite cache and giving the rest of
the app a single place to open a connection. Keeping this separate from
the Streamlit UI and the connectors means the schema can change without
touching search/scoring logic.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "careatzero.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the local cache, creating it if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False) -> None:
    """
    Create all tables from schema.sql.

    reset=True drops the existing file first — useful in dev when the
    schema changes, never call this from the live app.
    """
    if reset and DB_PATH.exists():
        DB_PATH.unlink()

    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Initialized database at {DB_PATH}")
