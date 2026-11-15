
from __future__ import annotations

import os
import sqlite3
import threading
import subprocess
import sys

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import router as auth_router, get_current_owner


app = FastAPI(
    title="Smart Visitor Counter API",
    description="Smart Store Telemetry and Visitor Analytics",
    version="3.0.0"
)

app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


DB_PATH = Path(__file__).resolve().parent / "smart_visitor_counter.db"
SIMULATOR_PATH = (
    Path(__file__).resolve().parent.parent
    / "simulator" / "simulator.py"
)

ZONES = ["grocery", "snacks", "freezer"]
EVENT_TYPES = ["ENTRY", "EXIT", "ZONE_ENTER", "ZONE_LEAVE"]

lock = threading.RLock()
simulator_processes = {}

bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
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


def count(db, supermarket_id, event_type, day, zone=None):
    sql = """
        SELECT COUNT(*) FROM events
        WHERE supermarket_id = ?
          AND type = ?
          AND substr(time, 1, 10) = ?
    """
    params = [supermarket_id, event_type, day]

    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)

    return db.execute(sql, params).fetchone()[0]


def average_dwell(
    db, supermarket_id, enter_type, leave_type, day, zone=None
):
    sql = """
        SELECT type, time
        FROM events
        WHERE supermarket_id = ?
          AND type IN (?, ?)
          AND substr(time, 1, 10) = ?
    """

    params = [supermarket_id, enter_type, leave_type, day]

    if zone is not None:
        sql += " AND zone = ?"
        params.append(zone)

    sql += " ORDER BY time, id"

    rows = db.execute(sql, params).fetchall()

    inside = 0
    total_person_seconds = 0.0
    completed = 0
    previous_time = None

    for row in rows:
        try:
            current_time = datetime.fromisoformat(
                row["time"]
            ).replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

        if previous_time is not None:
            elapsed = max(
                0.0,
                (current_time - previous_time).total_seconds()
            )
            total_person_seconds += inside * elapsed

        if row["type"] == enter_type:
            inside += 1

        elif row["type"] == leave_type:
            if inside > 0:
                inside -= 1
                completed += 1

        previous_time = current_time

    if completed == 0:
        return None, 0

    return round(total_person_seconds / completed, 1), completed


def build_insights(zones, total_visits):
    if total_visits < 5:
        return [
            "Not enough data yet. Insights appear after a few zone visits."
        ]

    insights = []

    busiest = max(zones, key=lambda z: zones[z]["visits"])
    quietest = min(zones, key=lambda z: zones[z]["visits"])

    insights.append(
        f"Busiest zone: {busiest} "
        f"({zones[busiest]['share_percent']}% of zone visits). "
        "A good spot for high-margin or featured products."
    )

    if zones[busiest]["visits"] != zones[quietest]["visits"]:
        insights.append(
            f"Quietest zone: {quietest} "
            f"({zones[quietest]['share_percent']}%). "
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


# --------------------------------------------------
# EVENT MODEL
# --------------------------------------------------

class Event(BaseModel):
    type: str
    zone: str
    device: str
    time: str


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Smart Visitor Counter backend is running"
    }


# --------------------------------------------------
# RECEIVE EVENTS — OWNER-SCOPED
# --------------------------------------------------

