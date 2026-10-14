from __future__ import annotations
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path
import subprocess
import sys
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

ZONES = ["grocery", "snacks", "freezer"]
EVENT_TYPES = ["ENTRY", "EXIT", "ZONE_ENTER", "ZONE_LEAVE"]
lock = threading.Lock()

# Dictionary to keep track of simulator processes per session: {session_id: subprocess.Popen}
simulator_processes = {}


def get_db(session_id: str = "default"):
    safe_session_id = "".join(c for c in session_id if c.isalnum() or c in ("_", "-"))
    if not safe_session_id:
        safe_session_id = "default"
    
    db_path = Path(__file__).parent / f"visitors_{safe_session_id}.db"
    db = sqlite3.connect(db_path)
    
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
    return db


def pick_day(day):
    if day is None:
        return date.today().isoformat()
    try:
        return date.fromisoformat(day).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="day must look like 2026-10-04"
        )


def count(db, event_type, day, zone=None):
    sql = "SELECT COUNT(*) FROM events WHERE type = ? AND substr(time, 1, 10) = ?"
    params = [event_type, day]

    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)

    return db.execute(sql, params).fetchone()[0]


def average_dwell(db, enter_type, leave_type, day, zone=None):
    sql = """
        SELECT type, time
        FROM events
        WHERE type IN (?, ?)
          AND substr(time, 1, 10) = ?
    """

    params = [enter_type, leave_type, day]

    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)

    sql += " ORDER BY time, id"

    rows = db.execute(sql, params).fetchall()

    inside = 0
    total_person_seconds = 0.0
    completed = 0
    previous_time = None

    for event_type, value in rows:
        try:
            current_time = datetime.fromisoformat(value).replace(tzinfo=None)
        except ValueError:
            continue

        if previous_time is not None:
            elapsed = max(
                0.0,
                (current_time - previous_time).total_seconds()
            )

            total_person_seconds += inside * elapsed

        if event_type == enter_type:
            inside += 1

        elif event_type == leave_type:
            if inside > 0:
                inside -= 1
                completed += 1

        previous_time = current_time

    if completed == 0:
        return None, 0

    average = total_person_seconds / completed

    return round(average, 1), completed


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
            insights.append(
                f"Longest stays: {longest}. Shoppers browse here longer."
            )

            insights.append(
                f"Shortest stays: {shortest}. Shoppers grab things quickly, "
                "so keep popular items easy to reach."
            )

    return insights


class Event(BaseModel):
    type: str
    zone: str
    device: str
    time: str


@app.get("/")
def home():
    return {"message": "Smart Visitor Counter backend is running"}


@app.post("/event")
def receive_event(event: Event, session_id: str = Query("default")):
    if event.type not in EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unknown event type"
        )

    if event.type in ("ZONE_ENTER", "ZONE_LEAVE") and event.zone not in ZONES:
        raise HTTPException(
            status_code=400,
            detail="Unknown zone"
        )

    day = pick_day(event.time[:10])

    with lock:
        db = get_db(session_id)

        try:
            if event.type == "EXIT":
                inside = count(db, "ENTRY", day) - count(db, "EXIT", day)

                if inside <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="EXIT rejected: nobody is inside"
                    )

            elif event.type == "ZONE_LEAVE":
                in_zone = (
                    count(db, "ZONE_ENTER", day, event.zone)
                    - count(db, "ZONE_LEAVE", day, event.zone)
                )

                if in_zone <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="ZONE_LEAVE rejected: nobody in this zone"
                    )

            db.execute(
                "INSERT INTO events (type, zone, device, time) VALUES (?, ?, ?, ?)",
                (
                    event.type,
                    event.zone,
                    event.device,
                    event.time
                ),
            )

            db.commit()

        finally:
            db.close()

    return {"status": "ok"}


