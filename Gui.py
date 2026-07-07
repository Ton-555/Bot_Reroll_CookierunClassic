"""
GUI Main Interface for MuMu Player Reroll Bot
"""

import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext
import cv2
import numpy as np

from Bot import (
    MAIN_FLOW,
    STEPS,
    STEP_GROUPS,
    get_step_label,
    get_steps_for_flow,
    get_runtime_step_delay,
    jitter_tap_coordinates,
    resolve_group_steps,
    tap as bot_tap,
    input_text as bot_text,
    keyevent as bot_keyevent,
)

DEFAULT_DEVICE_ID = "127.0.0.1:16384"
MAX_DEVICE_SLOTS = 6
REFRESH_INTERVAL = 0.7
IMAGE_SELECT_DIR = Path(__file__).resolve().parent / "Image_Select"
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
                self.app.safe_main_log(
                    self._format_score_loop_main_log(),
                    "info",
                )

                self._execute_state("1", STATE_OPEN_FREE_TREASURE)
                if self._should_stop_now():
                    break

                if self.score == 2:
                    self.log("State 1 ended with score 2. Routing to State 3.\n", "info")
                    self._execute_state("3", STATE_OPEN_PETS_15)
                    if self._should_stop_now():
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
                    self._execute_state("5", STATE_OPEN_PETS_9)
                    if self._should_stop_now():
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
                self.app.safe_main_log(
                    f"[D{self.slot_index + 1} {self.device_id}] Score complete | "
                    f"Loop #{self.cycle_count}  | Score {self.score}/{self.target_score}"
                    f"{self._format_found_targets()}\n",
                    "success",
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

    def _execute_state(self, state_number, group_key):
        group_data = STEP_GROUPS[group_key]
        self.log(f"-- State {state_number}: {group_data['label']} --\n", "info")
        self.app.root.after(
            0,
            lambda s=state_number: self.app._set_device_status(
                self.slot_index,
                f"State {s} | Score {self.score}/{self.target_score}",
            ),
        )
        self._execute_group(group_key)

    def _reset_score_for_next_account(self):
        self.score = 0
        self.matched_targets.clear()
        self.matched_target_names.clear()
        self.app.root.after(
            0,
            lambda: self.app._set_device_status(self.slot_index, f"Score 0/{self.target_score}"),
        )
        self.log(f"Score reset to 0/{self.target_score} for next account.\n", "info")

    def _execute_group(self, group_key):
        group_data = STEP_GROUPS[group_key]
        steps = resolve_group_steps(group_key)
        self.log(f"-- Group: {group_data['label']} ({len(steps)} steps) --\n", "info")
        self._execute_steps(steps)

    def _execute_steps(self, steps):
        for i, step in enumerate(steps, 1):
            if not self.running or self.score >= self.target_score:
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

            if self.score >= self.target_score:
                self.running = False
                break

    def _should_stop_now(self):
        return not self.running or self.score >= self.target_score


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
        self.root.geometry("1100x720")
        self.root.resizable(True, True)

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
        self.log_widget = None

        for slot in range(MAX_DEVICE_SLOTS):
            default_value = DEFAULT_DEVICE_ID if slot == 0 else ""
            device_var = tk.StringVar(value=default_value)
            status_var = tk.StringVar(value="Ready" if slot == 0 else "Empty")
            score_target_var = tk.StringVar(value=str(DEFAULT_SCORE_TARGET))
            device_var.trace_add("write", lambda *_: self._update_device_controls())
            self.device_id_vars.append(device_var)
            self.device_status_vars.append(status_var)
            self.device_score_target_vars.append(score_target_var)

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        main_tab = ttk.Frame(notebook)
        debug_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Main")
        notebook.add(debug_tab, text="Debug")

        self._build_main_tab(main_tab)
        self._build_debug_tab(debug_tab)

        self._log("Application started.\n", "success")
        self._log(f"Default device slot 1: {DEFAULT_DEVICE_ID}\n", "info")
        self._log(f"Bot steps loaded: {len(STEPS)}\n\n", "info")
        self._main_log("Application started.\n", "success")
        self._load_select_templates()
        self._load_score_templates()
        self._update_device_controls()

    def _build_main_tab(self, parent):
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_device_settings(main_frame)

        main_log_frame = ttk.LabelFrame(main_frame, text="Main Log", padding=5)
        main_log_frame.pack(fill=tk.BOTH, expand=True)

        main_log_filter_frame = ttk.Frame(main_log_frame)
        main_log_filter_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(main_log_filter_frame, text="Device:").pack(side=tk.LEFT, padx=(0, 5))
        self.main_log_filter_combo = ttk.Combobox(
            main_log_filter_frame,
            textvariable=self.main_log_filter_var,
            state="readonly",
            width=34,
        )
        self.main_log_filter_combo.pack(side=tk.LEFT)
        self.main_log_filter_combo.bind("<<ComboboxSelected>>", self._on_main_log_filter_changed)

        self.main_log_widget = scrolledtext.ScrolledText(
            main_log_frame, wrap=tk.WORD, width=70, height=18,
            font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.main_log_widget.pack(fill=tk.BOTH, expand=True)
        self._configure_log_tags(self.main_log_widget)
        self._update_main_log_filter_options()

    def _build_debug_tab(self, parent):
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_device_settings(main_frame)

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

        self.run_bot_btn = ttk.Button(bot_frame, text="Run Full Flow", command=self._on_run_bot)
        self.run_bot_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.run_score_btn = ttk.Button(bot_frame, text="Run Score Flow", command=self._on_run_score_flow)
        self.run_score_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.run_pet_img_test_btn = ttk.Button(
            bot_frame,
            text="Run Test Img pet",
            command=self._on_run_pet_img_test,
        )
        self.run_pet_img_test_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_bot_btn = ttk.Button(bot_frame, text="Stop All", command=self._on_stop_bot, state=tk.DISABLED)
        self.stop_bot_btn.pack(side=tk.LEFT)

        self.loop_var = tk.BooleanVar(value=True)
        self.loop_check = ttk.Checkbutton(
            bot_frame, text="Loop", variable=self.loop_var
        )
        self.loop_check.pack(side=tk.RIGHT, padx=(10, 0))

        step_frame = ttk.LabelFrame(main_frame, text="Step Control", padding=5)
        step_frame.pack(fill=tk.X, pady=(0, 5))

        self.group_label_to_key = {
            f"{data['label']} ({len(resolve_group_steps(key))} steps)": key
            for key, data in STEP_GROUPS.items()
        }
        ttk.Label(step_frame, text="Group:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.group_var = tk.StringVar(value=next(iter(self.group_label_to_key)))
        self.group_combo = ttk.Combobox(
            step_frame,
            textvariable=self.group_var,
            values=list(self.group_label_to_key.keys()),
            state="readonly",
            width=34,
        )
        self.group_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 5), pady=2)
        self.run_group_btn = ttk.Button(step_frame, text="Run Group", command=self._on_run_group)
        self.run_group_btn.grid(row=0, column=2, sticky=tk.W, padx=(0, 10), pady=2)

        self.step_label_to_index = {
            get_step_label(step, index): index - 1
            for index, step in enumerate(STEPS, 1)
        }
        ttk.Label(step_frame, text="Single Step:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.step_var = tk.StringVar(value=next(iter(self.step_label_to_index)))
        self.step_combo = ttk.Combobox(
            step_frame,
            textvariable=self.step_var,
            values=list(self.step_label_to_index.keys()),
            state="readonly",
            width=52,
        )
        self.step_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 5), pady=2)
        self.run_step_btn = ttk.Button(step_frame, text="Run Step", command=self._on_run_step)
        self.run_step_btn.grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=2)

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_widget = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, width=70, height=15,
            font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self._configure_log_tags(self.log_widget)

    def _build_device_settings(self, parent):
        settings_frame = ttk.LabelFrame(parent, text="Device Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        for slot in range(MAX_DEVICE_SLOTS):
            ttk.Label(settings_frame, text=f"Device {slot + 1}:").grid(
                row=slot, column=0, sticky=tk.W, padx=(0, 5), pady=2
            )

            ttk.Entry(settings_frame, textvariable=self.device_id_vars[slot], width=30).grid(
                row=slot, column=1, sticky=tk.W, padx=(0, 10), pady=2
            )
            ttk.Label(settings_frame, textvariable=self.device_status_vars[slot], width=18, foreground="gray").grid(
                row=slot, column=2, sticky=tk.W, padx=(0, 10), pady=2
            )
            ttk.Label(settings_frame, text="Target:").grid(
                row=slot, column=3, sticky=tk.W, padx=(0, 5), pady=2
            )
            score_target_combo = ttk.Combobox(
                settings_frame,
                textvariable=self.device_score_target_vars[slot],
                values=SCORE_TARGET_CHOICES,
                state="readonly",
                width=3,
            )
            score_target_combo.grid(row=slot, column=4, sticky=tk.W, padx=(0, 10), pady=2)
            score_btn = ttk.Button(
                settings_frame,
                text="Run Score",
                command=lambda slot_index=slot: self._on_run_score_for_slot(slot_index),
            )
            score_btn.grid(row=slot, column=5, sticky=tk.W, padx=(0, 5), pady=2)
            stop_btn = ttk.Button(
                settings_frame,
                text="Stop",
                command=lambda slot_index=slot: self._on_stop_slot(slot_index),
                state=tk.DISABLED,
            )
            stop_btn.grid(row=slot, column=6, sticky=tk.W, padx=(0, 10), pady=2)
            self.device_score_target_controls[slot].append(score_target_combo)
            self.device_score_buttons[slot].append(score_btn)
            self.device_stop_buttons[slot].append(stop_btn)

        ttk.Button(settings_frame, text="Reset ADB & Find", command=self._on_reset_adb).grid(
            row=0, column=7, padx=5
        )
        ttk.Button(settings_frame, text="List Devices", command=self._on_list_devices).grid(
            row=1, column=7, padx=5
        )
        ttk.Button(settings_frame, text="Fill Found Devices", command=self._on_fill_devices).grid(
            row=2, column=7, padx=5
        )

    def _configure_log_tags(self, widget):
        widget.tag_config("info", foreground="#4ec9b0")
        widget.tag_config("coord", foreground="#569cd6")
        widget.tag_config("error", foreground="#f44747")
        widget.tag_config("success", foreground="#6a9955")
        widget.tag_config("warn", foreground="#dcdcaa")

    def _log(self, text, tag=None):
        if self.log_widget is None:
            return
        self.log_widget.insert(tk.END, text, tag)
        self.log_widget.see(tk.END)

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

        self.main_log_filter_combo["values"] = values
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
        self.main_log_widget.delete("1.0", tk.END)
        for entry in self.main_log_entries:
            if self._main_log_entry_visible(entry):
                self.main_log_widget.insert(tk.END, entry["text"], entry["tag"])
        self.main_log_widget.see(tk.END)

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
        self.run_bot_btn.config(state=state)
        self.run_score_btn.config(state=state)
        self.run_pet_img_test_btn.config(state=state)
        self.run_group_btn.config(state=state)
        self.run_step_btn.config(state=state)

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
                control.config(state=score_target_state)
            for button in self.device_score_buttons[slot_index]:
                button.config(state=score_state)
            for button in self.device_stop_buttons[slot_index]:
                button.config(state=stop_state)
        self._update_main_log_filter_options()

    def _update_global_controls(self):
        any_running = any(runner and runner.running for runner in self.runners)
        self._set_start_buttons_state(tk.DISABLED if any_running else tk.NORMAL)
        self.stop_bot_btn.config(state=tk.NORMAL if any_running else tk.DISABLED)
        self.bot_info_var.set("Running..." if any_running else "Stopped")
        self.bot_info_lbl.config(foreground="green" if any_running else "red")
        self._update_device_controls()

    def _read_adb_devices(self):
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
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
        subprocess.run(["adb", "kill-server"], capture_output=True)
        self._log("      done.\n\n", "success")

        self._log("[2/3] adb start-server...\n", "info")
        result = subprocess.run(["adb", "start-server"], capture_output=True, text=True)
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
        self.stop_bot_btn.config(state=tk.NORMAL)
        self.bot_info_var.set("Running...")
        self.bot_info_lbl.config(foreground="green")

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
        self.stop_bot_btn.config(state=tk.NORMAL)
        self.bot_info_var.set("Score Flow Running...")
        self.bot_info_lbl.config(foreground="green")

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
        self.bot_info_lbl.config(foreground="green")
        self.stop_bot_btn.config(state=tk.NORMAL)
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
        self.stop_bot_btn.config(state=tk.NORMAL)
        self.bot_info_var.set("Pet Image Test Running...")
        self.bot_info_lbl.config(foreground="green")

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
        self.stop_bot_btn.config(state=tk.DISABLED)
        self.bot_info_var.set("Stopped")
        self.bot_info_lbl.config(foreground="red")
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
        self.root.after(0, lambda: self.find_pos_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_pos_btn.config(state=tk.DISABLED))

    def on_close(self):
        global _coord_window_running
        _coord_window_running = False
        for runner in self.runners:
            if runner and runner.running:
                runner.stop()
        cv2.destroyAllWindows()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
