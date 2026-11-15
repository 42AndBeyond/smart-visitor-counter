
import hashlib
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DB = BASE_DIR / "backend" / "visitors_default.db"
TARGET_DB = BASE_DIR / "backend" / "smart_visitor_counter.db"

SUPERMARKET_ID = 1
EXPECTED_EVENTS = 2835
MIGRATION_KEY = "visitors_default_to_supermarket_1_v1"


def main():
    if not SOURCE_DB.exists() or not TARGET_DB.exists():
        raise FileNotFoundError("Source or target database is missing.")

    source_hash = hashlib.sha256(SOURCE_DB.read_bytes()).hexdigest()

    # Read the original database without modifying it.
    source = sqlite3.connect(f"file:{SOURCE_DB.as_posix()}?mode=ro", uri=True)
    try:
        columns = {
            row[1] for row in source.execute("PRAGMA table_info(events)")
        }
        required = {"id", "type", "zone", "device", "time"}
        if not required.issubset(columns):
            raise RuntimeError("Unexpected source events table structure.")

        events = source.execute(
            "SELECT id, type, zone, device, time FROM events ORDER BY id"
        ).fetchall()
    finally:
        source.close()

    if len(events) != EXPECTED_EVENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_EVENTS} source events, found {len(events)}. "
            "No migration was performed."
        )

    timestamps = [row[4] for row in events]
    if not all(timestamps):
        raise RuntimeError("One or more events have a missing timestamp.")

    started_at = min(timestamps)
    ended_at = max(timestamps)

    target = sqlite3.connect(TARGET_DB, timeout=15)
    target.execute("PRAGMA foreign_keys = ON")

    try:
        target.execute("BEGIN IMMEDIATE")

        target.execute("""
            CREATE TABLE IF NOT EXISTS legacy_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_key TEXT NOT NULL UNIQUE,
                source_sha256 TEXT NOT NULL,
                imported_count INTEGER NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        previous = target.execute(
            "SELECT source_sha256, imported_count "
            "FROM legacy_migrations WHERE migration_key = ?",
            (MIGRATION_KEY,)
        ).fetchone()

        if previous:
            if previous[0] != source_hash or previous[1] != EXPECTED_EVENTS:
                raise RuntimeError(
                    "A migration marker exists, but its source details differ. "
                    "Stop and inspect the database."
                )
            target.rollback()
            print("Migration was already completed. No records were changed.")
            return

        owner = target.execute(
            "SELECT id FROM supermarkets WHERE id = ?",
            (SUPERMARKET_ID,)
        ).fetchone()

        if not owner:
            raise RuntimeError("The destination supermarket does not exist.")

        event_count = target.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        run_count = target.execute(
            "SELECT COUNT(*) FROM simulation_runs"
        ).fetchone()[0]

        if event_count != 0 or run_count != 0:
            raise RuntimeError(
                "The central database is no longer empty. "
                "Migration cancelled to protect existing data."
            )

        cursor = target.execute("""
            INSERT INTO simulation_runs
                (supermarket_id, started_at, ended_at, status)
            VALUES (?, ?, ?, 'stopped')
        """, (SUPERMARKET_ID, started_at, ended_at))

        run_id = cursor.lastrowid

        target.executemany("""
            INSERT INTO events
                (id, supermarket_id, simulation_run_id,
                 type, zone, device, time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (event_id, SUPERMARKET_ID, run_id,
             event_type, zone, device, event_time)
            for event_id, event_type, zone, device, event_time in events
        ])

        target.execute("""
            INSERT INTO legacy_migrations
                (migration_key, source_sha256, imported_count)
            VALUES (?, ?, ?)
        """, (MIGRATION_KEY, source_hash, len(events)))

        imported = target.execute(
            "SELECT COUNT(*) FROM events WHERE supermarket_id = ?",
            (SUPERMARKET_ID,)
        ).fetchone()[0]

        if imported != EXPECTED_EVENTS:
            raise RuntimeError(
                f"Verification failed: expected {EXPECTED_EVENTS}, got {imported}."
            )

        target.commit()

        print("MIGRATION SUCCESSFUL")
        print("Destination supermarket ID:", SUPERMARKET_ID)
        print("Historical simulation run ID:", run_id)
        print("Events imported:", imported)
        print("First event:", started_at)
        print("Last event:", ended_at)
        print("Original database: unchanged")

    except Exception:
        target.rollback()
        raise
    finally:
        target.close()


if __name__ == "__main__":
    main()
