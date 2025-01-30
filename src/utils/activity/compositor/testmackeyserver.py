import time
import json
import random
import sys

def send_event(event_type, data, event_id):
    """Sends an event to stdout in the expected format."""
    if event_type in ["CHARACTER", "MODIFIER", "MOUSE", "SPECIAL_KEY"]:
        event = f"{event_type},{data},{event_id}"
    else:
        event = f"{event_type},{json.dumps(data)},{event_id}"
    sys.stdout.write(event + "\n")
    sys.stdout.flush()

def main():
    """Simulates MacKeyServer events, including special keys and more varied scenarios."""
    event_id = 0
    event_threshold = 25

    # Modifier keys mapping (add more as needed)
    modifier_map = {
        "56": "alt",    # VK_LALT
        "58": "cmd",    # VK_LCOMMAND
        "55": "ctrl",   # VK_LCTRL
        "63": "fn",     # VK_FN
        "54": "cmd",    # VK_RCOMMAND
        "60": "shift",  # VK_RSHIFT
        "59": "ctrl",   # VK_RCTRL
        "57": "alt",    # VK_RALT
        "62": "ctrl",    # VK_FN_CTRL
        "56": "shift"   # VK_LSHIFT
    }

    # Simulate initial application
    send_event("APPLICATION", {"name": "TestApp"}, event_id)
    event_id += 1

    # Simulate initial window info
    send_event("WINDOW_INFO", {"kind": "ACTIVE", "ownerName": "TestApp", "windowName": "Test Window", "windowNumber": 1, "windowLayer": 0, "boundsX": 10, "boundsY": 20, "boundsWidth": 800, "boundsHeight": 600}, event_id)
    event_id += 1
    send_event("WINDOW_INFO", {"kind": "ALL", "data": [{"ownerName": "TestApp", "windowName": "Test Window", "windowNumber": 1, "windowLayer": 0, "boundsX": 10, "boundsY": 20, "boundsWidth": 800, "boundsHeight": 600}]}, event_id)
    event_id += 1

    while True:
        # --- Test Letters ---
        # Simulate "a" key (no modifiers)
        send_event("CHARACTER", "DOWN,a,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("CHARACTER", "UP,a,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate Shift key down
        modifier_code = list(modifier_map.keys())[list(modifier_map.values()).index('shift')]
        send_event("MODIFIER", f"{modifier_code},DOWN,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)

        # Simulate "B" key (Shift held down)
        send_event("CHARACTER", "DOWN,B,0,0,SHIFT", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("CHARACTER", "UP,B,0,0,SHIFT", event_id)
        event_id += 1
        time.sleep(0.1)

        # Simulate Shift key up
        send_event("MODIFIER", f"{modifier_code},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # --- Test Special Keys ---
        # Simulate "return" key (Enter/Return)
        send_event("SPECIAL_KEY", "DOWN,return,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,return,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "delete" key (Backspace)
        send_event("SPECIAL_KEY", "DOWN,delete,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,delete,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "tab" key
        send_event("SPECIAL_KEY", "DOWN,tab,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,tab,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "upArrow" key
        send_event("SPECIAL_KEY", "DOWN,upArrow,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,upArrow,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # --- Test Mouse ---
        # Simulate mouse click
        send_event("MOUSE", "DOWN,0,100,150", event_id)  # Simulate left click
        event_id += 1
        time.sleep(0.1)
        send_event("MOUSE", "UP,0,100,150", event_id)  # Simulate left click
        event_id += 1
        time.sleep(0.5)

        # Simulate scroll event
        send_event("MOUSE", f"SCROLL,1,{random.randint(0, 500)},{random.randint(0, 500)}", event_id)  # Simulate scroll
        event_id += 1
        time.sleep(0.5)

        # Simulate mouse move
        send_event("MOUSE", f"MOVE,{random.randint(0, 500)},{random.randint(0, 500)}", event_id)
        event_id += 1
        time.sleep(0.5)

        # --- Test Window/Application Change ---
        # Simulate application change (every 5 seconds)
        if event_id >= event_threshold:
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
            event_threshold += 25

        # --- Test More Special Keys and Modifiers ---

        # Simulate "command" + "tab" (application switcher)
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('cmd')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("SPECIAL_KEY", "DOWN,tab,0,0,CMD", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,tab,0,0,CMD", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('cmd')]},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "control" + "upArrow" (Mission Control)
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('ctrl')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("SPECIAL_KEY", "DOWN,upArrow,0,0,CTRL", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,upArrow,0,0,CTRL", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('ctrl')]},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "alt"+ "delete"
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('alt')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("SPECIAL_KEY", "DOWN,delete,0,0,ALT", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,delete,0,0,ALT", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('alt')]},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "control" + "shift" + "f"
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('ctrl')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('shift')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("CHARACTER", "DOWN,f,0,0,CTRL+SHIFT", event_id)  # Added modifier string
        event_id += 1
        time.sleep(0.1)
        send_event("CHARACTER", "UP,f,0,0,CTRL+SHIFT", event_id)  # Added modifier string
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('shift')]},UP,0,0,", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('ctrl')]},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "pageDown" key
        send_event("SPECIAL_KEY", "DOWN,pageDown,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,pageDown,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "pageUp" key
        send_event("SPECIAL_KEY", "DOWN,pageUp,0,0,", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,pageUp,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "F1" key
        send_event("SPECIAL_KEY", "DOWN,f1,0,0,", event_id)  # Note the lowercase "f" for function keys
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,f1,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

        # Simulate "F2" key with "fn" modifier
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('fn')]},DOWN,0,0,", event_id)
        event_id += 1
        send_event("SPECIAL_KEY", "DOWN,f2,0,0,FN", event_id)
        event_id += 1
        time.sleep(0.1)
        send_event("SPECIAL_KEY", "UP,f2,0,0,FN", event_id)
        event_id += 1
        send_event("MODIFIER", f"{list(modifier_map.keys())[list(modifier_map.values()).index('fn')]},UP,0,0,", event_id)
        event_id += 1
        time.sleep(0.5)

if __name__ == "__main__":
    main()