@app.get("/stats")
def get_stats(session_id: str = Query("default"), day: Optional[str] = None):
    day = pick_day(day)
    db = get_db(session_id)

    try:
        entered = count(db, "ENTRY", day)
        exited = count(db, "EXIT", day)

        zones = {}

        for z in ZONES:
            visits = count(db, "ZONE_ENTER", day, z)

            zones[z] = {
                "visits": visits,
                "inside": visits - count(
                    db,
                    "ZONE_LEAVE",
                    day,
                    z
                ),
            }

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
def latest_events(session_id: str = Query("default"), limit: int = 20, day: Optional[str] = None):
    day = pick_day(day)
    limit = max(1, min(limit, 200))
    db = get_db(session_id)

    try:
        rows = db.execute(
            "SELECT id, type, zone, device, time FROM events "
            "WHERE substr(time, 1, 10) = ? "
            "ORDER BY id DESC LIMIT ?",
            (day, limit),
        ).fetchall()

    finally:
        db.close()

    return [
        {
            "id": r[0],
            "type": r[1],
            "zone": r[2],
            "device": r[3],
            "time": r[4],
        }
        for r in rows
    ]


@app.get("/hourly")
def hourly_flow(session_id: str = Query("default"), day: Optional[str] = None):
    day = pick_day(day)
    db = get_db(session_id)

    try:
        rows = db.execute(
            "SELECT substr(time, 12, 2) AS hour, COUNT(*) "
            "FROM events "
            "WHERE type = 'ENTRY' "
            "AND substr(time, 1, 10) = ? "
            "GROUP BY hour",
            (day,),
        ).fetchall()

    finally:
        db.close()

    counts = {
        int(r[0]): r[1]
        for r in rows
        if r[0] and r[0].isdigit()
    }

    hours = [
        {
            "hour": h,
            "visitors": counts.get(h, 0)
        }
        for h in range(24)
    ]

    peak = max(
        hours,
        key=lambda item: item["visitors"]
    )

    return {
        "day": day,
        "hours": hours,
        "peak_hour": (
            peak["hour"]
            if peak["visitors"] > 0
            else None
        ),
    }


@app.get("/analytics")
def analytics(session_id: str = Query("default"), day: Optional[str] = None):
    day = pick_day(day)
    db = get_db(session_id)

    try:
        store_avg, store_pairs = average_dwell(
            db,
            "ENTRY",
            "EXIT",
            day
        )

        zones = {}

        for z in ZONES:
            avg, pairs = average_dwell(
                db,
                "ZONE_ENTER",
                "ZONE_LEAVE",
                day,
                z
            )

            zones[z] = {
                "visits": count(
                    db,
                    "ZONE_ENTER",
                    day,
                    z
                ),
                "avg_dwell_seconds": avg,
                "completed_stays": pairs,
            }

    finally:
        db.close()

    total_visits = sum(
        z["visits"]
        for z in zones.values()
    )

    for z in zones.values():
        z["share_percent"] = (
            round(
                z["visits"] * 100 / total_visits
            )
            if total_visits
            else 0
        )

    return {
        "day": day,
        "store": {
            "avg_dwell_seconds": store_avg,
            "completed_visits": store_pairs,
        },
        "zones": zones,
        "insights": build_insights(
            zones,
            total_visits
        ),
    }


@app.post("/api/simulator/start")
@app.post("/api/simulator/start/")
def start_simulator(session_id: str = Query("default")):
    global simulator_processes
    if session_id in simulator_processes and simulator_processes[session_id].poll() is None:
        return {"status": "Simulator is already running"}
    
    sim_path = Path(__file__).parent / "simulator.py"
    if not sim_path.exists():
        raise HTTPException(status_code=404, detail="simulator.py not found")
        
    proc = subprocess.Popen(
        [sys.executable, str(sim_path), "--session", session_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    simulator_processes[session_id] = proc
    return {"status": "started", "session_id": session_id}


@app.post("/api/simulator/stop")
@app.post("/api/simulator/stop/")
def stop_simulator(session_id: str = Query("default")):
    global simulator_processes
    if session_id in simulator_processes and simulator_processes[session_id].poll() is None:
        simulator_processes[session_id].terminate()
        del simulator_processes[session_id]
        return {"status": "stopped"}
    return {"status": "Simulator is not running"}


DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"

app.mount(
    "/dashboard",
    StaticFiles(
        directory=DASHBOARD_DIR,
        html=True
    ),
    name="dashboard"
)