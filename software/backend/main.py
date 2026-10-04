from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

ZONES = ["grocery", "snacks", "freezer"]

stats = {
    "entered": 0,
    "exited": 0,
    "zones": {z: {"visits": 0, "inside": 0} for z in ZONES},
}


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
    inside_now = stats["entered"] - stats["exited"]

    if event.type == "ENTRY":
        stats["entered"] += 1

    elif event.type == "EXIT":
        if inside_now <= 0:
            raise HTTPException(status_code=400, detail="EXIT rejected: nobody is inside")
        stats["exited"] += 1

    elif event.type == "ZONE_ENTER":
        if event.zone not in ZONES:
            raise HTTPException(status_code=400, detail="Unknown zone")
        stats["zones"][event.zone]["visits"] += 1
        stats["zones"][event.zone]["inside"] += 1

    elif event.type == "ZONE_LEAVE":
        if event.zone not in ZONES:
            raise HTTPException(status_code=400, detail="Unknown zone")
        if stats["zones"][event.zone]["inside"] <= 0:
            raise HTTPException(status_code=400, detail="ZONE_LEAVE rejected: nobody in this zone")
        stats["zones"][event.zone]["inside"] -= 1

    else:
        raise HTTPException(status_code=400, detail="Unknown event type")

    return {"status": "ok"}


@app.get("/stats")
def get_stats():
    return {
        "entered": stats["entered"],
        "exited": stats["exited"],
        "inside": stats["entered"] - stats["exited"],
        "zones": stats["zones"],
    }