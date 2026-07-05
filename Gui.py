"""
GUI Main Interface for MuMu Player Reroll Bot
"""

import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import cv2
import numpy as np

from Bot import STEPS, tap as bot_tap, input_text as bot_text, keyevent as bot_keyevent

DEFAULT_DEVICE_ID = "127.0.0.1:16384"
REFRESH_INTERVAL = 0.7

_coord_window_running = False
_coord_thread = None
_bot_running = False
_bot_thread = None


def screencap(device_id):
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
    subprocess.run(["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)])


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MuMu Bot - Reroll Tool")
        self.root.geometry("700x550")
        self.root.resizable(True, True)

        self.cycle_count = 0
        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        settings_frame = ttk.LabelFrame(main_frame, text="Device Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_frame, text="Device ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.device_id_var = tk.StringVar(value=DEFAULT_DEVICE_ID)
        self.device_entry = ttk.Entry(settings_frame, textvariable=self.device_id_var, width=30)
        self.device_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        ttk.Button(settings_frame, text="List Devices", command=self._on_list_devices).grid(
            row=0, column=2, padx=5
        )

        coord_frame = ttk.LabelFrame(main_frame, text="Coordinate Picker", padding=5)
        coord_frame.pack(fill=tk.X, pady=(0, 5))

        self.find_pos_btn = ttk.Button(coord_frame, text="Find Position", command=self._on_find_position)
        self.find_pos_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_pos_btn = ttk.Button(coord_frame, text="Stop Picker", command=self._on_stop_picker, state=tk.DISABLED)
        self.stop_pos_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.capture_once_btn = ttk.Button(coord_frame, text="Capture Once", command=self._on_capture_once)
        self.capture_once_btn.pack(side=tk.LEFT)

        bot_frame = ttk.LabelFrame(main_frame, text="Bot Control", padding=5)
        bot_frame.pack(fill=tk.X, pady=(0, 5))

        self.bot_info_var = tk.StringVar(value="Ready")
        self.bot_info_lbl = ttk.Label(bot_frame, textvariable=self.bot_info_var, foreground="gray")
        self.bot_info_lbl.pack(side=tk.LEFT, padx=(0, 10))

        self.run_bot_btn = ttk.Button(bot_frame, text="Run Bot", command=self._on_run_bot)
        self.run_bot_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_bot_btn = ttk.Button(bot_frame, text="Stop Bot", command=self._on_stop_bot, state=tk.DISABLED)
        self.stop_bot_btn.pack(side=tk.LEFT)

        self.loop_var = tk.BooleanVar(value=True)
        self.loop_check = ttk.Checkbutton(
            bot_frame, text="Loop", variable=self.loop_var
        )
        self.loop_check.pack(side=tk.RIGHT, padx=(10, 0))

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_widget = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, width=70, height=15,
            font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        self.log_widget.tag_config("info", foreground="#4ec9b0")
        self.log_widget.tag_config("coord", foreground="#569cd6")
        self.log_widget.tag_config("error", foreground="#f44747")
        self.log_widget.tag_config("success", foreground="#6a9955")
        self.log_widget.tag_config("warn", foreground="#dcdcaa")

        self._log("Application started.\n", "success")
        self._log(f"Default device: {DEFAULT_DEVICE_ID}\n", "info")
        self._log(f"Bot steps loaded: {len(STEPS)}\n\n", "info")

    def _log(self, text, tag=None):
        self.log_widget.insert(tk.END, text, tag)
        self.log_widget.see(tk.END)

    def _on_list_devices(self):
        self._log("Running: adb devices...\n", "info")
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            output = result.stdout.strip()
            lines = output.splitlines()
            self._log(f"{output}\n\n", "info")
            devices = [l.split()[0] for l in lines[1:] if l.strip() and "\tdevice" in l]
            if devices:
                self._log(f"Found devices: {', '.join(devices)}\n", "success")
            else:
                self._log("No devices found. Check your connection.\n", "error")
        except FileNotFoundError:
            self._log("Error: adb not found. Make sure adb is in your PATH.\n", "error")

    def _on_find_position(self):
        global _coord_window_running, _coord_thread

        device_id = self.device_id_var.get().strip()
        if not device_id:
            self._log("Error: Device ID is empty.\n", "error")
            return

        self._log(f"Starting live coordinate picker for: {device_id}\n", "info")
        self._log("Controls: Left-click=coords | Right-click=tap | SPACE=pause | q=quit\n", "info")
        self._log("-" * 50 + "\n", "info")

        self.find_pos_btn.config(state=tk.DISABLED)
        self.stop_pos_btn.config(state=tk.NORMAL)

        _coord_window_running = True
        _coord_thread = threading.Thread(target=self._run_coord_picker, args=(device_id,), daemon=True)
        _coord_thread.start()

    def _on_stop_picker(self):
        global _coord_window_running
        _coord_window_running = False
        self.find_pos_btn.config(state=tk.NORMAL)
        self.stop_pos_btn.config(state=tk.DISABLED)
        self._log("Coordinate picker stopped.\n\n", "info")

    def _on_capture_once(self):
        device_id = self.device_id_var.get().strip()
        if not device_id:
            self._log("Error: Device ID is empty.\n", "error")
            return
        self._log(f"Capturing screenshot from: {device_id}...\n", "info")
        img = screencap(device_id)
        if img is not None:
            self._log("Capture successful. Displaying image...\n", "success")
            cv2.imshow("Single Capture - Press any key to close", img)
            cv2.waitKey(0)
            cv2.destroyWindow("Single Capture - Press any key to close")
            self._log("Capture window closed.\n\n", "info")
        else:
            self._log("Error: Failed to capture screenshot.\n", "error")

    def _on_run_bot(self):
        global _bot_running, _bot_thread

        device_id = self.device_id_var.get().strip()
        if not device_id:
            self._log("Error: Device ID is empty.\n", "error")
            return

        self.cycle_count = 0
        self._log(f"=== Starting Bot on device: {device_id} ===\n", "success")
        self._log(f"Total steps per cycle: {len(STEPS)}\n", "info")
        self._log(f"Loop mode: {'ON' if self.loop_var.get() else 'OFF (single run)'}\n", "info")
        self._log("-" * 50 + "\n", "info")

        self.run_bot_btn.config(state=tk.DISABLED)
        self.stop_bot_btn.config(state=tk.NORMAL)
        self.bot_info_var.set("Running...")
        self.bot_info_lbl.config(foreground="green")

        _bot_running = True
        _bot_thread = threading.Thread(target=self._run_bot, args=(device_id,), daemon=True)
        _bot_thread.start()

    def _on_stop_bot(self):
        global _bot_running
        _bot_running = False
        self._log("\n[Bot] Stop requested. Waiting for current cycle to finish...\n", "warn")

    def _bot_stopped(self):
        self.run_bot_btn.config(state=tk.NORMAL)
        self.stop_bot_btn.config(state=tk.DISABLED)
        self.bot_info_var.set("Stopped")
        self.bot_info_lbl.config(foreground="red")

    def _run_bot(self, device_id):
        global _bot_running

        while _bot_running:
            self.cycle_count += 1

            def log_cycle_start():
                self._log(f"\n=== Reroll Cycle #{self.cycle_count} ===\n", "success")
                self.bot_info_var.set(f"Cycle #{self.cycle_count}")
            self.root.after(0, log_cycle_start)

            for i, step in enumerate(STEPS, 1):
                if not _bot_running:
                    break

                action = step[0]
                delay = step[-2]
                note = step[-1]

                if action == "tap":
                    _, x, y, _, _ = step
                    bot_tap(device_id, x, y)
                    detail = f"({x}, {y})"
                elif action == "text":
                    _, text, _, _ = step
                    bot_text(device_id, text)
                    detail = f'"{text}"'
                elif action == "keyevent":
                    _, keycode, _, _ = step
                    bot_keyevent(device_id, keycode)
                    detail = keycode
                else:
                    detail = "?"

                step_num = i
                def log_step():
                    self._log(f"  [{step_num:02d}/{len(STEPS)}] [{action}] {note}  {detail}  wait {delay:.1f}s\n", "coord")
                self.root.after(0, log_step)

                elapsed = 0
                while _bot_running and elapsed < delay:
                    time.sleep(0.1)
                    elapsed += 0.1

            if not _bot_running:
                self.root.after(0, lambda: self._log("\n[Bot] Cycle interrupted by stop.\n", "warn"))
                break

            def log_cycle_end():
                self._log(f"--- Cycle #{self.cycle_count} complete ---\n", "success")
            self.root.after(0, log_cycle_end)

            if not self.loop_var.get():
                self.root.after(0, lambda: self._log("[Bot] Single run complete.\n", "info"))
                break

            self.root.after(0, lambda: self._log("Waiting 3s before next cycle...\n", "info"))
            for _ in range(30):
                if not _bot_running:
                    break
                time.sleep(0.1)

        _bot_running = False
        self.root.after(0, self._bot_stopped)

    def _run_coord_picker(self, device_id):
        global _coord_window_running

        paused = False
        latest_frame = None
        last_capture_time = 0

        def on_mouse(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self._log(f"[Get coords] x={x}, y={y}\n", "coord")
            elif event == cv2.EVENT_RBUTTONDOWN:
                self._log(f"[TAP] x={x}, y={y} ... ", "info")
                send_tap(device_id, x, y)
                self._log(f"done.\n", "success")

        window_name = "MuMu Live View (left=coords, right=tap, q=quit)"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, on_mouse)

        while _coord_window_running:
            now = time.time()
            if not paused and (now - last_capture_time >= REFRESH_INTERVAL):
                frame = screencap(device_id)
                if frame is not None:
                    latest_frame = frame
                last_capture_time = now

            if latest_frame is not None:
                display = latest_frame.copy()
                status = "PAUSED" if paused else "LIVE"
                color = (0, 0, 255) if paused else (0, 255, 0)
                cv2.putText(display, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.imshow(window_name, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):
                paused = not paused

        cv2.destroyAllWindows()
        _coord_window_running = False
        self._log("Coordinate picker window closed.\n\n", "info")
        self.root.after(0, lambda: self.find_pos_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_pos_btn.config(state=tk.DISABLED))

    def on_close(self):
        global _coord_window_running, _bot_running
        _coord_window_running = False
        _bot_running = False
        cv2.destroyAllWindows()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