@app.post("/event")
def receive_event(
    event: Event,
    owner: dict = Depends(get_current_owner)
):
    supermarket_id = owner["supermarket_id"]

    if event.type not in EVENT_TYPES:
        raise HTTPException(400, "Unknown event type")

    if (
        event.type in ("ZONE_ENTER", "ZONE_LEAVE")
        and event.zone not in ZONES
    ):
        raise HTTPException(400, "Unknown zone")

    try:
        event_day = pick_day(event.time[:10])
        datetime.fromisoformat(event.time)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid event timestamp")

    with lock:
        db = get_db()

        try:
            if event.type == "EXIT":
                inside = (
                    count(db, supermarket_id, "ENTRY", event_day)
                    - count(db, supermarket_id, "EXIT", event_day)
                )

                if inside <= 0:
                    raise HTTPException(
                        400, "EXIT rejected: nobody is inside"
                    )

            elif event.type == "ZONE_LEAVE":
                in_zone = (
                    count(
                        db, supermarket_id,
                        "ZONE_ENTER", event_day, event.zone
                    )
                    - count(
                        db, supermarket_id,
                        "ZONE_LEAVE", event_day, event.zone
                    )
                )

                if in_zone <= 0:
                    raise HTTPException(
                        400,
                        "ZONE_LEAVE rejected: nobody in this zone"
                    )

            active_run = db.execute(
                """
                SELECT id FROM simulation_runs
                WHERE supermarket_id = ? AND status = 'running'
                ORDER BY id DESC LIMIT 1
                """,
                (supermarket_id,)
            ).fetchone()

            run_id = active_run["id"] if active_run else None

            db.execute(
                """
                INSERT INTO events
                    (supermarket_id, simulation_run_id,
                     type, zone, device, time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    supermarket_id,
                    run_id,
                    event.type,
                    event.zone,
                    event.device,
                    event.time
                )
            )

            db.commit()

        finally:
            db.close()

    return {"status": "ok"}


# --------------------------------------------------
# STATISTICS — OWNER-SCOPED
# --------------------------------------------------

@app.get("/stats")
def get_stats(
    day: Optional[str] = None,
    owner: dict = Depends(get_current_owner)
):
    day = pick_day(day)
    supermarket_id = owner["supermarket_id"]

    db = get_db()

    try:
        entered = count(db, supermarket_id, "ENTRY", day)
        exited = count(db, supermarket_id, "EXIT", day)

        zones = {}

        for zone in ZONES:
            visits = count(
                db, supermarket_id, "ZONE_ENTER", day, zone
            )
            leaves = count(
                db, supermarket_id, "ZONE_LEAVE", day, zone
            )

            zones[zone] = {
                "visits": visits,
                "inside": visits - leaves
            }

    finally:
        db.close()

    return {
        "day": day,
        "entered": entered,
        "exited": exited,
        "inside": entered - exited,
        "zones": zones
    }


# --------------------------------------------------
# EVENTS — OWNER-SCOPED
# --------------------------------------------------

@app.get("/events")
def latest_events(
    limit: int = 20,
    day: Optional[str] = None,
    owner: dict = Depends(get_current_owner)
):
    day = pick_day(day)
    limit = max(1, min(limit, 200))
    supermarket_id = owner["supermarket_id"]

    db = get_db()

    try:
        rows = db.execute(
            """
            SELECT id, type, zone, device, time
            FROM events
            WHERE supermarket_id = ?
              AND substr(time, 1, 10) = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (supermarket_id, day, limit)
        ).fetchall()

    finally:
        db.close()

    return [
        {
            "id": row["id"],
            "type": row["type"],
            "zone": row["zone"],
            "device": row["device"],
            "time": row["time"]
        }
        for row in rows
    ]


# --------------------------------------------------
# HOURLY VISITOR FLOW — OWNER-SCOPED
# --------------------------------------------------

@app.get("/hourly")
def hourly_flow(
    day: Optional[str] = None,
    owner: dict = Depends(get_current_owner)
):
    day = pick_day(day)
    supermarket_id = owner["supermarket_id"]

    db = get_db()

    try:
        rows = db.execute(
            """
            SELECT substr(time, 12, 2) AS hour, COUNT(*) AS total
            FROM events
            WHERE supermarket_id = ?
              AND type = 'ENTRY'
              AND substr(time, 1, 10) = ?
            GROUP BY hour
            """,
            (supermarket_id, day)
        ).fetchall()

    finally:
        db.close()

    counts = {
        int(row["hour"]): row["total"]
        for row in rows
        if row["hour"] and row["hour"].isdigit()
    }

    hours = [
        {"hour": hour, "visitors": counts.get(hour, 0)}
        for hour in range(24)
    ]

    peak = max(hours, key=lambda item: item["visitors"])

    return {
        "day": day,
        "hours": hours,
        "peak_hour": (
            peak["hour"] if peak["visitors"] > 0 else None
        )
    }


# --------------------------------------------------
# ANALYTICS — OWNER-SCOPED
# --------------------------------------------------

