import sqlite3
import threading
from datetime import date, datetime
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


def event_times(db, event_type, day, zone=None):
    sql = "SELECT time FROM events WHERE type = ? AND substr(time, 1, 10) = ?"
    params = [event_type, day]
    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)
    sql += " ORDER BY time, id"
    times = []
    for (value,) in db.execute(sql, params).fetchall():
        try:
            times.append(datetime.fromisoformat(value).replace(tzinfo=None))
        except ValueError:
            pass
    return times


def average_dwell(starts, ends):
    pairs = min(len(starts), len(ends))
    if pairs == 0:
        return None, 0
    total = 0.0
    for i in range(pairs):
        total += max(0.0, (ends[i] - starts[i]).total_seconds())
    return round(total / pairs, 1), pairs


def build_insights(zones, total_visits):
    if total_visits < 5:
        return ["Not enough data yet. Insights appear after a few zone visits."]
    insights = []
    busiest = max(zones, key=lambda z: zones[z]["visits"])
    quietest = min(zones, key=lambda z: zones[z]["visits"])
    insights.append(
        f"Busiest zone: {busiest} ({zones[busiest]['share_percent']}% of zone visits). "
        "A good spot for high-margin or featured products."
    )
    if zones[busiest]["visits"] != zones[quietest]["visits"]:
        insights.append(
            f"Quietest zone: {quietest} ({zones[quietest]['share_percent']}%). "
            "Consider promotions or signage to bring more shoppers here."
        )
    dwell = {
        z: s["avg_dwell_seconds"]
        for z, s in zones.items()
        if s["avg_dwell_seconds"] is not None
    }
    if len(dwell) >= 2:
        longest = max(dwell, key=dwell.get)
        shortest = min(dwell, key=dwell.get)
        if dwell[longest] != dwell[shortest]:
            insights.append(f"Longest stays: {longest}. Shoppers browse here longer.")
            insights.append(
                f"Shortest stays: {shortest}. Shoppers grab things quickly, "
                "so keep popular items easy to reach."
            )
    return insights


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


@app.get("/analytics")
def analytics(day: str | None = None):
    day = pick_day(day)
    db = get_db()
    try:
        store_avg, store_pairs = average_dwell(
            event_times(db, "ENTRY", day), event_times(db, "EXIT", day)
        )
        zones = {}
        for z in ZONES:
            avg, pairs = average_dwell(
                event_times(db, "ZONE_ENTER", day, z),
                event_times(db, "ZONE_LEAVE", day, z),
            )
            zones[z] = {
                "visits": count(db, "ZONE_ENTER", day, z),
                "avg_dwell_seconds": avg,
                "completed_stays": pairs,
            }
    finally:
        db.close()

    total_visits = sum(z["visits"] for z in zones.values())
    for z in zones.values():
        z["share_percent"] = round(z["visits"] * 100 / total_visits) if total_visits else 0

    return {
        "day": day,
        "store": {"avg_dwell_seconds": store_avg, "completed_visits": store_pairs},
        "zones": zones,
        "insights": build_insights(zones, total_visits),
    }


DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")