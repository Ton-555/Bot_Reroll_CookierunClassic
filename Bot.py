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
    ("tap", 1127, 33, 2.0,    "Press Setting"),
    ("tap", 1010, 150, 1.5,   "Press Game Info"),
    ("tap", 1013, 616, 65.0,  "Press Delete Account & Wait"),
    ("tap", 796, 494, 3.0,    "Press Confirm Delete"),
    ("tap", 626, 460, 5.0,    "Press Confirm"),
    ("tap", 665, 639, 4.5,    "Press DevPlay Login"),
    ("tap", 841, 485, 10.0,    "Press Play ID"),
    ("tap", 635, 460, 7.0,    "Press Confirm HI"),
    ("tap", 1197, 38, 4.5,    "Press Stop game"),
    ("tap", 608, 428, 4.0,    "Press Quit"),
    ("tap", 624, 360, 4.5,    "Press Quit tutorial"),
    ("tap", 631, 376, 5.0,    "Press Enter name"),
    ("text", "MyCharacterName", 2.5, "Input name"),
    ("keyevent", "KEYCODE_ENTER", 5.5, "Press Enter"),
    ("tap", 629, 492, 5.5,    "Press Confirm name"),
    ("tap", 1125, 56, 5.0,    "Press Skip ads news 1"),
    ("tap", 1125, 56, 5.0,    "Press Skip ads news 2"),
    ("tap", 1126, 72, 5.0,    "Press Skip ads news 3"),
    ("tap", 639, 568, 5.0,    "Press get gem"),
    ("tap", 639, 568, 5.0,    "Press get coin"),
    ("tap", 639, 568, 5.0,    "Press get gift point"),
    ("tap", 643, 659, 8.0,    "Press Confirm Daily Check-in"),
    ("tap", 642, 574, 5.0,    "Press Confirm gift ticket"),
    ("tap", 642, 574, 5.0,    "Press Confirm gift EXPx2"),
    ("tap", 642, 574, 5.0,    "Press Confirm gift Coin 200K"),
    ("tap", 642, 574, 5.0,    "Press Confirm gift Golden Dough"),
    ("tap", 642, 574, 5.0,    "Press Confirm gift 5 tickets"),
    ("tap", 642, 574, 7.0,    "Press Confirm gift 30 keys "),
    ("tap", 695, 678, 3.0,    "Press Mail Boxs"),
    ("tap", 826, 149, 5.0,    "Press Reward in mail boxs"),
    ("tap", 652, 622, 10.0,   "Press Claim all"),
    ("tap", 641, 571, 4.0,    "Press Confirm all rewards"),
    ("tap", 1128, 89, 1.0,    "Press Exit mail boxs"),
]


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
