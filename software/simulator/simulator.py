import json
import random
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

BACKEND_URL = "http://127.0.0.1:8000/event"
ZONES = ["grocery", "snacks", "freezer"]


def make_event(event_type, zone):
    return {
        "type": event_type,
        "zone": zone,
        "device": "simulator-1",
        "time": datetime.now().isoformat(timespec="seconds"),
    }


def send(event):
    data = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        BACKEND_URL, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            print("sent", event["type"], event["zone"], "->", response.status)
    except urllib.error.HTTPError as error:
        print("REJECTED", event["type"], event["zone"], "->", error.code, error.read().decode())
    except (urllib.error.URLError, TimeoutError):
        print("Cannot reach the backend. Is uvicorn running?")


def one_shopper():
    send(make_event("ENTRY", "entrance"))
    time.sleep(1)
    for zone in random.sample(ZONES, random.randint(1, 3)):
        send(make_event("ZONE_ENTER", zone))
        time.sleep(random.uniform(1, 3))
        send(make_event("ZONE_LEAVE", zone))
        time.sleep(1)
    send(make_event("EXIT", "entrance"))


def run_store():
    print("Simulator started. Press Ctrl+C to stop.")
    while True:
        threading.Thread(target=one_shopper, daemon=True).start()
        time.sleep(random.uniform(1, 4))


run_store()