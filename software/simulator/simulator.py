import json
import random
import time
from datetime import datetime

ZONES = ["grocery", "snacks", "freezer"]

def make_event(event_type, zone):
    return {
        "type": event_type,
        "zone": zone,
        "device": "simulator-1",
        "time": datetime.now().isoformat(timespec="seconds"),
    }

def send(event):
    print(json.dumps(event))

def one_shopper():
    send(make_event("ENTRY", "entrance"))
    time.sleep(1)
    for zone in random.sample(ZONES, random.randint(1, 3)):
        send(make_event("ZONE_ENTER", zone))
        time.sleep(random.uniform(1, 3))
        send(make_event("ZONE_LEAVE", zone))
        time.sleep(1)
    send(make_event("EXIT", "entrance"))

import threading

def run_store():
    print("Simulator started. Press Ctrl+C to stop.")
    while True:
        threading.Thread(target=one_shopper, daemon=True).start()
        time.sleep(random.uniform(1, 4))

run_store()