# Event format

Every message from the sensor or simulator looks like this:

{
  "type": "ENTRY",
  "zone": "entrance",
  "device": "esp32-door-1",
  "time": "2026-10-03T10:15:00"
}

type: ENTRY, EXIT, ZONE_ENTER or ZONE_LEAVE
zone: entrance, grocery, snacks or freezer
device: which sensor or ESP32 sent it
time: when it happened