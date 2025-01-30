import time
import json
import random
import sys

def send_event(event_type, data, event_id):
    """Sends an event to stdout in the expected format."""
    event = f"{event_type},{json.dumps(data)},{event_id}"
    sys.stdout.write(event + "\n")
    sys.stdout.flush()

def main():
    """Simulates MacKeyServer events."""
    event_id = 0

    # Simulate initial application
    send_event("APPLICATION", {"name": "TestApp"}, event_id)
    event_id += 1

    # Simulate initial window info
    send_event("WINDOW_INFO", {"kind": "ACTIVE", "ownerName": "TestApp", "windowName": "Test Window", "windowNumber": 1, "windowLayer": 0, "boundsX": 10, "boundsY": 20, "boundsWidth": 800, "boundsHeight": 600}, event_id)
    event_id += 1
    send_event("WINDOW_INFO", {"kind": "ALL", "data": [{"ownerName": "TestApp", "windowName": "Test Window", "windowNumber": 1, "windowLayer": 0, "boundsX": 10, "boundsY": 20, "boundsWidth": 800, "boundsHeight": 600}]}, event_id)
    event_id += 1

    while True:
        # Simulate keyboard events
        send_event("KEYBOARD", {"event": {"key": "A", "action": "DOWN"}, "type": "KEYBOARD"}, event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("KEYBOARD", {"event": {"key": "A", "action": "UP"}, "type": "KEYBOARD"}, event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate modifier key
        send_event("MODIFIER", {"event": {"modifier": "SHIFT", "state": "DOWN"}, "type": "MODIFIER"}, event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("KEYBOARD", {"event": {"key": "B", "action": "DOWN"}, "type": "KEYBOARD"}, event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("KEYBOARD", {"event": {"key": "B", "action": "UP"}, "type": "KEYBOARD"}, event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("MODIFIER", {"event": {"modifier": "SHIFT", "state": "UP"}, "type": "MODIFIER"}, event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate mouse click
        send_event("MOUSE", {"event": {"button": "left", "action": "DOWN"}, "type": "MOUSE"}, event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("MOUSE", {"event": {"button": "left", "action": "UP"}, "type": "MOUSE"}, event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate scroll event
        send_event("MOUSE", {"event": {"delta": 1}, "type": "SCROLL"}, event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate mouse move
        send_event("MOUSE", {"event": {}, "type": "MOVE", "x": random.randint(0, 500), "y": random.randint(0, 500)}, event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate application change (every 5 seconds)
        if event_id % 50 == 0:
            send_event("APPLICATION", {"name": "AnotherApp"}, event_id)
            event_id += 1
            time.sleep(0.1)
            send_event("WINDOW_INFO", {"kind": "ACTIVE", "ownerName": "AnotherApp", "windowName": "Another Window", "windowNumber": 2, "windowLayer": 0, "boundsX": 50, "boundsY": 100, "boundsWidth": 600, "boundsHeight": 400}, event_id)
            event_id += 1
            time.sleep(0.1)
            send_event("WINDOW_INFO", {"kind": "ALL", "data": [
                {"ownerName": "TestApp", "windowName": "Test Window", "windowNumber": 1, "windowLayer": 0, "boundsX": 10, "boundsY": 20, "boundsWidth": 800, "boundsHeight": 600},
                {"ownerName": "AnotherApp", "windowName": "Another Window", "windowNumber": 2, "windowLayer": 0, "boundsX": 50, "boundsY": 100, "boundsWidth": 600, "boundsHeight": 400}
            ]}, event_id)
            event_id += 1

if __name__ == "__main__":
    main()