"""
GUI Main Interface for MuMu Player Reroll Bot
"""

import json
import threading
import time
import tkinter as tk
import sys
import urllib.error
import urllib.request
from pathlib import Path
import customtkinter as ctk
import cv2
import numpy as np

import Bot
from Bot import (
    MAIN_FLOW,
    STEPS,
    STEP_GROUPS,
    get_step_label,
    get_steps_for_flow,
    get_runtime_step_delay,
    run_hidden,
    jitter_tap_coordinates,
    resolve_group_steps,
    tap as bot_tap,
    input_text as bot_text,
    keyevent as bot_keyevent,
)

DEFAULT_DEVICE_ID = "127.0.0.1:16384"
MAX_DEVICE_SLOTS = 6
REFRESH_INTERVAL = 0.7
APP_BG = "#101114"
SURFACE_BG = "#181a1f"
SURFACE_ALT_BG = "#121318"
LOG_BG = "#0c0d10"
BORDER_COLOR = "#2b2f36"
TEXT_COLOR = "#e5e7eb"
TEXT_MUTED_COLOR = "#8b949e"
ACCENT_COLOR = "#1f6f68"
ACCENT_HOVER_COLOR = "#287f77"
TAB_SELECTED_TEXT_COLOR = "#5eead4"
DANGER_COLOR = "#7f2d2d"
DANGER_HOVER_COLOR = "#923838"
SUCCESS_COLOR = "#3f8f5f"
WARN_COLOR = "#b38a22"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
IMAGE_SELECT_DIR = RESOURCE_DIR / "Image_Select"
DISCORD_WEBHOOK_CONFIG_PATH = APP_DIR / "discord_webhook.local"
STEP_CONFIG_PATH = APP_DIR / "step_config.local"
RUNTIME_CONFIG_PATH = APP_DIR / "runtime_config.local"
DISCORD_WEBHOOK_TIMEOUT = 4
IMAGE_MATCH_THRESHOLD = 0.84
SCORE_MATCH_THRESHOLD = 0.84
MATCH_SCALES = (0.90, 0.95, 1.0, 1.05, 1.10)
SCORE_CHECK_ATTEMPTS = 5
SCORE_CHECK_RETRY_DELAY = 0.5
OPEN_BOX_STEP_PREFIX = "Press Open Supreme boxs"
SCORE_TARGET_STEMS = {
    "Victor'sFeatherLaurelWreath",
    "Jingle-jangleCoinWallet",
    "TaterTraderhatched!",
}
SCORE_TARGET_SHORT_NAMES = {
    "TaterTraderhatched!": "Tater Trader",
    "TaterTraderHatched!": "Tater Trader",
    "Victor'sFeatherLaurelWreath": "Crown",
    "Jingle-jangleCoinWallet": "Bag Coin",
}
PET_TEST_TARGET_STEM = "TaterTraderhatched!"
MAIN_LOG_FILTER_ALL = "All Devices"
TARGET_MATCH_THRESHOLDS = {
    PET_TEST_TARGET_STEM: 0.82,
}
MULTI_PART_MATCH_TARGETS = {
    PET_TEST_TARGET_STEM: {
        "required_parts": 4,
        "min_average_score": 0.90,
    },
}
PET_CHECK_ATTEMPTS = 8
SCORE_TARGET_CHOICES = ("2", "3")
DEFAULT_SCORE_TARGET = 3
SCORE_NOTIFY_MILESTONES = {2, 3}
SCORE_CHECK_STEP_PREFIXES = (
    "Press Open Supreme boxs",
    "Press Open Treasure 6+1",
    "Press  Confirm Treasure",
    "Press Hatch 20 Gem",
)
STATE_OPEN_FREE_TREASURE = "State_Open_Free_Treasure"
STATE_OPEN_TREASURE_6_PLUS_1 = "State_Open_Treasure_6+1"
STATE_OPEN_PETS_15 = "State_Open_Pets_15"
STATE_OPEN_PETS_9 = "State_Open_Pets_9"
STATE_RESET_ID = "State_Reset_ID"

_coord_window_running = False
_coord_thread = None

DEFAULT_RUNTIME_TAP_POSITION_JITTER = Bot.TAP_POSITION_JITTER
DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MIN = Bot.DELAY_EXTRA_SECONDS_MIN
DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MAX = Bot.DELAY_EXTRA_SECONDS_MAX