@app.get("/analytics")
def analytics(
    day: Optional[str] = None,
    owner: dict = Depends(get_current_owner)
):
    day = pick_day(day)
    supermarket_id = owner["supermarket_id"]

    db = get_db()

    try:
        store_avg, store_pairs = average_dwell(
            db, supermarket_id, "ENTRY", "EXIT", day
        )

        zones = {}

        for zone in ZONES:
            avg, pairs = average_dwell(
                db, supermarket_id,
                "ZONE_ENTER", "ZONE_LEAVE", day, zone
            )

            zones[zone] = {
                "visits": count(
                    db, supermarket_id, "ZONE_ENTER", day, zone
                ),
                "avg_dwell_seconds": avg,
                "completed_stays": pairs
            }

    finally:
        db.close()

    total_visits = sum(
        zone["visits"] for zone in zones.values()
    )

    for zone in zones.values():
        zone["share_percent"] = (
            round(zone["visits"] * 100 / total_visits)
            if total_visits else 0
        )

    return {
        "day": day,
        "store": {
            "avg_dwell_seconds": store_avg,
            "completed_visits": store_pairs
        },
        "zones": zones,
        "insights": build_insights(zones, total_visits)
    }


# --------------------------------------------------
# SIMULATOR START — OWNER-SCOPED
# --------------------------------------------------

@app.post("/api/simulator/start")
@app.post("/api/simulator/start/")
def start_simulator(
    owner: dict = Depends(get_current_owner),
    credentials: Optional[HTTPAuthorizationCredentials] =
        Depends(bearer_scheme)
):
    supermarket_id = owner["supermarket_id"]

    if credentials is None:
        raise HTTPException(401, "Authentication required")

    token = credentials.credentials

    if not SIMULATOR_PATH.is_file():
        raise HTTPException(
            404, f"Simulator file not found: {SIMULATOR_PATH}"
        )

    with lock:
        existing = simulator_processes.get(supermarket_id)

        if existing and existing["process"].poll() is None:
            return {"status": "Simulator is already running"}

        db = get_db()

        try:
            cursor = db.execute(
                """
                INSERT INTO simulation_runs
                    (supermarket_id, started_at, status)
                VALUES (?, ?, 'running')
                """,
                (supermarket_id, datetime.now().isoformat())
            )
            run_id = cursor.lastrowid
            db.commit()

        finally:
            db.close()

        environment = os.environ.copy()
        environment["AAPP_ACCESS_TOKEN"] = token

        try:
            process = subprocess.Popen(
                [sys.executable, str(SIMULATOR_PATH)],
                cwd=str(SIMULATOR_PATH.parent),
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            db = get_db()
            try:
                db.execute(
                    """
                    UPDATE simulation_runs
                    SET status = 'stopped', ended_at = ?
                    WHERE id = ? AND supermarket_id = ?
                    """,
                    (datetime.now().isoformat(), run_id, supermarket_id)
                )
                db.commit()
            finally:
                db.close()
            raise HTTPException(500, "Could not start simulator")

        simulator_processes[supermarket_id] = {
            "process": process,
            "run_id": run_id
        }

    return {"status": "started"}


# --------------------------------------------------
# SIMULATOR STOP — OWNER-SCOPED
# --------------------------------------------------

@app.post("/api/simulator/stop")
@app.post("/api/simulator/stop/")
def stop_simulator(
    owner: dict = Depends(get_current_owner)
):
    supermarket_id = owner["supermarket_id"]

    with lock:
        entry = simulator_processes.get(supermarket_id)

        if not entry:
            return {"status": "Simulator is not running"}

        process = entry["process"]
        run_id = entry["run_id"]

        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        simulator_processes.pop(supermarket_id, None)

        db = get_db()

        try:
            db.execute(
                """
                UPDATE simulation_runs
                SET status = 'stopped', ended_at = ?
                WHERE id = ? AND supermarket_id = ?
                """,
                (datetime.now().isoformat(), run_id, supermarket_id)
            )
            db.commit()

        finally:
            db.close()

    return {"status": "stopped"}


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

DASHBOARD_DIR = (
    Path(__file__).resolve().parent.parent / "dashboard"
)

app.mount(
    "/dashboard",
    StaticFiles(directory=DASHBOARD_DIR, html=True),
    name="dashboard"
)
