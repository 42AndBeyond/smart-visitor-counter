import sqlite3
import threading
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

DB_PATH = Path(__file__).parent / "visitors.db"
ZONES = ["grocery", "snacks", "freezer"]
EVENT_TYPES = ["ENTRY", "EXIT", "ZONE_ENTER", "ZONE_LEAVE"]
lock = threading.Lock()


def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            zone TEXT NOT NULL,
            device TEXT NOT NULL,
            time TEXT NOT NULL
        )"""
    )
    db.commit()
    db.close()


def pick_day(day):
    if day is None:
        return date.today().isoformat()
    try:
        return date.fromisoformat(day).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="day must look like 2026-10-04")


def count(db, event_type, day, zone=None):
    sql = "SELECT COUNT(*) FROM events WHERE type = ? AND substr(time, 1, 10) = ?"
    params = [event_type, day]
    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)
    return db.execute(sql, params).fetchone()[0]


init_db()


class Event(BaseModel):
    type: str
    zone: str
    device: str
    time: str


@app.get("/")
def home():
    return {"message": "Smart Visitor Counter backend is running"}


@app.post("/event")
def receive_event(event: Event):
    if event.type not in EVENT_TYPES:
        raise HTTPException(status_code=400, detail="Unknown event type")
    if event.type in ("ZONE_ENTER", "ZONE_LEAVE") and event.zone not in ZONES:
        raise HTTPException(status_code=400, detail="Unknown zone")
    day = pick_day(event.time[:10])

    with lock:
        db = get_db()
        try:
            if event.type == "EXIT":
                inside = count(db, "ENTRY", day) - count(db, "EXIT", day)
                if inside <= 0:
                    raise HTTPException(status_code=400, detail="EXIT rejected: nobody is inside")
            elif event.type == "ZONE_LEAVE":
                in_zone = count(db, "ZONE_ENTER", day, event.zone) - count(db, "ZONE_LEAVE", day, event.zone)
                if in_zone <= 0:
                    raise HTTPException(status_code=400, detail="ZONE_LEAVE rejected: nobody in this zone")

            db.execute(
                "INSERT INTO events (type, zone, device, time) VALUES (?, ?, ?, ?)",
                (event.type, event.zone, event.device, event.time),
            )
            db.commit()
        finally:
            db.close()

    return {"status": "ok"}


@app.get("/stats")
def get_stats(day: str | None = None):
    day = pick_day(day)
    db = get_db()
    try:
        entered = count(db, "ENTRY", day)
        exited = count(db, "EXIT", day)
        zones = {}
        for z in ZONES:
            visits = count(db, "ZONE_ENTER", day, z)
            zones[z] = {"visits": visits, "inside": visits - count(db, "ZONE_LEAVE", day, z)}
    finally:
        db.close()
    return {
        "day": day,
        "entered": entered,
        "exited": exited,
        "inside": entered - exited,
        "zones": zones,
    }


@app.get("/events")
def latest_events(limit: int = 20, day: str | None = None):
    day = pick_day(day)
    limit = max(1, min(limit, 200))
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, type, zone, device, time FROM events "
            "WHERE substr(time, 1, 10) = ? ORDER BY id DESC LIMIT ?",
            (day, limit),
        ).fetchall()
    finally:
        db.close()
    return [
        {"id": r[0], "type": r[1], "zone": r[2], "device": r[3], "time": r[4]}
        for r in rows
    ]


@app.get("/hourly")
def hourly_flow(day: str | None = None):
    day = pick_day(day)
    db = get_db()
    try:
        rows = db.execute(
            "SELECT substr(time, 12, 2) AS hour, COUNT(*) FROM events "
            "WHERE type = 'ENTRY' AND substr(time, 1, 10) = ? GROUP BY hour",
            (day,),
        ).fetchall()
    finally:
        db.close()
    counts = {int(r[0]): r[1] for r in rows if r[0] and r[0].isdigit()}
    hours = [{"hour": h, "visitors": counts.get(h, 0)} for h in range(24)]
    peak = max(hours, key=lambda item: item["visitors"])
    return {
        "day": day,
        "hours": hours,
        "peak_hour": peak["hour"] if peak["visitors"] > 0 else None,
    }


DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")