def screencap(device_id):
    result = run_hidden(
        ["adb", "-s", device_id, "exec-out", "screencap", "-p"],
        capture_output=True
    )
    if not result.stdout:
        return None
    img_array = np.frombuffer(result.stdout, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return img


def send_tap(device_id, x, y):
    run_hidden(["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)])


def score_target_short_name(target_name):
    return SCORE_TARGET_SHORT_NAMES.get(target_name, target_name)


def read_image_file(path):
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def crop_red_box_region(img):
    regions = extract_red_box_regions(img)
    return max(regions, key=lambda region: region.shape[0] * region.shape[1])


def extract_red_box_regions(img):
    blue = img[:, :, 0]
    green = img[:, :, 1]
    red = img[:, :, 2]
    marker_masks = (
        ((green > 170) & (red >= 15) & (red <= 90) & (blue < 80)),  # #26E600 scope marker
        ((red > 170) & (green < 110) & (blue < 110)),              # legacy red scope marker
    )
    mask = None
    for marker_mask in marker_masks:
        candidate = marker_mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            mask = candidate
            break
    if mask is None:
        return [img]

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 60 or h < 25:
            continue

        inset = max(4, min(8, min(w, h) // 8))
        cropped = img[y + inset:y + h - inset, x + inset:x + w - inset]
        if cropped.size:
            regions.append((y, x, cropped))

    regions.sort(key=lambda region: (region[0], region[1]))
    return [region[2] for region in regions] or [img]


def load_select_templates():
    templates = []
    if not IMAGE_SELECT_DIR.exists():
        return templates

    for path in sorted(IMAGE_SELECT_DIR.glob("*.png")):
        img = read_image_file(path)
        if img is None:
            continue
        template = crop_red_box_region(img)
        templates.append({
            "name": path.name,
            "stem": path.stem,
            "image": template,
            "size": template.shape[:2],
        })
    return templates


def load_score_templates():
    templates = []
    if not IMAGE_SELECT_DIR.exists():
        return templates

    for path in sorted(IMAGE_SELECT_DIR.rglob("*.png")):
        if path.stem not in SCORE_TARGET_STEMS:
            continue
        img = read_image_file(path)
        if img is None:
            continue
        for index, template in enumerate(extract_red_box_regions(img), 1):
            templates.append({
                "name": path.stem,
                "file": path.name,
                "part": index,
                "image": template,
                "size": template.shape[:2],
                "threshold": TARGET_MATCH_THRESHOLDS.get(path.stem, SCORE_MATCH_THRESHOLD),
            })
    return templates


def find_template_matches(screen, templates, threshold):
    best_by_name = {}
    part_results_by_name = {}
    screen_h, screen_w = screen.shape[:2]
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    for template in templates:
        name = template["name"]
        tmpl = template["image"]
        tmpl_h, tmpl_w = tmpl.shape[:2]
        tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)
        best_score = -1.0
        best_loc = None
        best_size = template["size"]
        best_scale = None

        for scale in MATCH_SCALES:
            if scale == 1.0:
                scaled = tmpl_gray
            else:
                scaled_w = max(1, round(tmpl_w * scale))
                scaled_h = max(1, round(tmpl_h * scale))
                scaled = cv2.resize(tmpl_gray, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

            scaled_h, scaled_w = scaled.shape[:2]
            if scaled_h > screen_h or scaled_w > screen_w:
                continue

            result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(result)
            if score > best_score:
                best_score = score
                best_loc = loc
                best_size = (scaled_h, scaled_w)
                best_scale = scale

        template["last_score"] = best_score
        template["last_location"] = best_loc
        template["last_size"] = best_size
        template["last_scale"] = best_scale
        effective_threshold = template.get("threshold", threshold)
        template["last_threshold"] = effective_threshold
        part_result = {
            "name": name,
            "file": template.get("file", template["name"]),
            "part": template.get("part"),
            "score": best_score,
            "location": best_loc,
            "size": best_size,
            "scale": best_scale,
            "threshold": effective_threshold,
            "passed": best_loc is not None and best_score >= effective_threshold,
        }
        part_results_by_name.setdefault(name, []).append(part_result)

        if name in MULTI_PART_MATCH_TARGETS:
            continue

        if not part_result["passed"]:
            continue

        current = best_by_name.get(name)
        if current is None or best_score > current["score"]:
            best_by_name[name] = part_result

    for name, policy in MULTI_PART_MATCH_TARGETS.items():
        part_results = part_results_by_name.get(name, [])
        if not part_results:
            continue

        required_parts = policy.get("required_parts", len(part_results))
        passed_parts = [part for part in part_results if part["passed"]]
        if len(part_results) < required_parts or len(passed_parts) < required_parts:
            continue

        average_score = sum(part["score"] for part in part_results) / len(part_results)
        min_average_score = policy.get("min_average_score", threshold)
        if average_score < min_average_score:
            continue

        best_part = max(part_results, key=lambda part: part["score"])
        weakest_part = min(part_results, key=lambda part: part["score"])
        best_by_name[name] = {
            "name": name,
            "file": best_part["file"],
            "part": f"{len(passed_parts)}/{len(part_results)}",
            "score": average_score,
            "location": best_part["location"],
            "size": best_part["size"],
            "scale": best_part["scale"],
            "threshold": min_average_score,
            "parts": part_results,
            "matched_parts": len(passed_parts),
            "total_parts": len(part_results),
            "min_part_score": weakest_part["score"],
            "weakest_part": weakest_part["part"],
        }

    return sorted(best_by_name.values(), key=lambda match: match["score"], reverse=True)


def find_select_template_match(screen, templates):
    matches = find_template_matches(screen, templates, IMAGE_MATCH_THRESHOLD)
    return matches[0] if matches else None


def find_score_template_matches(screen, templates):
    return find_template_matches(screen, templates, SCORE_MATCH_THRESHOLD)


def execute_bot_step(device_id, step):
    action = step[0]
    if action == "tap":
        _, x, y, _, _ = step
        x, y = jitter_tap_coordinates(x, y)
        bot_tap(device_id, x, y)
        return f"({x}, {y})"
    if action == "text":
        _, text, _, _ = step
        bot_text(device_id, text)
        return f'"{text}"'
    if action == "keyevent":
        _, keycode, _, _ = step
        bot_keyevent(device_id, keycode)
        return keycode
    return "?"


def is_valid_discord_webhook_url(url):
    return url.startswith((
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
    ))


def read_discord_webhook_url():
    try:
        return DISCORD_WEBHOOK_CONFIG_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def write_discord_webhook_url(url):
    url = url.strip()
    if url:
        DISCORD_WEBHOOK_CONFIG_PATH.write_text(url + "\n", encoding="utf-8")
    elif DISCORD_WEBHOOK_CONFIG_PATH.exists():
        DISCORD_WEBHOOK_CONFIG_PATH.unlink()


def read_step_config_overrides():
    try:
        raw_config = json.loads(STEP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw_config, dict):
        return {}
    return raw_config


def write_step_config_overrides(step_config):
    if step_config:
        STEP_CONFIG_PATH.write_text(
            json.dumps(step_config, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    elif STEP_CONFIG_PATH.exists():
        STEP_CONFIG_PATH.unlink()


def read_runtime_config_overrides():
    try:
        raw_config = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw_config, dict):
        return {}
    return raw_config


def write_runtime_config_overrides(runtime_config):
    if runtime_config:
        RUNTIME_CONFIG_PATH.write_text(
            json.dumps(runtime_config, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    elif RUNTIME_CONFIG_PATH.exists():
        RUNTIME_CONFIG_PATH.unlink()


def apply_runtime_config_values(position_jitter, delay_min, delay_max):
    Bot.TAP_POSITION_JITTER = int(position_jitter)
    Bot.DELAY_EXTRA_SECONDS_MIN = float(delay_min)
    Bot.DELAY_EXTRA_SECONDS_MAX = float(delay_max)


def post_discord_webhook(url, content):
    payload = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "MuMu-Reroll-Bot",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=DISCORD_WEBHOOK_TIMEOUT) as response:
        return response.status


class BotRunner:
    def __init__(self, app, device_id, slot_index, steps, run_label, loop_enabled):
        self.app = app
        self.device_id = device_id
        self.slot_index = slot_index
        self.steps = list(steps)
        self.run_label = run_label
        self.loop_enabled = loop_enabled
        self.running = False
        self.thread = None
        self.cycle_count = 0
        self.stop_reason = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def log(self, text, tag=None):
        self.app.safe_log(f"[D{self.slot_index + 1} {self.device_id}] {text}", tag)

    def _run(self):
        self.log(f"{self.run_label} started.\n", "success")

        while self.running:
            self.cycle_count += 1
            cycle = self.cycle_count
            self.app.root.after(0, lambda c=cycle: self.app._set_device_status(self.slot_index, f"Cycle {c}"))
            self.app.safe_main_log(
                f"[D{self.slot_index + 1} {self.device_id}] {self.run_label} Loop #{cycle}\n",
                "info",
            )
            self.log(f"=== {self.run_label} Cycle #{cycle} ===\n", "success")
            self.log(f"Loop summary: {self.run_label} Loop #{cycle} started.\n", "info")

            for i, step in enumerate(self.steps, 1):
                if not self.running:
                    break

                action = step[0]
                delay = get_runtime_step_delay(step)
                note = step[-1]

                detail = execute_bot_step(self.device_id, step)

                self.log(f"  [{i:02d}/{len(self.steps)}] [{action}] {note}  {detail}  wait {delay:.1f}s\n", "coord")

                elapsed = 0
                while self.running and elapsed < delay:
                    time.sleep(0.1)
                    elapsed += 0.1

                if self.running and self.app.should_check_select_image(step):
                    match = self.app.check_select_image(self.device_id)
                    if match:
                        self.log(
                            f"Image matched: {match['name']} score={match['score']:.3f}. Stopping next steps.\n",
                            "success",
                        )
                        self.app.notify_discord_result(
                            "Image match found",
                            (
                                f"D{self.slot_index + 1} {self.device_id}\n"
                                f"Flow: {self.run_label}\n"
                                f"Target: {match['name']} score={match['score']:.3f}\n"
                                f"Cycle: {cycle}"
                            ),
                        )
                        self.stop_reason = "image_match"
                        self.running = False
                        break
                    self.log("Image check: no selected image found.\n", "info")

            if not self.running:
                if self.stop_reason == "image_match":
                    self.log("Stopped because selected image was found.\n", "success")
                else:
                    self.log("Cycle interrupted by stop.\n", "warn")
                break

            self.log(f"--- Cycle #{cycle} complete ---\n", "success")
            self.log(f"Loop summary: {self.run_label} Loop #{cycle} complete.\n", "success")
            self.app.safe_main_log(
                f"[D{self.slot_index + 1} {self.device_id}] {self.run_label} Loop #{cycle} complete\n",
                "success",
            )

            if not self.loop_enabled:
                self.log("Single run complete.\n", "info")
                break

            self.log("Waiting 3s before next cycle...\n", "info")
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(0.1)

        self.running = False
        self.app.root.after(0, lambda: self.app._runner_finished(self.slot_index))


class ScoreFlowRunner:
    def __init__(self, app, device_id, slot_index, target_score):
        self.app = app
        self.device_id = device_id
        self.slot_index = slot_index
        self.target_score = target_score
        self.running = False
        self.thread = None
        self.score = 0
        self.matched_targets = set()
        self.matched_target_names = []
        self.notified_score_milestones = set()
        self.cycle_count = 0
        self.stop_reason = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_reason = self.stop_reason or "manual_stop"
        self.running = False

    def log(self, text, tag=None):
        self.app.safe_log(f"[D{self.slot_index + 1} {self.device_id}] {text}", tag)

    def _format_found_targets(self):
        if not self.matched_target_names:
            return ""
        names = [score_target_short_name(target) for target in self.matched_target_names]
        return f" | {', '.join(names)}"

    def _format_score_loop_main_log(self):
        return (
            f"[D{self.slot_index + 1} {self.device_id}] "
            f"Score Loop #{self.cycle_count}  | "
            f"Score {self.score}/{self.target_score}"
            f"{self._format_found_targets()}\n"
        )

    def _notify_score_milestone(self, latest_target):
        if self.score not in SCORE_NOTIFY_MILESTONES:
            return
        if self.score in self.notified_score_milestones:
            return

        self.notified_score_milestones.add(self.score)
        self.app.notify_discord_result(
            f"Score {self.score} reached",
            (
                f"D{self.slot_index + 1} {self.device_id}\n"
                f"Score: {self.score}/{self.target_score}\n"
                f"Loop: {self.cycle_count}\n"
                f"Latest target: {score_target_short_name(latest_target)}"
                f"{self._format_found_targets()}"
            ),
        )

    def _run(self):
        self.log(f"Score State Flow started. Start at State 1. Target score: {self.target_score}\n", "success")
        self.app.root.after(
            0,
            lambda: self.app._set_device_status(self.slot_index, f"Score 0/{self.target_score}"),
        )

        try:
            while self.running and self.score < self.target_score:
                self.cycle_count += 1
                self.log(
                    f"=== Score Flow Round #{self.cycle_count} | score {self.score}/{self.target_score} ===\n",
                    "success",
                )
                self.log(
                    f"Loop summary: Score Loop #{self.cycle_count} | "
                    f"Score {self.score}/{self.target_score}{self._format_found_targets()}\n",
                    "info",
                )
                self.app.safe_main_log(
                    self._format_score_loop_main_log(),
                    "info",
                )

                self._execute_state("1", STATE_OPEN_FREE_TREASURE)
                if self._should_stop_now():
                    break

                if self.score == 2:
                    self.log("State 1 ended with score 2. Routing to State 3.\n", "info")
                    self._execute_state("3", STATE_OPEN_PETS_15, allow_target_score=True)
                    if self._should_stop_now() or self.score >= self.target_score:
                        break
                    self.log("State 3 ended with score 2. Routing to State 6.\n", "info")
                    self._execute_reset_state()
                    continue

                self.log(f"State 1 ended with score {self.score}. Routing to State 2.\n", "info")
                self._execute_state("2", STATE_OPEN_TREASURE_6_PLUS_1)
                if self._should_stop_now():
                    break

                if self.score == 2:
                    self.log("State 2 ended with score 2. Routing to State 5.\n", "info")
                    self._execute_state("5", STATE_OPEN_PETS_9, allow_target_score=True)
                    if self._should_stop_now() or self.score >= self.target_score:
                        break
                    self.log("State 5 ended with score 2. Routing to State 6.\n", "info")
                    self._execute_reset_state()
                    continue

                self.log(f"State 2 ended with score {self.score}. Routing to State 6.\n", "info")
                self._execute_reset_state()

            if self.score >= self.target_score:
                self.stop_reason = "score_complete"
                self.log(
                    f"Target reached: score is {self.score}/{self.target_score}. Stopping this device.\n",
                    "success",
                )
                self.log(
                    f"Loop summary: Score Loop #{self.cycle_count} complete | "
                    f"Score {self.score}/{self.target_score}{self._format_found_targets()}\n",
                    "success",
                )
                self.app.safe_main_log(
                    f"[D{self.slot_index + 1} {self.device_id}] Score complete | "
                    f"Loop #{self.cycle_count}  | Score {self.score}/{self.target_score}"
                    f"{self._format_found_targets()}\n",
                    "success",
                )
                if self.score not in self.notified_score_milestones:
                    self.app.notify_discord_result(
                        "Score flow complete",
                        (
                            f"D{self.slot_index + 1} {self.device_id}\n"
                            f"Score: {self.score}/{self.target_score}\n"
                            f"Loop: {self.cycle_count}"
                            f"{self._format_found_targets()}"
                        ),
                    )
            elif self.stop_reason == "manual_stop":
                self.log("Score flow stopped by user.\n", "warn")
            else:
                self.log("Score flow stopped.\n", "warn")
        finally:
            self.running = False
            self.app.root.after(0, lambda: self.app._runner_finished(self.slot_index))

    def _execute_reset_state(self):
        if not self.running or self.score >= self.target_score:
            return
        self._execute_state("6", STATE_RESET_ID)
        if self.running and self.score < self.target_score:
            self._reset_score_for_next_account()
            self.log("State 6 complete. Returning to State 1.\n", "warn")

    def _execute_state(self, state_number, group_key, allow_target_score=False):
        group_data = STEP_GROUPS[group_key]
        self.log(f"-- State {state_number}: {group_data['label']} --\n", "info")
        self.app.root.after(
            0,
            lambda s=state_number: self.app._set_device_status(
                self.slot_index,
                f"State {s} | Score {self.score}/{self.target_score}",
            ),
        )
        self._execute_group(group_key, allow_target_score=allow_target_score)

    def _reset_score_for_next_account(self):
        self.score = 0
        self.matched_targets.clear()
        self.matched_target_names.clear()
        self.notified_score_milestones.clear()
        self.app.root.after(
            0,
            lambda: self.app._set_device_status(self.slot_index, f"Score 0/{self.target_score}"),
        )
        self.log(f"Score reset to 0/{self.target_score} for next account.\n", "info")

    def _execute_group(self, group_key, allow_target_score=False):
        group_data = STEP_GROUPS[group_key]
        steps = resolve_group_steps(group_key)
        self.log(f"-- Group: {group_data['label']} ({len(steps)} steps) --\n", "info")
        self._execute_steps(steps, allow_target_score=allow_target_score)

    def _execute_steps(self, steps, allow_target_score=False):
        for i, step in enumerate(steps, 1):
            if not self.running:
                break
            if self.score >= self.target_score and not allow_target_score:
                break

            action = step[0]
            delay = get_runtime_step_delay(step)
            note = step[-1]
            detail = execute_bot_step(self.device_id, step)
            self.log(f"  [{i:02d}/{len(steps)}] [{action}] {note}  {detail}  wait {delay:.1f}s\n", "coord")

            elapsed = 0
            while self.running and elapsed < delay:
                time.sleep(0.1)
                elapsed += 0.1

            if self.running and self.app.should_check_score_image(step):
                self._check_score_image()

    def _check_score_image(self):
        matches = self.app.check_score_images(self.device_id)
        if not matches:
            best = self.app.get_best_score_template()
            if best:
                self.log(
                    f"Score check: no target found. Best {best['name']} part {best['part']} "
                    f"score={best['last_score']:.3f} "
                    f"threshold={best.get('threshold', SCORE_MATCH_THRESHOLD):.2f} "
                    f"scale={best.get('last_scale') or 0:.2f}. "
                    f"Score {self.score}/{self.target_score}.\n",
                    "info",
                )
            else:
                self.log(f"Score check: no target found. Score {self.score}/{self.target_score}.\n", "info")
            return

        for match in matches:
            target = match["name"]
            if target in self.matched_targets:
                self.log(
                    f"Score check: {target} already counted score={match['score']:.3f}. "
                    f"Score {self.score}/{self.target_score}.\n",
                    "info",
                )
                continue

            self.matched_targets.add(target)
            self.matched_target_names.append(target)
            self.score += 1
            self.log(
                f"Score +1: {target} matched score={match['score']:.3f}. "
                f"Total {self.score}/{self.target_score}.\n",
                "success",
            )
            self.app.root.after(
                0,
                lambda score=self.score: self.app._set_device_status(
                    self.slot_index,
                    f"Score {score}/{self.target_score}",
                ),
            )
            self.app.safe_main_log(
                self._format_score_loop_main_log(),
                "success",
            )
            self._notify_score_milestone(target)

            if self.score >= self.target_score and self.score != 2:
                self.running = False
                break

    def _should_stop_now(self):
        return not self.running or (self.score >= self.target_score and self.score != 2)


class PetImageTestRunner:
    def __init__(self, app, device_id, slot_index):
        self.app = app
        self.device_id = device_id
        self.slot_index = slot_index
        self.running = False
        self.thread = None
        self.found_match = None
        self.cycle_count = 0
        self.stop_reason = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_reason = self.stop_reason or "manual_stop"
        self.running = False

    def log(self, text, tag=None):
        self.app.safe_log(f"[D{self.slot_index + 1} {self.device_id}] {text}", tag)

    def _run(self):
        self.log(f"Pet image test started. Target: {PET_TEST_TARGET_STEM}\n", "success")
        self.app.root.after(0, lambda: self.app._set_device_status(self.slot_index, "Test Pet Img"))

        try:
            while self.running:
                self.cycle_count += 1
                self.found_match = None
                self.log(f"=== Pet Image Test Loop #{self.cycle_count} ===\n", "success")
                self.log(f"Loop summary: Pet Image Test Loop #{self.cycle_count} started.\n", "info")
                self.app.safe_main_log(
                    f"[D{self.slot_index + 1} {self.device_id}] Pet Image Test Loop #{self.cycle_count}\n",
                    "info",
                )

                self._execute_state("3", STATE_OPEN_PETS_15, check_pet_image=True)

                if not self.running:
                    break

                if self.found_match:
                    match = self.found_match
                    self.log(
                        f"Pet image matched: {match['name']} score={match['score']:.3f}. "
                        "Stopping pet image test and keeping current account.\n",
                        "success",
                    )
                    self.log(
                        f"Loop summary: Pet Image Test Loop #{self.cycle_count} matched "
                        f"{match['name']} score={match['score']:.3f}.\n",
                        "success",
                    )
                    self.app.notify_discord_result(
                        "Pet image match found",
                        (
                            f"D{self.slot_index + 1} {self.device_id}\n"
                            f"Target: {match['name']} score={match['score']:.3f}\n"
                            f"Loop: {self.cycle_count}"
                        ),
                    )
                    self.stop_reason = "image_match"
                    self.running = False
                    break
                else:
                    self.log(
                        f"Pet image test loop #{self.cycle_count} finished without finding "
                        f"{PET_TEST_TARGET_STEM}. Running State 6 reset.\n",
                        "warn",
                    )

                self._execute_state("6", STATE_RESET_ID, check_pet_image=False)
                if not self.running:
                    break

                self.log(
                    f"Pet image test loop #{self.cycle_count} complete. "
                    "State 6 reset finished. Starting next loop.\n",
                    "success",
                )
                self.log(
                    f"Loop summary: Pet Image Test Loop #{self.cycle_count} complete | reset finished.\n",
                    "success",
                )

            if self.stop_reason == "manual_stop":
                self.log("Pet image test stopped by user.\n", "warn")
            else:
                self.log("Pet image test stopped.\n", "warn")
        finally:
            self.running = False
            self.app.root.after(0, lambda: self.app._runner_finished(self.slot_index))

    def _execute_state(self, state_number, group_key, check_pet_image):
        if not self.running:
            return

        group_data = STEP_GROUPS[group_key]
        self.log(f"-- Test State {state_number}: {group_data['label']} --\n", "info")
        self.app.root.after(
            0,
            lambda s=state_number: self.app._set_device_status(self.slot_index, f"Test State {s}"),
        )
        steps = resolve_group_steps(group_key)
        self.log(f"-- Group: {group_data['label']} ({len(steps)} steps) --\n", "info")
        self._execute_steps(steps, check_pet_image)

    def _execute_steps(self, steps, check_pet_image):
        for i, step in enumerate(steps, 1):
            if not self.running or (check_pet_image and self.found_match):
                break

            action = step[0]
            delay = get_runtime_step_delay(step)
            note = step[-1]
            detail = execute_bot_step(self.device_id, step)
            self.log(f"  [{i:02d}/{len(steps)}] [{action}] {note}  {detail}  wait {delay:.1f}s\n", "coord")

            elapsed = 0
            while self.running and elapsed < delay:
                time.sleep(0.1)
                elapsed += 0.1

            if self.running and check_pet_image and self.app.should_check_pet_test_image(step):
                self.log(f"Pet image check after step: {note}\n", "info")
                self._check_pet_image()

    def _check_pet_image(self):
        match = self.app.check_pet_test_image(self.device_id)
        if match:
            self.found_match = match
            if match.get("parts"):
                part_scores = ", ".join(
                    f"p{part['part']}={part['score']:.3f}"
                    for part in match["parts"]
                )
                self.log(
                    f"Pet image FOUND: {match['name']} parts={match['matched_parts']}/{match['total_parts']} "
                    f"avg_score={match['score']:.3f} avg_threshold={match['threshold']:.2f} "
                    f"min_part=p{match['weakest_part']}:{match['min_part_score']:.3f}. "
                    f"Scores: {part_scores}.\n",
                    "success",
                )
            else:
                self.log(
                    f"Pet image FOUND: {match['name']} part {match['part']} "
                    f"score={match['score']:.3f} threshold={match['threshold']:.2f} "
                    f"scale={match['scale']:.2f}.\n",
                    "success",
                )
            return

        best = self.app.get_best_score_template(PET_TEST_TARGET_STEM)
        if best:
            part_scores = self.app.get_score_template_part_scores(PET_TEST_TARGET_STEM)
            part_detail = f" Parts: {part_scores}." if part_scores else ""
            self.log(
                f"Pet image check: not found. Best {best['name']} part {best['part']} "
                f"score={best['last_score']:.3f} "
                f"threshold={best.get('threshold', SCORE_MATCH_THRESHOLD):.2f} "
                f"scale={best.get('last_scale') or 0:.2f}.{part_detail}\n",
                "info",
            )
        else:
            self.log("Pet image check: not found.\n", "info")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MuMu Bot - Reroll Tool")
        self.root.geometry("1180x760")
        self.root.minsize(1040, 680)
        self.root.resizable(True, True)
        self.root.configure(fg_color=APP_BG)

        self.device_id_vars = []
        self.device_status_vars = []
        self.device_score_target_vars = []
        self.device_score_target_controls = [[] for _ in range(MAX_DEVICE_SLOTS)]
        self.device_score_buttons = [[] for _ in range(MAX_DEVICE_SLOTS)]
        self.device_stop_buttons = [[] for _ in range(MAX_DEVICE_SLOTS)]
        self.runners = [None] * MAX_DEVICE_SLOTS
        self.group_label_to_key = {}
        self.step_label_to_index = {}
        self.select_templates = []
        self.score_templates = []
        self.main_log_widget = None
        self.main_log_entries = []
        self.main_log_filter_var = tk.StringVar(value=MAIN_LOG_FILTER_ALL)
        self.main_log_filter_combo = None
        self.tab_view = None
        self.log_widget = None
        self.debug_log_entries = []
        self.debug_log_filter_var = tk.StringVar(value=MAIN_LOG_FILTER_ALL)
        self.debug_log_filter_combo = None
        discord_webhook_url = read_discord_webhook_url()
        self.discord_webhook_url = discord_webhook_url
        self.discord_webhook_var = tk.StringVar(value=discord_webhook_url)
        self.discord_webhook_status_var = tk.StringVar(
            value="Configured" if discord_webhook_url else "Not configured"
        )
        self.config_step_label_to_index = {}
        self.config_step_var = tk.StringVar()
        self.config_step_action_var = tk.StringVar(value="-")
        self.config_step_note_var = tk.StringVar(value="-")
        self.config_step_x_var = tk.StringVar()
        self.config_step_y_var = tk.StringVar()
        self.config_step_time_var = tk.StringVar()
        self.config_step_text_var = tk.StringVar()
        self.config_step_value_var = tk.StringVar()
        self.config_step_status_var = tk.StringVar(value="Select a step to edit")
        self.config_step_x_entry = None
        self.config_step_y_entry = None
        self.config_step_value_label = None
        self.config_step_value_entry = None
        self.config_step_coord_frame = None
        self.config_step_save_btn = None
        self.config_step_reload_btn = None
        self.config_step_status_label = None
        self.config_step_combo = None
        self.config_step_picker = None
        self.config_step_picker_parent = None
        self.runtime_position_jitter_var = tk.StringVar()
        self.runtime_delay_min_var = tk.StringVar()
        self.runtime_delay_max_var = tk.StringVar()
        self.runtime_config_status_var = tk.StringVar(value="Runtime config ready")
        self.debug_group_picker = None
        self.debug_group_picker_parent = None
        self.debug_step_picker = None
        self.debug_step_picker_parent = None
        self.step_config_overrides = read_step_config_overrides()
        self.runtime_config_overrides = read_runtime_config_overrides()

        for slot in range(MAX_DEVICE_SLOTS):
            default_value = DEFAULT_DEVICE_ID if slot == 0 else ""
            device_var = tk.StringVar(value=default_value)
            status_var = tk.StringVar(value="Ready" if slot == 0 else "Empty")
            score_target_var = tk.StringVar(value=str(DEFAULT_SCORE_TARGET))
            device_var.trace_add("write", lambda *_: self._update_device_controls())
            self.device_id_vars.append(device_var)
            self.device_status_vars.append(status_var)
            self.device_score_target_vars.append(score_target_var)

        loaded_step_overrides = self._load_step_config_overrides()
        loaded_runtime_overrides = self._load_runtime_config_overrides()
        self._build_ui()
        if loaded_step_overrides:
            self._log(f"Loaded {loaded_step_overrides} step config override(s).\n", "info")
        if loaded_runtime_overrides:
            self._log(f"Loaded {loaded_runtime_overrides} runtime random config override(s).\n", "info")

    def _build_ui(self):
        tab_view = ctk.CTkTabview(
            self.root,
            fg_color=APP_BG,
            segmented_button_fg_color=SURFACE_BG,
            segmented_button_selected_color=SURFACE_BG,
            segmented_button_selected_hover_color=SURFACE_ALT_BG,
            segmented_button_unselected_color=SURFACE_BG,
            segmented_button_unselected_hover_color=SURFACE_ALT_BG,
            text_color=TEXT_MUTED_COLOR,
            command=self._on_tab_changed,
            anchor="w",
        )
        self.tab_view = tab_view
        tab_view.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        tab_view.add("Main")
        tab_view.add("Config")
        tab_view.add("Debug")

        main_tab = tab_view.tab("Main")
        config_tab = tab_view.tab("Config")
        debug_tab = tab_view.tab("Debug")

        self._build_main_tab(main_tab)
        self._build_config_tab(config_tab)
        self._build_debug_tab(debug_tab)
        self._style_tab_selector()

        self._log("Application started.\n", "success")
        self._log(f"Default device slot 1: {DEFAULT_DEVICE_ID}\n", "info")
        self._log(f"Bot steps loaded: {len(STEPS)}\n\n", "info")
        self._main_log("Application started.\n", "success")
        self._load_select_templates()
        self._load_score_templates()
        self._update_device_controls()

    def _on_tab_changed(self):
        self._style_tab_selector()

    def _style_tab_selector(self):
        if self.tab_view is None:
            return

        segmented_button = getattr(self.tab_view, "_segmented_button", None)
        if segmented_button is None:
            return

        try:
            segmented_button.grid_configure(sticky=tk.W)
        except tk.TclError:
            return

        try:
            selected_tab = self.tab_view.get()
        except tk.TclError:
            selected_tab = "Main"

        for tab_name, tab_button in getattr(segmented_button, "_buttons_dict", {}).items():
            tab_button.configure(
                fg_color=SURFACE_BG,
                hover_color=SURFACE_ALT_BG,
                text_color=TAB_SELECTED_TEXT_COLOR if tab_name == selected_tab else TEXT_MUTED_COLOR,
            )

    def _section(self, parent, title):
        section = ctk.CTkFrame(
            parent,
            fg_color=SURFACE_BG,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        title_label = ctk.CTkLabel(
            section,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_COLOR,
            anchor="w",
        )
        title_label.pack(fill=tk.X, padx=12, pady=(10, 4))
        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        return section, body

    def _button(self, parent, text, command, width=112, state=tk.NORMAL, danger=False):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=30,
            corner_radius=6,
            fg_color=DANGER_COLOR if danger else ACCENT_COLOR,
            hover_color=DANGER_HOVER_COLOR if danger else ACCENT_HOVER_COLOR,
            text_color=TEXT_COLOR,
            text_color_disabled="#6b7280",
            state=state,
        )

    def _build_main_tab(self, parent):
        main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._build_device_settings(main_frame)

        main_log_section, main_log_frame = self._section(main_frame, "Main Log")
        main_log_section.pack(fill=tk.BOTH, expand=True)

        main_log_filter_frame = ctk.CTkFrame(main_log_frame, fg_color="transparent")
        main_log_filter_frame.pack(fill=tk.X, pady=(0, 5))
        ctk.CTkLabel(
            main_log_filter_frame,
            text="Device:",
            text_color=TEXT_MUTED_COLOR,
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.main_log_filter_combo = ctk.CTkComboBox(
            main_log_filter_frame,
            variable=self.main_log_filter_var,
            values=[MAIN_LOG_FILTER_ALL],
            state="readonly",
            width=280,
            height=30,
            corner_radius=6,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            button_color=SURFACE_ALT_BG,
            button_hover_color=BORDER_COLOR,
            dropdown_fg_color=SURFACE_BG,
            dropdown_hover_color=SURFACE_ALT_BG,
            text_color=TEXT_COLOR,
            dropdown_text_color=TEXT_COLOR,
            command=lambda _choice: self._on_main_log_filter_changed(),
        )
        self.main_log_filter_combo.pack(side=tk.LEFT)

        self.main_log_widget = ctk.CTkTextbox(
            main_log_frame,
            wrap=tk.WORD,
            height=320,
            font=("Consolas", 10),
            fg_color=LOG_BG,
            text_color=TEXT_COLOR,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=ACCENT_COLOR,
        )
        self.main_log_widget.pack(fill=tk.BOTH, expand=True)
        self._configure_log_tags(self.main_log_widget)
        self._update_main_log_filter_options()

    def _build_debug_tab(self, parent):
        main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        coord_section, coord_frame = self._section(main_frame, "Coordinate Picker")
        coord_section.pack(fill=tk.X, pady=(0, 8))

        self.find_pos_btn = self._button(coord_frame, "Find Position", self._on_find_position, width=128)
        self.find_pos_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_pos_btn = self._button(
            coord_frame,
            "Stop Picker",
            self._on_stop_picker,
            width=118,
            state=tk.DISABLED,
            danger=True,
        )
        self.stop_pos_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.capture_once_btn = self._button(coord_frame, "Capture Once", self._on_capture_once, width=128)
        self.capture_once_btn.pack(side=tk.LEFT)

        bot_section, bot_frame = self._section(main_frame, "Bot Control")
        bot_section.pack(fill=tk.X, pady=(0, 8))

        self.bot_info_var = tk.StringVar(value="Ready")
        self.bot_info_lbl = ctk.CTkLabel(
            bot_frame,
            textvariable=self.bot_info_var,
            text_color=TEXT_MUTED_COLOR,
            width=92,
            anchor="w",
        )
        self.bot_info_lbl.pack(side=tk.LEFT, padx=(0, 12))

        self.run_bot_btn = self._button(bot_frame, "Run Full Flow", self._on_run_bot, width=118)
        self.run_bot_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.run_score_btn = self._button(bot_frame, "Run Score Flow", self._on_run_score_flow, width=128)
        self.run_score_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.run_pet_img_test_btn = self._button(
            bot_frame, "Run Test Img pet", self._on_run_pet_img_test, width=132
        )
        self.run_pet_img_test_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_bot_btn = self._button(
            bot_frame, "Stop All", self._on_stop_bot, width=92, state=tk.DISABLED, danger=True
        )
        self.stop_bot_btn.pack(side=tk.LEFT)

        self.loop_var = tk.BooleanVar(value=True)
        self.loop_check = ctk.CTkCheckBox(
            bot_frame,
            text="Loop",
            variable=self.loop_var,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
        )
        self.loop_check.pack(side=tk.RIGHT, padx=(10, 0))

        step_section, step_frame = self._section(main_frame, "Step Control")
        step_section.pack(fill=tk.X, pady=(0, 8))
        self.debug_group_picker_parent = step_frame
        self.debug_step_picker_parent = step_frame
        step_frame.grid_columnconfigure(1, weight=1)

        self.group_label_to_key = {
            f"{data['label']} ({len(resolve_group_steps(key))} steps)": key
            for key, data in STEP_GROUPS.items()
        }
        ctk.CTkLabel(step_frame, text="Group:", text_color=TEXT_MUTED_COLOR).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.group_var = tk.StringVar(value=next(iter(self.group_label_to_key)))
        self.group_combo = ctk.CTkEntry(
            step_frame,
            textvariable=self.group_var,
            state="readonly",
            width=320,
            height=30,
            corner_radius=6,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
        )
        self.group_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 8), pady=4)
        self._button(step_frame, "Select", self._open_debug_group_picker, width=82).grid(
            row=0, column=2, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.run_group_btn = self._button(step_frame, "Run Group", self._on_run_group, width=110)
        self.run_group_btn.grid(row=0, column=3, sticky=tk.W, pady=4)

        self.step_label_to_index = {
            get_step_label(step, index): index - 1
            for index, step in enumerate(STEPS, 1)
        }
        ctk.CTkLabel(step_frame, text="Single Step:", text_color=TEXT_MUTED_COLOR).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.step_var = tk.StringVar(value=next(iter(self.step_label_to_index)))
        self.step_combo = ctk.CTkEntry(
            step_frame,
            textvariable=self.step_var,
            state="readonly",
            width=460,
            height=30,
            corner_radius=6,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
        )
        self.step_combo.grid(row=2, column=1, sticky=tk.EW, padx=(0, 8), pady=4)
        self._button(step_frame, "Select", self._open_debug_step_picker, width=82).grid(
            row=2, column=2, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.run_step_btn = self._button(step_frame, "Run Step", self._on_run_step, width=110)
        self.run_step_btn.grid(row=2, column=3, sticky=tk.W, pady=4)

        log_section, log_frame = self._section(main_frame, "Log")
        log_section.pack(fill=tk.BOTH, expand=True)

        debug_log_filter_frame = ctk.CTkFrame(log_frame, fg_color="transparent")
        debug_log_filter_frame.pack(fill=tk.X, pady=(0, 5))
        ctk.CTkLabel(
            debug_log_filter_frame,
            text="Device:",
            text_color=TEXT_MUTED_COLOR,
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.debug_log_filter_combo = ctk.CTkComboBox(
            debug_log_filter_frame,
            variable=self.debug_log_filter_var,
            values=[MAIN_LOG_FILTER_ALL],
            state="readonly",
            width=280,
            height=30,
            corner_radius=6,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            button_color=SURFACE_ALT_BG,
            button_hover_color=BORDER_COLOR,
            dropdown_fg_color=SURFACE_BG,
            dropdown_hover_color=SURFACE_ALT_BG,
            text_color=TEXT_COLOR,
            dropdown_text_color=TEXT_COLOR,
            command=lambda _choice: self._on_debug_log_filter_changed(),
        )
        self.debug_log_filter_combo.pack(side=tk.LEFT)

        self.log_widget = ctk.CTkTextbox(
            log_frame,
            wrap=tk.WORD,
            height=260,
            font=("Consolas", 10),
            fg_color=LOG_BG,
            text_color=TEXT_COLOR,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=ACCENT_COLOR,
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self._configure_log_tags(self.log_widget)
        self._update_debug_log_filter_options()

    def _build_config_tab(self, parent):
        main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._build_step_config(main_frame)
        self._build_runtime_config(main_frame)
        self._build_notification_settings(main_frame)

    def _build_step_config(self, parent):
        config_section, config_frame = self._section(parent, "Step Config")
        config_section.pack(fill=tk.X, pady=(0, 8))
        self.config_step_picker_parent = config_frame

        self.config_step_label_to_index = {
            get_step_label(step, index): index - 1
            for index, step in enumerate(STEPS, 1)
        }
        first_step_label = next(iter(self.config_step_label_to_index), "")
        self.config_step_var.set(first_step_label)

        ctk.CTkLabel(config_frame, text="Step:", text_color=TEXT_MUTED_COLOR).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.config_step_combo = ctk.CTkEntry(
            config_frame,
            textvariable=self.config_step_var,
            state="readonly",
            width=280,
            height=30,
            corner_radius=6,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
        )
        self.config_step_combo.grid(row=0, column=1, sticky=tk.W, pady=4)
        self._button(config_frame, "Select", self._open_config_step_picker, width=82).grid(
            row=0, column=2, sticky=tk.W, padx=(8, 0), pady=4
        )

        ctk.CTkLabel(config_frame, text="Step Text:", text_color=TEXT_MUTED_COLOR).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        ctk.CTkEntry(
            config_frame,
            textvariable=self.config_step_text_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=280,
            height=30,
            corner_radius=6,
        ).grid(row=2, column=1, sticky=tk.W, pady=4)

        self.config_step_value_label = ctk.CTkLabel(config_frame, text="Text Value:", text_color=TEXT_MUTED_COLOR)
        self.config_step_value_label.grid(
            row=3, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        self.config_step_value_entry = ctk.CTkEntry(
            config_frame,
            textvariable=self.config_step_value_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=280,
            height=30,
            corner_radius=6,
        )
        self.config_step_value_entry.grid(row=3, column=1, sticky=tk.W, pady=4)

        self.config_step_coord_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        self.config_step_coord_frame.grid(row=4, column=1, columnspan=5, sticky=tk.W, pady=4)

        ctk.CTkLabel(self.config_step_coord_frame, text="X:", text_color=TEXT_MUTED_COLOR).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.config_step_x_entry = ctk.CTkEntry(
            self.config_step_coord_frame,
            textvariable=self.config_step_x_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        )
        self.config_step_x_entry.pack(side=tk.LEFT)

        ctk.CTkLabel(self.config_step_coord_frame, text="Y:", text_color=TEXT_MUTED_COLOR).pack(
            side=tk.LEFT, padx=(12, 6)
        )
        self.config_step_y_entry = ctk.CTkEntry(
            self.config_step_coord_frame,
            textvariable=self.config_step_y_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        )
        self.config_step_y_entry.pack(side=tk.LEFT)

        ctk.CTkLabel(self.config_step_coord_frame, text="Time:", text_color=TEXT_MUTED_COLOR).pack(
            side=tk.LEFT, padx=(12, 6)
        )
        ctk.CTkEntry(
            self.config_step_coord_frame,
            textvariable=self.config_step_time_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        ).pack(side=tk.LEFT)

        self.config_step_save_btn = self._button(config_frame, "Save Step", self._on_save_config_step, width=108)
        self.config_step_save_btn.grid(
            row=5, column=1, sticky=tk.W, padx=(0, 8), pady=(8, 0)
        )
        self.config_step_reload_btn = self._button(config_frame, "Reload", self._load_config_step_fields, width=90)
        self.config_step_reload_btn.grid(
            row=5, column=2, sticky=tk.W, pady=(8, 0)
        )
        self.config_step_status_label = ctk.CTkLabel(
            config_frame,
            textvariable=self.config_step_status_var,
            text_color=TEXT_MUTED_COLOR,
            anchor="w",
        )
        self.config_step_status_label.grid(row=5, column=3, columnspan=3, sticky=tk.W, padx=(12, 0), pady=(8, 0))

        self._load_config_step_fields()

    def _build_runtime_config(self, parent):
        runtime_section, runtime_frame = self._section(parent, "Runtime Random")
        runtime_section.pack(fill=tk.X, pady=(0, 8))

        ctk.CTkLabel(runtime_frame, text="Tap jitter +/- px:", text_color=TEXT_MUTED_COLOR).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4
        )
        ctk.CTkEntry(
            runtime_frame,
            textvariable=self.runtime_position_jitter_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 16), pady=4)

        ctk.CTkLabel(runtime_frame, text="Delay random min:", text_color=TEXT_MUTED_COLOR).grid(
            row=0, column=2, sticky=tk.W, padx=(0, 8), pady=4
        )
        ctk.CTkEntry(
            runtime_frame,
            textvariable=self.runtime_delay_min_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        ).grid(row=0, column=3, sticky=tk.W, padx=(0, 16), pady=4)

        ctk.CTkLabel(runtime_frame, text="Delay random max:", text_color=TEXT_MUTED_COLOR).grid(
            row=0, column=4, sticky=tk.W, padx=(0, 8), pady=4
        )
        ctk.CTkEntry(
            runtime_frame,
            textvariable=self.runtime_delay_max_var,
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            width=90,
            height=30,
            corner_radius=6,
        ).grid(row=0, column=5, sticky=tk.W, padx=(0, 16), pady=4)

        self._button(runtime_frame, "Save", self._on_save_runtime_config, width=78).grid(
            row=0, column=6, sticky=tk.W, padx=(0, 6), pady=4
        )
        self._button(runtime_frame, "Reload", self._on_reload_runtime_config, width=82).grid(
            row=0, column=7, sticky=tk.W, padx=(0, 12), pady=4
        )
        ctk.CTkLabel(
            runtime_frame,
            textvariable=self.runtime_config_status_var,
            text_color=TEXT_MUTED_COLOR,
            anchor="w",
        ).grid(row=0, column=8, sticky=tk.W, pady=4)

    def _build_device_settings(self, parent):
        settings_section, settings_frame = self._section(parent, "Device Settings")
        settings_section.pack(fill=tk.X, pady=(0, 8))
        settings_frame.grid_columnconfigure(1, weight=1)

        for slot in range(MAX_DEVICE_SLOTS):
            ctk.CTkLabel(
                settings_frame,
                text=f"Device {slot + 1}:",
                text_color=TEXT_MUTED_COLOR,
                width=70,
                anchor="w",
            ).grid(
                row=slot, column=0, sticky=tk.W, padx=(0, 8), pady=4
            )

            ctk.CTkEntry(
                settings_frame,
                textvariable=self.device_id_vars[slot],
                fg_color=LOG_BG,
                border_color=BORDER_COLOR,
                text_color=TEXT_COLOR,
                height=30,
                corner_radius=6,
            ).grid(
                row=slot, column=1, sticky=tk.EW, padx=(0, 10), pady=4
            )
            ctk.CTkLabel(
                settings_frame,
                textvariable=self.device_status_vars[slot],
                width=130,
                text_color=TEXT_MUTED_COLOR,
                anchor="w",
            ).grid(
                row=slot, column=2, sticky=tk.W, padx=(0, 10), pady=4
            )
            ctk.CTkLabel(settings_frame, text="Target:", text_color=TEXT_MUTED_COLOR).grid(
                row=slot, column=3, sticky=tk.W, padx=(0, 6), pady=4
            )
            score_target_combo = ctk.CTkComboBox(
                settings_frame,
                variable=self.device_score_target_vars[slot],
                values=SCORE_TARGET_CHOICES,
                state="readonly",
                width=64,
                height=30,
                corner_radius=6,
                fg_color=LOG_BG,
                border_color=BORDER_COLOR,
                button_color=SURFACE_ALT_BG,
                button_hover_color=BORDER_COLOR,
                dropdown_fg_color=SURFACE_BG,
                dropdown_hover_color=SURFACE_ALT_BG,
                text_color=TEXT_COLOR,
                dropdown_text_color=TEXT_COLOR,
            )
            score_target_combo.grid(row=slot, column=4, sticky=tk.W, padx=(0, 10), pady=4)
            score_btn = self._button(
                settings_frame,
                "Run Score",
                lambda slot_index=slot: self._on_run_score_for_slot(slot_index),
                width=100,
            )
            score_btn.grid(row=slot, column=5, sticky=tk.W, padx=(0, 6), pady=4)
            stop_btn = self._button(
                settings_frame,
                "Stop",
                lambda slot_index=slot: self._on_stop_slot(slot_index),
                width=72,
                state=tk.DISABLED,
                danger=True,
            )
            stop_btn.grid(row=slot, column=6, sticky=tk.W, padx=(0, 12), pady=4)
            self.device_score_target_controls[slot].append(score_target_combo)
            self.device_score_buttons[slot].append(score_btn)
            self.device_stop_buttons[slot].append(stop_btn)

        self._button(settings_frame, "Reset ADB & Find", self._on_reset_adb, width=148).grid(
            row=0, column=7, sticky=tk.EW, padx=(0, 0), pady=4
        )
        self._button(settings_frame, "List Devices", self._on_list_devices, width=148).grid(
            row=1, column=7, sticky=tk.EW, padx=(0, 0), pady=4
        )
        self._button(settings_frame, "Fill Found Devices", self._on_fill_devices, width=148).grid(
            row=2, column=7, sticky=tk.EW, padx=(0, 0), pady=4
        )

    def _toggle_inline_picker(self, picker_attr, parent, row, column, columnspan, width, labels, on_select):
        picker = getattr(self, picker_attr)
        if picker is not None and picker.winfo_exists():
            picker.destroy()
            setattr(self, picker_attr, None)
            return

        picker = ctk.CTkScrollableFrame(
            parent,
            fg_color=SURFACE_BG,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            width=width,
            height=300,
        )
        setattr(self, picker_attr, picker)
        picker.grid(row=row, column=column, columnspan=columnspan, sticky=tk.W, pady=(2, 8))

        def close_picker():
            if picker is not None and picker.winfo_exists():
                picker.destroy()
            setattr(self, picker_attr, None)

        for label in labels:
            ctk.CTkButton(
                picker,
                text=label,
                command=lambda selected=label: (on_select(selected), close_picker()),
                height=30,
                corner_radius=4,
                fg_color="transparent",
                hover_color=SURFACE_ALT_BG,
                text_color=TEXT_COLOR,
                anchor="w",
            ).pack(fill=tk.X, padx=4, pady=1)

    def _open_debug_group_picker(self):
        self._toggle_inline_picker(
            "debug_group_picker",
            self.debug_group_picker_parent,
            1,
            1,
            3,
            520,
            list(self.group_label_to_key.keys()),
            self.group_var.set,
        )

    def _open_debug_step_picker(self):
        self._toggle_inline_picker(
            "debug_step_picker",
            self.debug_step_picker_parent,
            3,
            1,
            3,
            520,
            list(self.step_label_to_index.keys()),
            self.step_var.set,
        )

    def _open_config_step_picker(self):
        self._toggle_inline_picker(
            "config_step_picker",
            self.config_step_picker_parent,
            1,
            1,
            3,
            520,
            list(self.config_step_label_to_index.keys()),
            self._select_config_step,
        )

    def _close_config_step_picker(self):
        if self.config_step_picker is not None and self.config_step_picker.winfo_exists():
            self.config_step_picker.destroy()
        self.config_step_picker = None

    def _select_config_step(self, selected_label):
        self.config_step_var.set(selected_label)
        self._load_config_step_fields()
        self._close_config_step_picker()

    def _load_step_config_overrides(self):
        loaded = 0
        for raw_index, config in self.step_config_overrides.items():
            if not isinstance(config, dict):
                continue
            try:
                step_index = int(raw_index)
            except ValueError:
                continue
            if step_index < 0 or step_index >= len(STEPS):
                continue

            step = STEPS[step_index]
            action = step[0]
            try:
                delay = float(config.get("time", step[-2]))
            except (TypeError, ValueError):
                continue
            if delay < 0:
                continue

            note = str(config.get("note", step[-1]))
            if action == "tap":
                try:
                    x = int(config.get("x", step[1]))
                    y = int(config.get("y", step[2]))
                except (TypeError, ValueError):
                    continue
                if x < 0 or y < 0:
                    continue
                new_step = ("tap", x, y, delay, note)
            elif action == "text":
                text_value = str(config.get("value", step[1]))
                new_step = ("text", text_value, delay, note)
            elif action == "keyevent":
                new_step = ("keyevent", step[1], delay, note)
            else:
                continue

            self._replace_step_everywhere(step_index, new_step)
            loaded += 1
        return loaded

    def _set_runtime_config_fields(self):
        self.runtime_position_jitter_var.set(str(Bot.TAP_POSITION_JITTER))
        self.runtime_delay_min_var.set(f"{Bot.DELAY_EXTRA_SECONDS_MIN:g}")
        self.runtime_delay_max_var.set(f"{Bot.DELAY_EXTRA_SECONDS_MAX:g}")

    def _load_runtime_config_overrides(self):
        position_jitter = DEFAULT_RUNTIME_TAP_POSITION_JITTER
        delay_min = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MIN
        delay_max = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MAX
        loaded = 0

        try:
            if "tap_position_jitter" in self.runtime_config_overrides:
                position_jitter = int(self.runtime_config_overrides["tap_position_jitter"])
                loaded += 1
            if "delay_extra_seconds_min" in self.runtime_config_overrides:
                delay_min = float(self.runtime_config_overrides["delay_extra_seconds_min"])
                loaded += 1
            if "delay_extra_seconds_max" in self.runtime_config_overrides:
                delay_max = float(self.runtime_config_overrides["delay_extra_seconds_max"])
                loaded += 1
        except (TypeError, ValueError):
            position_jitter = DEFAULT_RUNTIME_TAP_POSITION_JITTER
            delay_min = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MIN
            delay_max = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MAX
            loaded = 0

        if position_jitter < 0:
            position_jitter = DEFAULT_RUNTIME_TAP_POSITION_JITTER
            loaded = 0
        if delay_min < 0 or delay_max < 0 or delay_max < delay_min:
            delay_min = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MIN
            delay_max = DEFAULT_RUNTIME_DELAY_EXTRA_SECONDS_MAX
            loaded = 0

        apply_runtime_config_values(position_jitter, delay_min, delay_max)
        self._set_runtime_config_fields()
        return loaded

    def _parse_runtime_config_fields(self):
        try:
            position_jitter = int(self.runtime_position_jitter_var.get().strip())
        except ValueError:
            raise ValueError("Tap jitter must be an integer.")

        try:
            delay_min = float(self.runtime_delay_min_var.get().strip())
            delay_max = float(self.runtime_delay_max_var.get().strip())
        except ValueError:
            raise ValueError("Delay random min/max must be numbers.")

        if position_jitter < 0:
            raise ValueError("Tap jitter must be 0 or more.")
        if delay_min < 0 or delay_max < 0:
            raise ValueError("Delay random min/max must be 0 or more.")
        if delay_max < delay_min:
            raise ValueError("Delay random max must be greater than or equal to min.")

        return position_jitter, delay_min, delay_max

    def _on_save_runtime_config(self):
        try:
            position_jitter, delay_min, delay_max = self._parse_runtime_config_fields()
        except ValueError as exc:
            self.runtime_config_status_var.set("Invalid value")
            self._log(f"Runtime random config was not saved: {exc}\n", "error")
            return

        apply_runtime_config_values(position_jitter, delay_min, delay_max)
        runtime_config = {
            "tap_position_jitter": position_jitter,
            "delay_extra_seconds_min": delay_min,
            "delay_extra_seconds_max": delay_max,
        }
        try:
            write_runtime_config_overrides(runtime_config)
        except OSError as exc:
            self.runtime_config_status_var.set("Save failed")
            self._log(f"Runtime random config save failed: {exc}\n", "error")
            return

        self.runtime_config_overrides = runtime_config
        self._set_runtime_config_fields()
        self.runtime_config_status_var.set("Saved")
        self._log(
            f"Runtime random config saved: tap jitter +/-{position_jitter}px, "
            f"delay +{delay_min:g}-{delay_max:g}s.\n",
            "success",
        )

    def _on_reload_runtime_config(self):
        self.runtime_config_overrides = read_runtime_config_overrides()
        loaded = self._load_runtime_config_overrides()
        self.runtime_config_status_var.set("Reloaded" if loaded else "Defaults")
        self._log(
            f"Runtime random config reloaded: tap jitter +/-{Bot.TAP_POSITION_JITTER}px, "
            f"delay +{Bot.DELAY_EXTRA_SECONDS_MIN:g}-{Bot.DELAY_EXTRA_SECONDS_MAX:g}s.\n",
            "info",
        )

    def _selected_config_step_index(self):
        return self.config_step_label_to_index.get(self.config_step_var.get())

    def _set_config_text_value_visible(self, visible):
        coord_row = 4 if visible else 3
        button_row = coord_row + 1

        if self.config_step_value_label is not None:
            if visible:
                self.config_step_value_label.grid()
            else:
                self.config_step_value_label.grid_remove()
        if self.config_step_value_entry is not None:
            if visible:
                self.config_step_value_entry.grid()
            else:
                self.config_step_value_entry.grid_remove()
        if self.config_step_coord_frame is not None:
            self.config_step_coord_frame.grid_configure(row=coord_row)
        if self.config_step_save_btn is not None:
            self.config_step_save_btn.grid_configure(row=button_row)
        if self.config_step_reload_btn is not None:
            self.config_step_reload_btn.grid_configure(row=button_row)
        if self.config_step_status_label is not None:
            self.config_step_status_label.grid_configure(row=button_row)

    def _load_config_step_fields(self):
        step_index = self._selected_config_step_index()
        if step_index is None:
            self.config_step_action_var.set("-")
            self.config_step_note_var.set("-")
            self.config_step_x_var.set("")
            self.config_step_y_var.set("")
            self.config_step_time_var.set("")
            self.config_step_text_var.set("")
            self.config_step_value_var.set("")
            self._set_config_text_value_visible(False)
            self.config_step_status_var.set("Select a step to edit")
            return

        step = STEPS[step_index]
        action = step[0]
        self.config_step_action_var.set(action)
        self.config_step_note_var.set(step[-1])
        self.config_step_time_var.set(str(float(step[-2])))
        self.config_step_text_var.set(step[-1])

        x_y_state = tk.NORMAL if action == "tap" else tk.DISABLED
        value_state = tk.NORMAL if action == "text" else tk.DISABLED
        self._set_config_text_value_visible(action == "text")
        if action == "tap":
            self.config_step_x_var.set(str(step[1]))
            self.config_step_y_var.set(str(step[2]))
        else:
            self.config_step_x_var.set("")
            self.config_step_y_var.set("")

        if action == "text":
            self.config_step_value_var.set(str(step[1]))
        else:
            self.config_step_value_var.set("")

        if self.config_step_x_entry is not None:
            self.config_step_x_entry.configure(state=x_y_state)
        if self.config_step_y_entry is not None:
            self.config_step_y_entry.configure(state=x_y_state)
        if self.config_step_value_entry is not None:
            self.config_step_value_entry.configure(state=value_state)
        self.config_step_status_var.set(f"Loaded step {step_index + 1}")

    def _replace_step_everywhere(self, step_index, new_step):
        old_step = STEPS[step_index]
        STEPS[step_index] = new_step
        for group in STEP_GROUPS.values():
            group_steps = group.get("steps")
            if not group_steps:
                continue
            for index, step in enumerate(group_steps):
                if step is old_step:
                    group_steps[index] = new_step

    def _refresh_step_selectors(self, selected_step_index):
        self.config_step_label_to_index = {
            get_step_label(step, index): index - 1
            for index, step in enumerate(STEPS, 1)
        }
        selected_config_label = get_step_label(STEPS[selected_step_index], selected_step_index + 1)
        self.config_step_var.set(selected_config_label)

        self.step_label_to_index = {
            get_step_label(step, index): index - 1
            for index, step in enumerate(STEPS, 1)
        }
        step_combo = getattr(self, "step_combo", None)
        if step_combo is not None:
            self.step_var.set(selected_config_label)

    def _on_save_config_step(self):
        step_index = self._selected_config_step_index()
        if step_index is None:
            self.config_step_status_var.set("No step selected")
            return

        step = STEPS[step_index]
        action = step[0]
        note = self.config_step_text_var.get().strip()
        if not note:
            self.config_step_status_var.set("Step Text is required")
            return

        try:
            delay = float(self.config_step_time_var.get().strip())
        except ValueError:
            self.config_step_status_var.set("Time must be a number")
            return
        if delay < 0:
            self.config_step_status_var.set("Time must be >= 0")
            return

        if action == "tap":
            try:
                x = int(self.config_step_x_var.get().strip())
                y = int(self.config_step_y_var.get().strip())
            except ValueError:
                self.config_step_status_var.set("X and Y must be integers")
                return
            if x < 0 or y < 0:
                self.config_step_status_var.set("X and Y must be >= 0")
                return
            new_step = ("tap", x, y, delay, note)
        elif action == "text":
            text_value = self.config_step_value_var.get()
            if not text_value:
                self.config_step_status_var.set("Text Value is required")
                return
            new_step = ("text", text_value, delay, note)
        elif action == "keyevent":
            new_step = ("keyevent", step[1], delay, note)
        else:
            self.config_step_status_var.set(f"Unsupported action: {action}")
            return

        self._replace_step_everywhere(step_index, new_step)
        self._refresh_step_selectors(step_index)
        step_config = {"time": delay, "note": note}
        if action == "tap":
            step_config["x"] = x
            step_config["y"] = y
        elif action == "text":
            step_config["value"] = text_value
        self.step_config_overrides[str(step_index)] = step_config
        try:
            write_step_config_overrides(self.step_config_overrides)
        except OSError as exc:
            self.config_step_status_var.set("Saved in memory; file save failed")
            self._log(f"Step config file save failed: {exc}\n", "error")
            return

        self.config_step_status_var.set(f"Saved step {step_index + 1}")
        self._log(f"Config updated step {step_index + 1}: {get_step_label(new_step)}\n", "success")

    def _build_notification_settings(self, parent):
        notification_section, notification_frame = self._section(parent, "Notifications")
        notification_section.pack(fill=tk.X, pady=(0, 8))
        notification_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            notification_frame,
            text="Discord Webhook:",
            text_color=TEXT_MUTED_COLOR,
            anchor="w",
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)

        ctk.CTkEntry(
            notification_frame,
            textvariable=self.discord_webhook_var,
            placeholder_text="Paste Discord webhook URL",
            fg_color=LOG_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_COLOR,
            height=30,
            corner_radius=6,
        ).grid(row=0, column=1, sticky=tk.EW, padx=(0, 8), pady=4)

        self._button(
            notification_frame,
            "Save",
            self._on_save_discord_webhook,
            width=78,
        ).grid(row=0, column=2, sticky=tk.W, padx=(0, 6), pady=4)

        self._button(
            notification_frame,
            "Test",
            self._on_test_discord_webhook,
            width=78,
        ).grid(row=0, column=3, sticky=tk.W, padx=(0, 8), pady=4)

        ctk.CTkLabel(
            notification_frame,
            textvariable=self.discord_webhook_status_var,
            text_color=TEXT_MUTED_COLOR,
            anchor="w",
            width=110,
        ).grid(row=0, column=4, sticky=tk.W, pady=4)

    def _text_widget(self, widget):
        return getattr(widget, "_textbox", widget)

    def _configure_log_tags(self, widget):
        text_widget = self._text_widget(widget)
        text_widget.configure(
            bg=LOG_BG,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            selectbackground=BORDER_COLOR,
            relief="flat",
            borderwidth=0,
        )
        text_widget.tag_config("info", foreground="#4ec9b0")
        text_widget.tag_config("coord", foreground="#60a5fa")
        text_widget.tag_config("error", foreground="#f87171")
        text_widget.tag_config("success", foreground="#22c55e")
        text_widget.tag_config("warn", foreground="#facc15")

    def _insert_log_text(self, widget, text, tag=None):
        text_widget = self._text_widget(widget)
        if tag is None:
            text_widget.insert(tk.END, text)
        else:
            text_widget.insert(tk.END, text, tag)
        text_widget.see(tk.END)

    def _delete_log_text(self, widget):
        self._text_widget(widget).delete("1.0", tk.END)

    def _log(self, text, tag=None):
        if self.log_widget is None:
            return
        device_key, device_label = self._parse_main_log_device(text)
        self.debug_log_entries.append({
            "text": text,
            "tag": tag,
            "device_key": device_key,
            "device_label": device_label,
        })
        self._update_debug_log_filter_options(render_on_change=False)
        self._render_debug_log()

    def safe_log(self, text, tag=None):
        self.root.after(0, lambda: self._log(text, tag))

    def _parse_main_log_device(self, text):
        if not text.startswith("[D"):
            return None, None

        close_index = text.find("]")
        if close_index == -1:
            return None, None

        device_label = text[1:close_index].strip()
        if not device_label:
            return None, None

        device_key = device_label.split(maxsplit=1)[0]
        if len(device_key) < 2 or device_key[0] != "D" or not device_key[1:].isdigit():
            return None, None

        return device_key, device_label

    def _selected_main_log_device_key(self):
        selected = self.main_log_filter_var.get()
        if selected == MAIN_LOG_FILTER_ALL:
            return None
        return selected.split(maxsplit=1)[0]

    def _main_log_entry_visible(self, entry):
        selected_key = self._selected_main_log_device_key()
        return selected_key is None or entry["device_key"] == selected_key

    def _main_log_filter_label(self, device_key):
        slot_index = int(device_key[1:]) - 1
        if 0 <= slot_index < len(self.device_id_vars):
            device_id = self.device_id_vars[slot_index].get().strip()
            if device_id:
                return f"{device_key} {device_id}"
        return device_key

    def _selected_debug_log_device_key(self):
        selected = self.debug_log_filter_var.get()
        if selected == MAIN_LOG_FILTER_ALL:
            return None
        return selected.split(maxsplit=1)[0]

    def _debug_log_entry_visible(self, entry):
        selected_key = self._selected_debug_log_device_key()
        return selected_key is None or entry["device_key"] == selected_key

    def _update_debug_log_filter_options(self, render_on_change=True):
        if self.debug_log_filter_combo is None:
            return

        previous = self.debug_log_filter_var.get()
        selected_key = self._selected_debug_log_device_key()
        values = [MAIN_LOG_FILTER_ALL]
        seen_keys = set()

        for slot_index, device_var in enumerate(self.device_id_vars):
            device_id = device_var.get().strip()
            if not device_id:
                continue
            device_key = f"D{slot_index + 1}"
            values.append(f"{device_key} {device_id}")
            seen_keys.add(device_key)

        for entry in self.debug_log_entries:
            device_key = entry["device_key"]
            if not device_key or device_key in seen_keys:
                continue
            values.append(entry["device_label"] or self._main_log_filter_label(device_key))
            seen_keys.add(device_key)

        self.debug_log_filter_combo.configure(values=values)
        if selected_key is None:
            self.debug_log_filter_var.set(MAIN_LOG_FILTER_ALL)
        else:
            selected_value = next(
                (value for value in values if value.split(maxsplit=1)[0] == selected_key),
                MAIN_LOG_FILTER_ALL,
            )
            self.debug_log_filter_var.set(selected_value)

        if render_on_change and self.debug_log_filter_var.get() != previous:
            self._render_debug_log()

    def _on_debug_log_filter_changed(self, _event=None):
        self._render_debug_log()

    def _render_debug_log(self):
        if self.log_widget is None:
            return
        self._delete_log_text(self.log_widget)
        for entry in self.debug_log_entries:
            if self._debug_log_entry_visible(entry):
                self._insert_log_text(self.log_widget, entry["text"], entry["tag"])

    def _update_main_log_filter_options(self, render_on_change=True):
        if self.main_log_filter_combo is None:
            return

        previous = self.main_log_filter_var.get()
        selected_key = self._selected_main_log_device_key()
        values = [MAIN_LOG_FILTER_ALL]
        seen_keys = set()

        for slot_index, device_var in enumerate(self.device_id_vars):
            device_id = device_var.get().strip()
            if not device_id:
                continue
            device_key = f"D{slot_index + 1}"
            values.append(f"{device_key} {device_id}")
            seen_keys.add(device_key)

        for entry in self.main_log_entries:
            device_key = entry["device_key"]
            if not device_key or device_key in seen_keys:
                continue
            values.append(entry["device_label"] or self._main_log_filter_label(device_key))
            seen_keys.add(device_key)

        self.main_log_filter_combo.configure(values=values)
        if selected_key is None:
            self.main_log_filter_var.set(MAIN_LOG_FILTER_ALL)
        else:
            selected_value = next(
                (value for value in values if value.split(maxsplit=1)[0] == selected_key),
                MAIN_LOG_FILTER_ALL,
            )
            self.main_log_filter_var.set(selected_value)

        if render_on_change and self.main_log_filter_var.get() != previous:
            self._render_main_log()

    def _on_main_log_filter_changed(self, _event=None):
        self._render_main_log()

    def _render_main_log(self):
        if self.main_log_widget is None:
            return
        self._delete_log_text(self.main_log_widget)
        for entry in self.main_log_entries:
            if self._main_log_entry_visible(entry):
                self._insert_log_text(self.main_log_widget, entry["text"], entry["tag"])

    def _main_log(self, text, tag=None):
        if self.main_log_widget is None:
            return
        device_key, device_label = self._parse_main_log_device(text)
        self.main_log_entries.append({
            "text": text,
            "tag": tag,
            "device_key": device_key,
            "device_label": device_label,
        })
        self._update_main_log_filter_options(render_on_change=False)
        self._render_main_log()

    def safe_main_log(self, text, tag=None):
        self.root.after(0, lambda: self._main_log(text, tag))

    def _discord_webhook_url(self):
        return self.discord_webhook_var.get().strip()

    def _on_save_discord_webhook(self):
        url = self._discord_webhook_url()
        if url and not is_valid_discord_webhook_url(url):
            self.discord_webhook_status_var.set("Invalid URL")
            self._log("Discord webhook was not saved: invalid webhook URL.\n", "error")
            return

        try:
            write_discord_webhook_url(url)
        except OSError as exc:
            self.discord_webhook_status_var.set("Save failed")
            self._log(f"Discord webhook save failed: {exc}\n", "error")
            return

        if url:
            self.discord_webhook_url = url
            self.discord_webhook_status_var.set("Configured")
            self._log("Discord webhook saved.\n", "success")
        else:
            self.discord_webhook_url = ""
            self.discord_webhook_status_var.set("Not configured")
            self._log("Discord webhook cleared.\n", "info")

    def _on_test_discord_webhook(self):
        url = self._discord_webhook_url()
        if not url:
            self.discord_webhook_status_var.set("Not configured")
            self._log("Discord webhook test skipped: paste a webhook URL first.\n", "warn")
            return
        if not is_valid_discord_webhook_url(url):
            self.discord_webhook_status_var.set("Invalid URL")
            self._log("Discord webhook test skipped: invalid webhook URL.\n", "error")
            return

        self.discord_webhook_status_var.set("Testing...")
        self._send_discord_webhook_async(url, "MuMu Reroll Bot webhook test.", log_success=True)

    def notify_discord_result(self, title, detail):
        url = self.discord_webhook_url
        if not url:
            return
        if not is_valid_discord_webhook_url(url):
            self.safe_log("Discord notification skipped: invalid webhook URL.\n", "error")
            self.root.after(0, lambda: self.discord_webhook_status_var.set("Invalid URL"))
            return

        content = f"**{title}**\n{detail}"
        self._send_discord_webhook_async(url, content, log_success=False)

    def _send_discord_webhook_async(self, url, content, log_success):
        content = content[:1900]

        def worker():
            try:
                status = post_discord_webhook(url, content)
            except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                self.safe_log(f"Discord webhook failed: {exc}\n", "warn")
                self.root.after(0, lambda: self.discord_webhook_status_var.set("Send failed"))
                return

            if 200 <= status < 300:
                if log_success:
                    self.safe_log("Discord webhook test sent.\n", "success")
                self.root.after(0, lambda: self.discord_webhook_status_var.set("Last send OK"))
            else:
                self.safe_log(f"Discord webhook returned HTTP {status}.\n", "warn")
                self.root.after(0, lambda: self.discord_webhook_status_var.set("Send failed"))

        threading.Thread(target=worker, daemon=True).start()

    def _load_select_templates(self):
        self.select_templates = load_select_templates()
        if self.select_templates:
            names = ", ".join(template["name"] for template in self.select_templates)
            self._log(f"Image select templates loaded: {names}\n\n", "success")
        else:
            self._log(f"No image select templates found in: {IMAGE_SELECT_DIR}\n\n", "warn")

    def _load_score_templates(self):
        self.score_templates = load_score_templates()
        if self.score_templates:
            names = ", ".join(sorted({template["name"] for template in self.score_templates}))
            self._log(f"Score templates loaded: {names}\n\n", "success")
        else:
            self._log("No score templates found. Check Image_Select/*/Definitions.\n\n", "warn")

    def should_check_select_image(self, step):
        return step[0] == "tap" and step[-1].startswith(OPEN_BOX_STEP_PREFIX)

    def should_check_score_image(self, step):
        return step[0] == "tap" and step[-1].startswith(SCORE_CHECK_STEP_PREFIXES)

    def should_check_pet_test_image(self, step):
        return step[0] == "tap" and step[-1].startswith("Press Hatch 20 Gem")

    def check_select_image(self, device_id):
        if not self.select_templates:
            return None
        screen = screencap(device_id)
        if screen is None:
            self.safe_log(f"[{device_id}] Image check failed: screenshot capture returned empty.\n", "error")
            return None
        return find_select_template_match(screen, self.select_templates)

    def check_score_images(self, device_id):
        if not self.score_templates:
            return []
        for attempt in range(1, SCORE_CHECK_ATTEMPTS + 1):
            screen = screencap(device_id)
            if screen is None:
                self.safe_log(f"[{device_id}] Score check failed: screenshot capture returned empty.\n", "error")
                return []
            matches = find_score_template_matches(screen, self.score_templates)
            if matches or attempt == SCORE_CHECK_ATTEMPTS:
                return matches
            time.sleep(SCORE_CHECK_RETRY_DELAY)
        return []

    def check_pet_test_image(self, device_id):
        pet_templates = [
            template for template in self.score_templates
            if template["name"] == PET_TEST_TARGET_STEM
        ]
        if not pet_templates:
            self.safe_log(f"[{device_id}] Pet image check failed: template not loaded.\n", "error")
            return None

        for attempt in range(1, PET_CHECK_ATTEMPTS + 1):
            screen = screencap(device_id)
            if screen is None:
                self.safe_log(f"[{device_id}] Pet image check failed: screenshot capture returned empty.\n", "error")
                return None

            matches = find_score_template_matches(screen, pet_templates)
            if matches:
                return matches[0]

            if attempt < PET_CHECK_ATTEMPTS:
                time.sleep(SCORE_CHECK_RETRY_DELAY)
        return None

    def get_best_score_template(self, target_name=None):
        scored_templates = [
            template for template in self.score_templates
            if template.get("last_score") is not None
            and (target_name is None or template["name"] == target_name)
        ]
        if not scored_templates:
            return None
        return max(scored_templates, key=lambda template: template["last_score"])

    def get_score_template_part_scores(self, target_name):
        scored_templates = [
            template for template in self.score_templates
            if template["name"] == target_name and template.get("last_score") is not None
        ]
        scored_templates.sort(key=lambda template: template.get("part") or 0)
        return ", ".join(
            f"p{template['part']}={template['last_score']:.3f}/"
            f"{template.get('threshold', SCORE_MATCH_THRESHOLD):.2f}"
            for template in scored_templates
        )

    def _get_device_ids(self):
        device_ids = []
        seen = set()
        for device_var in self.device_id_vars:
            device_id = device_var.get().strip()
            if not device_id:
                continue
            if device_id in seen:
                self._log(f"Duplicate device ignored: {device_id}\n", "warn")
                continue
            seen.add(device_id)
            device_ids.append(device_id)
        return device_ids

    def _find_device_slot(self, device_id):
        for index, device_var in enumerate(self.device_id_vars):
            if device_var.get().strip() == device_id:
                return index
        return None

    def _set_device_status(self, slot_index, status):
        self.device_status_vars[slot_index].set(status)

    def _set_start_buttons_state(self, state):
        self.run_bot_btn.configure(state=state)
        self.run_score_btn.configure(state=state)
        self.run_pet_img_test_btn.configure(state=state)
        self.run_group_btn.configure(state=state)
        self.run_step_btn.configure(state=state)

    def _slot_has_device(self, slot_index):
        return bool(self.device_id_vars[slot_index].get().strip())

    def _slot_is_running(self, slot_index):
        runner = self.runners[slot_index]
        return bool(runner and runner.running)

    def _get_score_target_for_slot(self, slot_index):
        raw_value = self.device_score_target_vars[slot_index].get().strip()
        try:
            target_score = int(raw_value)
        except ValueError:
            target_score = DEFAULT_SCORE_TARGET

        if str(target_score) not in SCORE_TARGET_CHOICES:
            target_score = DEFAULT_SCORE_TARGET
            self.device_score_target_vars[slot_index].set(str(target_score))
        return target_score

    def _update_device_controls(self):
        for slot_index in range(MAX_DEVICE_SLOTS):
            has_device = self._slot_has_device(slot_index)
            is_running = self._slot_is_running(slot_index)
            score_state = tk.NORMAL if has_device and not is_running else tk.DISABLED
            score_target_state = "readonly" if has_device and not is_running else tk.DISABLED
            stop_state = tk.NORMAL if is_running else tk.DISABLED
            for control in self.device_score_target_controls[slot_index]:
                control.configure(state=score_target_state)
            for button in self.device_score_buttons[slot_index]:
                button.configure(state=score_state)
            for button in self.device_stop_buttons[slot_index]:
                button.configure(state=stop_state)
        self._update_main_log_filter_options()
        self._update_debug_log_filter_options()

    def _update_global_controls(self):
        any_running = any(runner and runner.running for runner in self.runners)
        self._set_start_buttons_state(tk.DISABLED if any_running else tk.NORMAL)
        self.stop_bot_btn.configure(state=tk.NORMAL if any_running else tk.DISABLED)
        self.bot_info_var.set("Running..." if any_running else "Stopped")
        self.bot_info_lbl.configure(text_color=SUCCESS_COLOR if any_running else DANGER_COLOR)
        self._update_device_controls()

    def _read_adb_devices(self):
        result = run_hidden(["adb", "devices"], capture_output=True, text=True)
        output = result.stdout.strip()
        lines = output.splitlines()
        devices = [l.split()[0] for l in lines[1:] if l.strip() and "\tdevice" in l]
        return output, devices

    def _fill_device_slots(self, devices):
        for index, device_var in enumerate(self.device_id_vars):
            device_var.set(devices[index] if index < len(devices) else "")
            self.device_status_vars[index].set("Ready" if index < len(devices) else "Empty")
        self._update_device_controls()

    def _on_reset_adb(self):
        self._log("=== Reset ADB & Find Devices ===\n", "info")

        self._log("[1/3] adb kill-server...\n", "warn")
        run_hidden(["adb", "kill-server"], capture_output=True)
        self._log("      done.\n\n", "success")

        self._log("[2/3] adb start-server...\n", "info")
        result = run_hidden(["adb", "start-server"], capture_output=True, text=True)
        self._log(f"      {result.stdout.strip()}\n\n", "success")

        self._log("[3/3] adb devices\n", "info")
        output, devices = self._read_adb_devices()
        self._log(f"{output}\n\n", "info")

        if devices:
            self._log(f"Found devices: {', '.join(devices)}\n", "success")
            self._fill_device_slots(devices[:MAX_DEVICE_SLOTS])
        else:
            self._log("No devices found. Check emulator is running.\n", "error")
        self._log(f"{'=' * 50}\n\n", "info")

    def _on_list_devices(self):
        self._log("Running: adb devices...\n", "info")
        try:
            output, devices = self._read_adb_devices()
            self._log(f"{output}\n\n", "info")
            if devices:
                self._log(f"Found devices: {', '.join(devices)}\n", "success")
            else:
                self._log("No devices found. Check your connection.\n", "error")
        except FileNotFoundError:
            self._log("Error: adb not found. Make sure adb is in your PATH.\n", "error")

    def _on_fill_devices(self):
        self._log("Finding devices to fill slots...\n", "info")
        try:
            output, devices = self._read_adb_devices()
            self._log(f"{output}\n\n", "info")
            if not devices:
                self._log("No devices found. Nothing to fill.\n", "error")
                return
            self._fill_device_slots(devices[:MAX_DEVICE_SLOTS])
            self._log(f"Filled {min(len(devices), MAX_DEVICE_SLOTS)} device slot(s).\n", "success")
            if len(devices) > MAX_DEVICE_SLOTS:
                self._log(f"Only first {MAX_DEVICE_SLOTS} devices were filled.\n", "warn")
        except FileNotFoundError:
            self._log("Error: adb not found. Make sure adb is in your PATH.\n", "error")

    def _on_find_position(self):
        global _coord_window_running, _coord_thread

        device_ids = self._get_device_ids()
        if not device_ids:
            self._log("Error: Device ID is empty.\n", "error")
            return
        device_id = device_ids[0]

        self._log(f"Starting live coordinate picker for: {device_id}\n", "info")
        self._log("Controls: Left-click=coords | Right-click=tap | SPACE=pause | q=quit\n", "info")
        self._log("-" * 50 + "\n", "info")

        self.find_pos_btn.configure(state=tk.DISABLED)
        self.stop_pos_btn.configure(state=tk.NORMAL)

        _coord_window_running = True
        _coord_thread = threading.Thread(target=self._run_coord_picker, args=(device_id,), daemon=True)
        _coord_thread.start()

    def _on_stop_picker(self):
        global _coord_window_running
        _coord_window_running = False
        self.find_pos_btn.configure(state=tk.NORMAL)
        self.stop_pos_btn.configure(state=tk.DISABLED)
        self._log("Coordinate picker stopped.\n\n", "info")

    def _on_capture_once(self):
        device_ids = self._get_device_ids()
        if not device_ids:
            self._log("Error: Device ID is empty.\n", "error")
            return
        device_id = device_ids[0]
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
        self._start_runners(
            steps=get_steps_for_flow(MAIN_FLOW),
            run_label="Full Flow",
            loop_enabled=self.loop_var.get(),
        )

    def _on_run_score_flow(self):
        self._start_score_runners()

    def _on_run_pet_img_test(self):
        self._start_pet_img_test_runners()

    def _on_run_score_for_slot(self, slot_index):
        self._start_score_runner_for_slot(slot_index, load_templates=True)

    def _on_run_group(self):
        group_label = self.group_var.get()
        group_key = self.group_label_to_key.get(group_label)
        if not group_key:
            self._log("Error: No step group selected.\n", "error")
            return

        group_data = STEP_GROUPS[group_key]
        steps = resolve_group_steps(group_key)
        self._start_runners(
            steps=steps,
            run_label=group_data["label"],
            loop_enabled=False,
        )

    def _on_run_step(self):
        step_label = self.step_var.get()
        step_index = self.step_label_to_index.get(step_label)
        if step_index is None:
            self._log("Error: No single step selected.\n", "error")
            return

        step = STEPS[step_index]
        self._start_runners(
            steps=[step],
            run_label=get_step_label(step, step_index + 1),
            loop_enabled=False,
        )

    def _start_runners(self, steps, run_label, loop_enabled):
        device_ids = self._get_device_ids()
        if not device_ids:
            self._log("Error: At least one Device ID is required.\n", "error")
            return

        if not steps:
            self._log("Error: No steps to run.\n", "error")
            return

        if any(runner and runner.running for runner in self.runners):
            self._log("Bot is already running. Stop it before starting again.\n", "warn")
            return

        self._load_select_templates()
        self._log(f"=== Starting {run_label} on {len(device_ids)} device(s) ===\n", "success")
        self._log(f"Steps to run: {len(steps)}\n", "info")
        self._log(f"Loop mode: {'ON' if loop_enabled else 'OFF (single run)'}\n", "info")
        self._log("-" * 50 + "\n", "info")

        self._set_start_buttons_state(tk.DISABLED)
        self.stop_bot_btn.configure(state=tk.NORMAL)
        self.bot_info_var.set("Running...")
        self.bot_info_lbl.configure(text_color=SUCCESS_COLOR)

        for device_id in device_ids[:MAX_DEVICE_SLOTS]:
            slot_index = self._find_device_slot(device_id)
            if slot_index is None:
                continue
            runner = BotRunner(self, device_id, slot_index, steps, run_label, loop_enabled)
            self.runners[slot_index] = runner
            self._set_device_status(slot_index, "Starting")
            runner.start()
        self._update_device_controls()

    def _start_score_runners(self):
        device_ids = self._get_device_ids()
        if not device_ids:
            self._log("Error: At least one Device ID is required.\n", "error")
            return

        self._load_score_templates()
        missing = sorted(SCORE_TARGET_STEMS - {template["name"] for template in self.score_templates})
        if missing:
            self._log(f"Error: Missing score templates: {', '.join(missing)}\n", "error")
            return

        start_slots = []
        for device_id in device_ids[:MAX_DEVICE_SLOTS]:
            slot_index = self._find_device_slot(device_id)
            if slot_index is None:
                continue
            if self._slot_is_running(slot_index):
                self._log(f"[D{slot_index + 1} {device_id}] Already running. Skipped.\n", "warn")
                continue
            start_slots.append(slot_index)

        if not start_slots:
            self._log("No idle device slots available for Score Flow.\n", "warn")
            return

        self._log(f"=== Starting Score Flow on {len(start_slots)} device(s) ===\n", "success")
        self._log("Score targets: Victor'sFeatherLaurelWreath, Jingle-jangleCoinWallet, TaterTraderhatched!\n", "info")
        target_summary = ", ".join(
            f"D{slot_index + 1}={self._get_score_target_for_slot(slot_index)}"
            for slot_index in start_slots
        )
        self._log(f"Target score: {target_summary}\n", "info")
        self._log("-" * 50 + "\n", "info")

        self._set_start_buttons_state(tk.DISABLED)
        self.stop_bot_btn.configure(state=tk.NORMAL)
        self.bot_info_var.set("Score Flow Running...")
        self.bot_info_lbl.configure(text_color=SUCCESS_COLOR)

        for slot_index in start_slots:
            self._start_score_runner_for_slot(slot_index, load_templates=False)
        self._update_device_controls()

    def _start_score_runner_for_slot(self, slot_index, load_templates):
        device_id = self.device_id_vars[slot_index].get().strip()
        if not device_id:
            self._log(f"[D{slot_index + 1}] Error: Device ID is empty.\n", "error")
            return False

        if self._slot_is_running(slot_index):
            self._log(f"[D{slot_index + 1} {device_id}] Already running.\n", "warn")
            return False

        if load_templates:
            self._load_score_templates()
            missing = sorted(SCORE_TARGET_STEMS - {template["name"] for template in self.score_templates})
            if missing:
                self._log(f"Error: Missing score templates: {', '.join(missing)}\n", "error")
                return False

            target_score = self._get_score_target_for_slot(slot_index)
            self._log(f"=== Starting Score Flow on D{slot_index + 1}: {device_id} ===\n", "success")
            self._log(f"Target score: {target_score}\n", "info")
            self._log("-" * 50 + "\n", "info")
        else:
            target_score = self._get_score_target_for_slot(slot_index)

        runner = ScoreFlowRunner(self, device_id, slot_index, target_score)
        self.runners[slot_index] = runner
        self._set_device_status(slot_index, f"Score 0/{target_score}")
        self.bot_info_var.set("Score Flow Running...")
        self.bot_info_lbl.configure(text_color=SUCCESS_COLOR)
        self.stop_bot_btn.configure(state=tk.NORMAL)
        self._set_start_buttons_state(tk.DISABLED)
        runner.start()
        self._update_device_controls()
        return True

    def _start_pet_img_test_runners(self):
        device_ids = self._get_device_ids()
        if not device_ids:
            self._log("Error: At least one Device ID is required.\n", "error")
            return

        self._load_score_templates()
        if PET_TEST_TARGET_STEM not in {template["name"] for template in self.score_templates}:
            self._log(f"Error: Missing pet test template: {PET_TEST_TARGET_STEM}\n", "error")
            return

        start_slots = []
        for device_id in device_ids[:MAX_DEVICE_SLOTS]:
            slot_index = self._find_device_slot(device_id)
            if slot_index is None:
                continue
            if self._slot_is_running(slot_index):
                self._log(f"[D{slot_index + 1} {device_id}] Already running. Skipped.\n", "warn")
                continue
            start_slots.append(slot_index)

        if not start_slots:
            self._log("No idle device slots available for Pet Image Test.\n", "warn")
            return

        self._log(f"=== Starting Pet Image Test on {len(start_slots)} device(s) ===\n", "success")
        self._log(f"Image target: {PET_TEST_TARGET_STEM}\n", "info")
        self._log("Flow: State_Open_Pets_15 -> if matched stop, otherwise State_Reset_ID\n", "info")
        self._log("-" * 50 + "\n", "info")

        self._set_start_buttons_state(tk.DISABLED)
        self.stop_bot_btn.configure(state=tk.NORMAL)
        self.bot_info_var.set("Pet Image Test Running...")
        self.bot_info_lbl.configure(text_color=SUCCESS_COLOR)

        for slot_index in start_slots:
            device_id = self.device_id_vars[slot_index].get().strip()
            runner = PetImageTestRunner(self, device_id, slot_index)
            self.runners[slot_index] = runner
            self._set_device_status(slot_index, "Test Pet Img")
            runner.start()
        self._update_device_controls()

    def _on_stop_bot(self):
        any_running = False
        for runner in self.runners:
            if runner and runner.running:
                runner.stop()
                any_running = True
        if any_running:
            self._log("\n[Bot] Stop requested for all devices. Waiting for active delay/step to finish...\n", "warn")
        else:
            self._log("\n[Bot] No running bot to stop.\n", "warn")

    def _on_stop_slot(self, slot_index):
        runner = self.runners[slot_index]
        if runner and runner.running:
            runner.stop()
            self._log(
                f"\n[D{slot_index + 1} {runner.device_id}] Stop requested. Waiting for active delay/step to finish...\n",
                "warn",
            )
            self._update_device_controls()
        else:
            self._log(f"\n[D{slot_index + 1}] No running bot to stop.\n", "warn")

    def _bot_stopped(self):
        self._set_start_buttons_state(tk.NORMAL)
        self.stop_bot_btn.configure(state=tk.DISABLED)
        self.bot_info_var.set("Stopped")
        self.bot_info_lbl.configure(text_color=DANGER_COLOR)
        self._update_device_controls()

    def _runner_finished(self, slot_index):
        runner = self.runners[slot_index]
        self.runners[slot_index] = None
        self._set_device_status(slot_index, "Stopped")
        if runner:
            self._log(f"[D{slot_index + 1} {runner.device_id}] Bot stopped.\n", "warn")

        if not any(runner and runner.running for runner in self.runners):
            self._bot_stopped()
        else:
            self._update_global_controls()

    def _run_coord_picker(self, device_id):
        global _coord_window_running

        paused = False
        latest_frame = None
        last_capture_time = 0

        def on_mouse(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.safe_log(f"[Get coords] x={x}, y={y}\n", "coord")
            elif event == cv2.EVENT_RBUTTONDOWN:
                self.safe_log(f"[TAP] x={x}, y={y} ... ", "info")
                send_tap(device_id, x, y)
                self.safe_log(f"done.\n", "success")

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
        self.safe_log("Coordinate picker window closed.\n\n", "info")
        self.root.after(0, lambda: self.find_pos_btn.configure(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_pos_btn.configure(state=tk.DISABLED))

    def on_close(self):
        global _coord_window_running
        _coord_window_running = False
        for runner in self.runners:
            if runner and runner.running:
                runner.stop()
        cv2.destroyAllWindows()
        self.root.destroy()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
