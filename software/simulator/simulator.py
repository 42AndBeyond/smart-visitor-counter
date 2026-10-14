import argparse
import random
import time
from datetime import datetime
import requests

# Define zones and possible event types matching backend configuration
ZONES = ["grocery", "snacks", "freezer"]

def run_simulation(session_id: str):
    base_url = f"http://localhost:8000/event?session_id={session_id}"
    print(f"Starting customer simulator for session: {session_id}")

    # Track active simulated visitors to manage realistic exits and zone transitions
    active_visitors = {}

    while True:
        try:
            # Decide whether to spawn a new visitor, move an existing one, or have someone leave
            action_choice = random.choice(["spawn", "move", "exit"])

            current_time = datetime.now().isoformat()

            if action_choice == "spawn" or not active_visitors:
                # Spawn a new visitor entering the store
                device_id = f"dev_{random.randint(1000, 9999)}"
                if device_id not in active_visitors:
                    active_visitors[device_id] = {"zone": None}
                    payload = {
                        "type": "ENTRY",
                        "zone": "entrance",
                        "device": device_id,
                        "time": current_time
                    }
                    requests.post(base_url, json=payload, timeout=2)

            elif action_choice == "move" and active_visitors:
                # Pick a random active visitor to move into a zone
                device_id = random.choice(list(active_visitors.keys()))
                zone = random.choice(ZONES)
                
                # If they were already in a zone, leave it first
                old_zone = active_visitors[device_id]["zone"]
                if old_zone and old_zone != zone:
                    leave_payload = {
                        "type": "ZONE_LEAVE",
                        "zone": old_zone,
                        "device": device_id,
                        "time": current_time
                    }
                    requests.post(base_url, json=leave_payload, timeout=2)

                # Enter new zone
                active_visitors[device_id]["zone"] = zone
                enter_payload = {
                    "type": "ZONE_ENTER",
                    "zone": zone,
                    "device": device_id,
                    "time": current_time
                }
                requests.post(base_url, json=enter_payload, timeout=2)

            elif action_choice == "exit" and active_visitors:
                # Remove and exit a random visitor
                device_id = random.choice(list(active_visitors.keys()))
                old_zone = active_visitors[device_id]["zone"]
                
                if old_zone:
                    leave_payload = {
                        "type": "ZONE_LEAVE",
                        "zone": old_zone,
                        "device": device_id,
                        "time": current_time
                    }
                    requests.post(base_url, json=leave_payload, timeout=2)

                exit_payload = {
                    "type": "EXIT",
                    "zone": "exit",
                    "device": device_id,
                    "time": current_time
                }
                requests.post(base_url, json=exit_payload, timeout=2)
                del active_visitors[device_id]

        except Exception as e:
            print(f"Simulator error: {e}")

        # Control frequency of simulated actions
        time.sleep(random.uniform(0.8, 2.0))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Store Customer Simulator")
    parser.add_argument("--session", type=str, default="default", help="Session ID for isolated telemetry data")
    args = parser.parse_args()
    
    run_simulation(args.session)