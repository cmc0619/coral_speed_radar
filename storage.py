"""Durable SQLite event journal."""
import sqlite3
from datetime import datetime, timezone


def initialize(db_path):
    with sqlite3.connect(db_path, timeout=10) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY,
            detected_at TEXT NOT NULL, track_id INTEGER NOT NULL,
            plate TEXT, plate_votes INTEGER NOT NULL,
            vehicle_type TEXT NOT NULL, speed_mph REAL NOT NULL,
            direction TEXT NOT NULL, elapsed_seconds REAL NOT NULL,
            post_status TEXT NOT NULL, post_error TEXT)""")


def save_event(db_path, event, status):
    with sqlite3.connect(db_path, timeout=10) as db:
        cursor = db.execute("""INSERT INTO events
            (detected_at,track_id,plate,plate_votes,vehicle_type,speed_mph,
             direction,elapsed_seconds,post_status)
             VALUES(?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(), event["track_id"],
             event["plate"], event["plate_votes"], event["vehicle_type"],
             event["speed_mph"], event["direction"],
             event["elapsed_seconds"], status))
        return cursor.lastrowid


def update_status(db_path, event_id, status, error=None):
    with sqlite3.connect(db_path, timeout=10) as db:
        db.execute("UPDATE events SET post_status=?,post_error=? WHERE id=?",
                   (status, error, event_id))


def recent(db_path):
    with sqlite3.connect(db_path, timeout=10) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT 50")]
