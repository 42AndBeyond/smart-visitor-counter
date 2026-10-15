
import argparse
import random
import time
from datetime import datetime
from urllib.parse import urlencode

import requests


ZONES = ["grocery", "snacks", "freezer"]
BASE_URL = "http://127.0.0.1:8000"

# Keep track of simulated visitors and their current zones.
def run_simulation(session_id: str):
    params = urlencode({"session_id": session_id})
    event_url = f"{BASE_URL}/event?{params}"

    print(f"Starting customer simulator for session: {session_id}", flush=True)
    print(f"Sending events to: {event_url}", flush=True)

    active_visitors = {}
    visitor_number = 0

    with requests.Session() as client:
        while True:
            try:
                action = random.choice(["spawn", "move", "exit"])

                # Spawn a visitor if needed.
                if action == "spawn" or not active_visitors:
                    visitor_number += 1
                    device_id = f"visitor_{session_id}_{visitor_number}"

                    payload = {
                        "type": "ENTRY",
                        "zone": "entrance",
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        event_url, json=payload, timeout=5
                    )

                    if response.ok:
                        active_visitors[device_id] = {"zone": None}
                        print(
                            f"ENTRY accepted: {device_id}",
                            flush=True,
                        )
                    else:
                        print(
                            f"ENTRY rejected ({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

                elif action == "move" and active_visitors:
                    device_id = random.choice(
                        list(active_visitors.keys())
                    )
                    old_zone = active_visitors[device_id]["zone"]
                    new_zone = random.choice(ZONES)

                    if old_zone == new_zone:
                        time.sleep(1)
                        continue

                    # Leave the previous zone first.
                    if old_zone is not None:
                        leave_payload = {
                            "type": "ZONE_LEAVE",
                            "zone": old_zone,
                            "device": device_id,
                            "time": datetime.now().isoformat(),
                        }

                        response = client.post(
                            event_url,
                            json=leave_payload,
                            timeout=5,
                        )

                        if not response.ok:
                            print(
                                f"ZONE_LEAVE rejected "
                                f"({response.status_code}): "
                                f"{response.text}",
                                flush=True,
                            )
                            time.sleep(1)
                            continue

                    # Enter the new zone.
                    enter_payload = {
                        "type": "ZONE_ENTER",
                        "zone": new_zone,
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        event_url,
                        json=enter_payload,
                        timeout=5,
                    )

                    if response.ok:
                        active_visitors[device_id]["zone"] = new_zone
                        print(
                            f"ZONE_ENTER accepted: "
                            f"{device_id} -> {new_zone}",
                            flush=True,
                        )
                    else:
                        print(
                            f"ZONE_ENTER rejected "
                            f"({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

                elif action == "exit" and active_visitors:
                    device_id = random.choice(
                        list(active_visitors.keys())
                    )
                    old_zone = active_visitors[device_id]["zone"]

                    # Leave the current zone before exiting the store.
                    if old_zone is not None:
                        leave_payload = {
                            "type": "ZONE_LEAVE",
                            "zone": old_zone,
                            "device": device_id,
                            "time": datetime.now().isoformat(),
                        }

                        response = client.post(
                            event_url,
                            json=leave_payload,
                            timeout=5,
                        )

                        if not response.ok:
                            print(
                                f"ZONE_LEAVE rejected "
                                f"({response.status_code}): "
                                f"{response.text}",
                                flush=True,
                            )
                            time.sleep(1)
                            continue

                    exit_payload = {
                        "type": "EXIT",
                        "zone": "exit",
                        "device": device_id,
                        "time": datetime.now().isoformat(),
                    }

                    response = client.post(
                        event_url,
                        json=exit_payload,
                        timeout=5,
                    )

                    if response.ok:
                        del active_visitors[device_id]
                        print(
                            f"EXIT accepted: {device_id}",
                            flush=True,
                        )
                    else:
                        print(
                            f"EXIT rejected ({response.status_code}): "
                            f"{response.text}",
                            flush=True,
                        )

            except requests.RequestException as error:
                print(
                    f"Cannot contact backend: {error}",
                    flush=True,
                )

            except Exception as error:
                print(
                    f"Simulator error: {error}",
                    flush=True,
                )

            time.sleep(random.uniform(0.8, 1.5))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smart Store Customer Simulator"
    )

    parser.add_argument(
        "--session",
        type=str,
        default="default",
        help="Session ID for isolated telemetry data",
    )

    args = parser.parse_args()
    run_simulation(args.session)
