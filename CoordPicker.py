"""
Coordinate Picker (Live Auto-Refresh) for MuMu Player

Features:
- Screenshot updates automatically in live mode (no need to press r)
- Left-click  -> Show x, y coordinates in terminal (coordinate viewer mode)
- Right-click -> Send actual tap command to game at that position (test Step 4)
- Press q     -> Quit program
- Press SPACE -> Pause/resume image refresh (to freeze frame for precise viewing)

Usage:
1. Set DEVICE_ID below to match your device (check from `adb devices`)
2. Run: python coord_picker_live.py
3. Play the game normally (in MuMu window) -> this window will update live
4. Left-click to note coordinates, or right-click to test tapping via script
"""

import subprocess
import time
import cv2
import numpy as np

# ===== Set your device ID here =====
DEVICE_ID = "127.0.0.1:16384"  # from command: adb devices
REFRESH_INTERVAL = 0.7          # seconds between each capture (adjust based on your PC)
# ===================================

paused = False
latest_frame = None


def screencap(device_id):
    """Capture current device screenshot and convert to OpenCV-compatible image"""
    result = subprocess.run(
        ["adb", "-s", device_id, "exec-out", "screencap", "-p"],
        capture_output=True
    )
    if not result.stdout:
        return None
    img_array = np.frombuffer(result.stdout, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return img


def send_tap(device_id, x, y):
    """Send actual tap command to device at the specified coordinates"""
    subprocess.run(["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)])


def on_mouse_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f">>> [Get coords] x={x}, y={y}   (note this down!)")
    elif event == cv2.EVENT_RBUTTONDOWN:
        print(f">>> [TAP] x={x}, y={y} ...")
        send_tap(DEVICE_ID, x, y)
        print(f"    Tapped at ({x}, {y})")


def main():
    global paused, latest_frame

    print(f"Connecting to device: {DEVICE_ID}")
    print("Controls: Left-click=coords | Right-click=tap | SPACE=pause/resume | q=quit")
    print("-" * 60)

    window_name = "MuMu Live View (left=coords, right=tap, q=quit)"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse_click)

    last_capture_time = 0

    while True:
        now = time.time()

        # Auto-capture new frame on interval (unless paused)
        if not paused and (now - last_capture_time >= REFRESH_INTERVAL):
            frame = screencap(DEVICE_ID)
            if frame is not None:
                latest_frame = frame
            last_capture_time = now

        if latest_frame is not None:
            display_frame = latest_frame.copy()
            status_text = "PAUSED" if paused else "LIVE"
            cv2.putText(
                display_frame, status_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0, 0, 255) if paused else (0, 255, 0), 2
            )
            cv2.imshow(window_name, display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
            print("Paused (press SPACE again to resume)" if paused else "Resumed")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
