"""
Reroll Bot for MuMu Player
Executes a predefined sequence of actions to automate the reroll process.

Step formats (action_type, *args, delay_seconds, "description"):
  ("tap", x, y, delay, note)               - Tap at (x, y)
  ("text", "some text", delay, note)        - Input text via adb
  ("keyevent", "KEYCODE_ENTER", delay, note) - Send keyevent
"""

import subprocess
import time
import sys

DEVICE_ID = "127.0.0.1:16384"

STEPS = [
    ("tap", 1127, 33, 3.0,    "Press Setting"),  # index 00
    ("tap", 1010, 150, 3.0,   "Press Game Info"),  # index 01
    ("tap", 1013, 616, 70.0,  "Press Delete Account & Wait"),  # index 02
    ("tap", 796, 494, 5.0,    "Press Confirm Delete"),  # index 03
    ("tap", 626, 460, 15.0,    "Press Confirm"),  # index 04
    ("tap", 665, 639, 7.5,    "Press DevPlay Login"),  # index 05
    ("tap", 841, 485, 30.0,    "Press Play ID"),  # index 06
    ("tap", 635, 460, 14.0,    "Press Confirm HI"),  # index 07
    ("tap", 1197, 38, 6.5,    "Press Stop game"),  # index 08
    ("tap", 608, 428, 6.0,    "Press Quit"),  # index 09
    ("tap", 624, 360, 6.5,    "Press Quit tutorial"),  # index 10
    ("tap", 631, 376, 5.0,    "Press Enter name"),  # index 11
    ("text", "MyCharacterName", 3.5, "Input name"),  # index 12
    ("keyevent", "KEYCODE_ENTER", 6.5, "Press Enter"),  # index 13
    ("tap", 629, 492, 8.0,    "Press Confirm name"),  # index 14
    ("tap", 1125, 56, 5.0,    "Press Skip ads news 1"),  # index 15
    ("tap", 1125, 56, 5.0,    "Press Skip ads news 2"),  # index 16
    ("tap", 1126, 72, 5.0,    "Press Skip ads news 3"),  # index 17
    ("tap", 639, 568, 5.0,    "Press get gem"),  # index 18
    ("tap", 639, 568, 5.0,    "Press get coin"),  # index 19
    ("tap", 639, 568, 5.0,    "Press get gift point"),  # index 20
    ("tap", 643, 659, 8.0,    "Press Confirm Daily Check-in"),  # index 21
    ("tap", 642, 574, 5.0,    "Press Confirm gift ticket"),  # index 22
    ("tap", 642, 574, 5.0,    "Press Confirm gift EXPx2"),  # index 23
    ("tap", 642, 574, 5.0,    "Press Confirm gift Coin 200K"),  # index 24
    ("tap", 642, 574, 5.0,    "Press Confirm gift Golden Dough"),  # index 25
    ("tap", 642, 574, 5.0,    "Press Confirm gift 5 tickets"),  # index 26
    ("tap", 642, 574, 7.0,    "Press Confirm gift 30 keys "),  # index 27
    ("tap", 695, 678, 3.0,    "Press Mail Boxs"),  # index 28
    ("tap", 826, 149, 5.0,    "Press Reward in mail boxs"),  # index 29
    ("tap", 652, 622, 10.0,   "Press Claim all"),  # index 30
    ("tap", 641, 571, 4.0,    "Press Confirm all rewards"),  # index 31
    ("tap", 1128, 89, 3.0,    "Press Exit mail boxs"),  # index 32

    ("tap", 1088, 533, 3.0,    "Press Treasure Button"),  # index 33
    ("tap", 288, 645, 3.0,    "Press Draw"),  # index 34
    #loop
    #have matching img gear
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 1"),  # index 35
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 1"),  # index 36
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 2"),  # index 37
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 2"),  # index 38
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 3"),  # index 39
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 3"),  # index 40
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 4"),  # index 41
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 4"),  # index 42
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 5"),  # index 43
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 5"),  # index 44
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 6"),  # index 45
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 6"),  # index 46
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 7"),  # index 47
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 7"),  # index 48
    ("tap", 749, 522, 10.0,    "Press Open Supreme boxs 8"),  # index 49
    ("tap", 644, 567, 3.0,    "Press Confirm get Treasure 8"),  # index 50
    ("tap", 1128, 89, 3.0,    "Press Exit Treasure"),  # index 51
    ("tap", 1128, 89, 3.0,    "Press Exit con firm Treasure2"),  # index 52
    #open treasure add 6+1 If have pao or moungud
    ("tap", 1006, 552, 15.0,    "Press Open Treasure 6+1"),  # index 53
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 1"),  # index 54
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 2"),  # index 55
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 3"),  # index 56
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 4"),  # index 57
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 5"),  # index 58
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 6"),  # index 59
    ("tap", 640, 573, 3.0,    "Press  Confirm Treasure 7"),  # index 60
    ("tap", 1038, 122, 15.0,    "Press Exit Treasure 6+1"),  # index 61
    ("tap", 1128, 89, 3.0,    "Press Exit Treasure"),  # index 62
    ("tap", 1128, 89, 3.0,    "Press Exit con firm Treasure2"),  # index 63
    
    #Open pet 9 time 
    #if have two open pets and 6+1
    ("tap", 810, 551, 4.0,    "Press Pet Button"),  # index 64
    ("tap", 171, 637, 4.0,    "Press Hatch Pet"),  # index 65
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 1"),  # index 66
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem "),  # index 67
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 2"),  # index 68
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 2"),  # index 69
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 3"),  # index 70
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 3"),  # index 71
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 4"),  # index 72
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 4"),  # index 73
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 5"),  # index 74
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 5"),  # index 75
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 6"),  # index 76
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 6"),  # index 77
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 7"),  # index 78
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 7"),  # index 79
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 8"),  # index 80
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 8"),  # index 81
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 9"),  # index 82
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 9"),  # index 83
    ("tap", 1124, 114, 3.0,    "Press Exit Hatch"),  # index 84
    ("tap", 1219, 123, 3.0,    "Press Exit Hatch to Main menu"),  # index 85

    #Open pet 15 time
    ("tap", 810, 551, 4.0,    "Press Pet Button"),  # index 86
    ("tap", 171, 637, 4.0,    "Press Hatch Pet"),  # index 87
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 1"),  # index 88
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem "),  # index 89
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 2"),  # index 90
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 2"),  # index 91
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 3"),  # index 92
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 3"),  # index 93
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 4"),  # index 94
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 4"),  # index 95
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 5"),  # index 96
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 5"),  # index 97
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 6"),  # index 98
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 6"),  # index 99
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 7"),  # index 100
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 7"),  # index 101
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 8"),  # index 102
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 8"),  # index 103 
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 9"),  # index 104
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 9"),  # index 105 
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 10"),  # index 106
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 10"),  # index 107 
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 11"),  # index 108
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 11"),  # index 109
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 12"),  # index 110
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 12"),  # index 111 
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 13"),  # index 112
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 13"),  # index 113
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 14"),  # index 114
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 14"),  # index 115 
    ("tap", 964, 586, 12.0,    "Press Hatch 20 Gem 15"),  # index 116
    ("tap", 1016, 107, 3.0,    "Press Exit Hatch 20 gem 15"),  # index 117
    ("tap", 1124, 114, 3.0,    "Press Exit Hatch"),  # index 118
    ("tap", 1219, 123, 3.0,    "Press Exit Hatch to Main menu"),  # index 119 
]

