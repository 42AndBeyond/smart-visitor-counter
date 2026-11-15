
import os
import random
import time
import uuid
from datetime import datetime

import requests


ZONES = ["grocery", "snacks", "freezer"]
BASE_URL = "http://127.0.0.1:8000"
EVENT_URL = f"{BASE_URL}/event"


def run_simulation():
    token = os.getenv("AAPP_ACCESS_TOKEN")

    if not token:
        print("ERROR: Authentication token not provided.", flush=True)
        return

    run_tag = uuid.uuid4().hex[:8]

    active_visitors = {}
    visitor_number = 0

    print("Starting authenticated customer simulator.", flush=True)
    print("Events will be sent to the authenticated owner's store.", flush=True)

    with requests.Session() as client:
        client.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

        while True:
            try:
                action = random.choice(["spawn", "move", "exit"])

                # Create a new visitor.
                if action == "spawn" or not active_visitors:
                    visitor_number += 1
                    device_id = f"visitor_{run_tag}_{visitor_number}"

                    payload = {
                        "type": "ENTRY",
                        "zone": "entrance",
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        EVENT_URL, json=payload, timeout=5
                    )

                    if response.ok:
                        active_visitors[device_id] = {"zone": None}
                        print(f"ENTRY accepted: {device_id}", flush=True)
                    else:
                        print(
                            f"ENTRY rejected ({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

                # Move a visitor between zones.
                elif action == "move" and active_visitors:
                    device_id = random.choice(list(active_visitors.keys()))
                    old_zone = active_visitors[device_id]["zone"]
                    new_zone = random.choice(ZONES)

                    if old_zone == new_zone:
                        time.sleep(1)
                        continue

                    if old_zone is not None:
                        payload = {
                            "type": "ZONE_LEAVE",
                            "zone": old_zone,
                            "device": device_id,
                            "time": datetime.now().isoformat(),
                        }

                        response = client.post(
                            EVENT_URL, json=payload, timeout=5
                        )

                        if not response.ok:
                            print(
                                f"ZONE_LEAVE rejected ({response.status_code}): "
                                f"{response.text}",
                                flush=True,
                            )
                            time.sleep(1)
                            continue

                    payload = {
                        "type": "ZONE_ENTER",
                        "zone": new_zone,
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        EVENT_URL, json=payload, timeout=5
                    )

                    if response.ok:
                        active_visitors[device_id]["zone"] = new_zone
                        print(
                            f"ZONE_ENTER accepted: {device_id} -> {new_zone}",
                            flush=True,
                        )
                    else:
                        print(
                            f"ZONE_ENTER rejected ({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

                # Remove a visitor from the store.
                elif action == "exit" and active_visitors:
                    device_id = random.choice(list(active_visitors.keys()))
                    old_zone = active_visitors[device_id]["zone"]

                    if old_zone is not None:
                        payload = {
                            "type": "ZONE_LEAVE",
                            "zone": old_zone,
                            "device": device_id,
                            "time": datetime.now().isoformat(),
                        }

                        response = client.post(
                            EVENT_URL, json=payload, timeout=5
                        )

                        if not response.ok:
                            print(
                                f"ZONE_LEAVE rejected ({response.status_code}): "
                                f"{response.text}",
                                flush=True,
                            )
                            time.sleep(1)
                            continue

                    payload = {
                        "type": "EXIT",
                        "zone": "exit",
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        EVENT_URL, json=payload, timeout=5
                    )

                    if response.ok:
                        del active_visitors[device_id]
                        print(f"EXIT accepted: {device_id}", flush=True)
                    else:
                        print(
                            f"EXIT rejected ({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

            except requests.RequestException as error:
                print(f"Cannot contact backend: {error}", flush=True)

            except Exception as error:
                print(f"Simulator error: {error}", flush=True)

            time.sleep(random.uniform(0.8, 1.5))


if __name__ == "__main__":
    run_simulation()
