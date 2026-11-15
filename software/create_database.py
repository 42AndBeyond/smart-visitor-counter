import sqlite3
from pathlib import Path

# Always create the database inside the backend folder.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "backend" / "smart_visitor_counter.db"

if DB_PATH.exists():
    raise SystemExit(
        f"STOP: Database already exists. Nothing was changed: {DB_PATH}"
    )

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    connection.executescript("""
    BEGIN TRANSACTION;

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_name TEXT NOT NULL,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE supermarkets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_user_id INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_user_id)
            REFERENCES users(id)
            ON DELETE RESTRICT
    );

    CREATE TABLE simulation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supermarket_id INTEGER NOT NULL,
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ended_at TEXT,
        status TEXT NOT NULL DEFAULT 'running'
            CHECK (status IN ('running', 'stopped', 'reset')),
        reset_at TEXT,
        FOREIGN KEY (supermarket_id)
            REFERENCES supermarkets(id)
            ON DELETE RESTRICT,
        UNIQUE (id, supermarket_id)
    );

    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supermarket_id INTEGER NOT NULL,
        simulation_run_id INTEGER,
        type TEXT NOT NULL,
        zone TEXT,
        device TEXT,
        time TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (supermarket_id)
            REFERENCES supermarkets(id)
            ON DELETE RESTRICT,

        FOREIGN KEY (simulation_run_id, supermarket_id)
            REFERENCES simulation_runs(id, supermarket_id)
            ON DELETE RESTRICT
    );

    CREATE TABLE auth_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    );

    CREATE INDEX idx_events_supermarket_time
        ON events(supermarket_id, time);

    CREATE INDEX idx_events_simulation_run
        ON events(simulation_run_id);

    CREATE INDEX idx_runs_supermarket
        ON simulation_runs(supermarket_id, started_at);

    CREATE INDEX idx_sessions_user
        ON auth_sessions(user_id);

    COMMIT;
    """)

    print("Database created successfully.")

except Exception:
    connection.rollback()
    raise

finally:
    connection.close()

# Reopen in read-only mode to verify the database.
verification = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)

tables = verification.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()

integrity = verification.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print("\nDatabase location:", DB_PATH)
print("\nTables created:")

for table in tables:
    print("-", table[0])

print("\nIntegrity check:", integrity)
print("Foreign keys enabled during creation.")

verification.close()