STEP_GROUPS = {
    "reset_account": {
        "label": "Reset Account",
        "steps": STEPS[0:5],
    },
    "devplay_login": {
        "label": "DevPlay Login",
        "steps": STEPS[5:8],
    },
    "exit_tutorial": {
        "label": "Exit Tutorial",
        "steps": STEPS[8:11],
    },
    "name_character": {
        "label": "Name Character",
        "steps": STEPS[11:15],
    },
    "skip_news": {
        "label": "Skip News",
        "steps": STEPS[15:18],
    },
    "claim_popup_rewards": {
        "label": "Claim Popup Rewards",
        "steps": STEPS[18:28],
    },
    "mailbox_rewards": {
        "label": "Mailbox Rewards",
        "steps": STEPS[28:33],
    },
    "enter_treasure_draw": {
        "label": "Enter Treasure Draw",
        "steps": STEPS[33:35],
    },
    "open_treasure_boxes": {
        "label": "Open Treasure Boxes",
        "steps": STEPS[35:53],
    },
    "exit_treasure": {
        "label": "Exit Treasure",
        "steps": STEPS[51:53],
    },
    "open_treasure_boxs_6+1":{
        "label": "Open Treasure Boxes 6+1",
        "steps": STEPS[53:64],
    },
    "Hatch_9_time":{
        "label": "Hatch 9 time",
        "steps": STEPS[64:86],
    },
    "Hatch_15_time":{
        "label": "Hatch 15 time",
        "steps": STEPS[86:120],
    },
    "State_Reset_ID": {                     #State number 6
        "label": "State_Reset_ID",
        "groups": [
            "reset_account",
            "devplay_login",
            "exit_tutorial",
            "name_character",
            "skip_news",
            "claim_popup_rewards",
            "mailbox_rewards",
        ],
    },
    "State_Open_Free_Treasure": {         #State number 1
        "label": "State_Open_Free_Treasure",
        "groups": [
            "enter_treasure_draw",
            "open_treasure_boxes"
        ],
    },
    "State_Open_Treasure_6+1": {         #State number 2
        "label": "State_Open_Treasure_6+1",
        "groups": [
            "enter_treasure_draw",
            "open_treasure_boxs_6+1"
        ],
    },
    "State_Open_Pets_15": {         #State number 3 
        "label": "State_Open_Pets_15",
        "groups": [
            "Hatch_15_time",
        ],
    },
    "State_Open_Pets_9": {         #State number 5
        "label": "State_Open_Pets_9",
        "groups": [
            "Hatch_9_time",
        ],
    },
}

MAIN_FLOW = [
    "reset_account",
    "devplay_login",
    "exit_tutorial",
    "name_character",
    "skip_news",
    "claim_popup_rewards",
    "mailbox_rewards",
    "enter_treasure_draw",
    "open_treasure_boxes",
    "exit_treasure",
]


def resolve_group_steps(group_key, seen=None):
    if seen is None:
        seen = []
    if group_key in seen:
        chain = " -> ".join(seen + [group_key])
        raise ValueError(f"Circular step group reference: {chain}")

    group = STEP_GROUPS[group_key]
    if "steps" in group:
        return list(group["steps"])

    steps = []
    for child_key in group.get("groups", []):
        steps.extend(resolve_group_steps(child_key, seen + [group_key]))
    return steps


def get_steps_for_flow(group_keys=None):
    if group_keys is None:
        group_keys = MAIN_FLOW

    steps = []
    for group_key in group_keys:
        steps.extend(resolve_group_steps(group_key))
    return steps


def get_step_label(step, index=None):
    action = step[0]
    note = step[-1]
    prefix = f"{index:02d}. " if index is not None else ""
    return f"{prefix}[{action}] {note}"


def tap(device_id, x, y):
    subprocess.run(
        ["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)],
        capture_output=True
    )


def input_text(device_id, text):
    subprocess.run(
        ["adb", "-s", device_id, "shell", "input", "text", text],
        capture_output=True
    )


def keyevent(device_id, keycode):
    subprocess.run(
        ["adb", "-s", device_id, "shell", "input", "keyevent", keycode],
        capture_output=True
    )


def execute_step(device_id, step):
    action = step[0]
    if action == "tap":
        _, x, y, _, _ = step
        tap(device_id, x, y)
        return f"({x}, {y})"
    elif action == "text":
        _, text, _, _ = step
        input_text(device_id, text)
        return f'"{text}"'
    elif action == "keyevent":
        _, keycode, _, _ = step
        keyevent(device_id, keycode)
        return keycode
    else:
        raise ValueError(f"Unknown action type: {action}")


def run_once(device_id):
    print(f"Starting reroll cycle on device: {device_id}")
    print("-" * 50)

    for i, step in enumerate(STEPS, 1):
        action = step[0]
        delay = step[-2]  # delay is 2nd to last
        note = step[-1]   # note is last

        detail = execute_step(device_id, step)
        print(f"  [{i:02d}/{len(STEPS)}] [{action}] {note}  {detail} -> done. Waiting {delay:.1f}s")
        time.sleep(delay)

    print("-" * 50)
    print("Cycle complete.\n")


def main():
    print(f"Device: {DEVICE_ID}")
    print(f"Total steps per cycle: {len(STEPS)}")
    print()

    cycle = 1
    while True:
        print(f"=== Reroll Cycle #{cycle} ===")
        run_once(DEVICE_ID)
        cycle += 1
        print("Next cycle in 3 seconds... (Ctrl+C to stop)")
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped.")
        sys.exit(0)
