import subprocess
import time
import os
import tempfile
import json
import platform
from pathlib import Path


COSMICMSG = os.path.expanduser("~/.cargo/bin/cosmicmsg")


# ──────────────── Typing & Keys ────────────────

def type_text(text: str) -> str:
    """Type text at the current cursor position."""
    time.sleep(0.15)

    if platform.system() == "Windows":
        try:
            import pyautogui
            pyautogui.write(text, interval=0.02)
            return f"Typed: {text[:80]}"
        except Exception as e:
            return f"Could not type text: {e}"

    result = subprocess.run(
        ["wtype", text],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not type text: {result.stderr.strip()}"

    return f"Typed: {text[:80]}"

_KEYCODES = {
    "enter": 28,
    "return": 28,
    "esc": 1,
    "escape": 1,
    "space": 57,
    "tab": 15,
    "backspace": 14,
    "delete": 111,
    "up": 103,
    "down": 108,
    "left": 105,
    "right": 106,
    "home": 102,
    "end": 107,
    "pageup": 104,
    "pagedown": 109,
    "ctrl": 29,
    "control": 29,
    "shift": 42,
    "alt": 56,
    "super": 125,
    "meta": 125,
}


def press_key(keys: str) -> str:
    """Press a key or hotkey combo using ydotool."""
    parts = [k.strip().lower() for k in keys.split("+") if k.strip()]

    if not parts:
        return "No key specified."

    codes = []
    unknown = []

    for part in parts:
        if len(part) == 1 and part.isalpha():
            code = {
                "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33,
                "g": 34, "h": 35, "i": 23, "j": 36, "k": 37, "l": 38,
                "m": 50, "n": 49, "o": 24, "p": 25, "q": 16, "r": 19,
                "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45,
                "y": 21, "z": 44,
            }[part]
        elif part in _KEYCODES:
            code = _KEYCODES[part]
        else:
            unknown.append(part)
            continue

        codes.append(code)

    if unknown:
        return f"Unknown key(s): {', '.join(unknown)}"

    args = ["ydotool", "key"]

    for code in codes:
        args.append(f"{code}:1")

    for code in reversed(codes):
        args.append(f"{code}:0")

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not press key: {result.stderr.strip()}"

    return f"Pressed: {keys}"


# ──────────────── Mouse Control ────────────────

def click_at(x: int, y: int, button: str = "left") -> str:
    """Move to screen coordinates and click using ydotool."""
    move = subprocess.run(
        ["ydotool", "mousemove", "--absolute", str(x), str(y)],
        capture_output=True,
        text=True,
    )

    if move.returncode != 0:
        return f"Could not move mouse: {move.stderr.strip()}"

    button = button.lower().strip()

    click_codes = {
        "left": "0xC0",
        "right": "0xC1",
    }

    if button == "double":
        for _ in range(2):
            result = subprocess.run(
                ["ydotool", "click", "0xC0"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return f"Could not click: {result.stderr.strip()}"
            time.sleep(0.08)

        return f"Clicked (double) at ({x}, {y})."

    code = click_codes.get(button)

    if code is None:
        return f"Unknown mouse button: {button}. Use left/right/double."

    result = subprocess.run(
        ["ydotool", "click", code],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not click: {result.stderr.strip()}"

    return f"Clicked ({button}) at ({x}, {y})."


def scroll_screen(direction: str, amount: int = 3) -> str:
    """Scroll up or down using ydotool."""
    direction = direction.lower().strip()
    amount = max(1, int(amount))

    if direction == "up":
        value = "4"
    elif direction == "down":
        value = "5"
    else:
        return f"Unknown direction: {direction}. Use up/down."

    for _ in range(amount):
        result = subprocess.run(
            ["ydotool", "click", value],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return f"Could not scroll: {result.stderr.strip()}"

    return f"Scrolled {direction} by {amount}."


def move_mouse(x: int, y: int) -> str:
    """Move mouse cursor to absolute screen coordinates."""
    result = subprocess.run(
        ["ydotool", "mousemove", "--absolute", str(x), str(y)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not move mouse: {result.stderr.strip()}"

    return f"Moved mouse to ({x}, {y})."


# ──────────────── Screen Reading (OCR) ────────────────

def _capture_screen(path: str) -> str:
    """Capture the primary COSMIC output to a PNG file."""
    result = subprocess.run(
        [COSMICMSG, "capture", "output", "-f", path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not capture screen: {result.stderr.strip()}"

    return path


def read_screen() -> str:
    """Capture the screen and OCR visible text with approximate positions."""
    tmp = os.path.join(tempfile.gettempdir(), "elizabeth_screen.png")

    captured = _capture_screen(tmp)
    if captured.startswith("Could not capture"):
        return captured

    return _ocr_image(tmp)


def _ocr_image(image_path: str) -> str:
    """Run Tesseract OCR and return text with approximate center coordinates."""
    result = subprocess.run(
        [
            "tesseract",
            image_path,
            "stdout",
            "-l",
            "por+eng",
            "tsv",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode != 0:
        return f"OCR failed: {result.stderr.strip()}"

    lines = {}

    for raw in result.stdout.splitlines()[1:]:
        cols = raw.split("\t")

        if len(cols) != 12:
            continue

        try:
            level = int(cols[0])
            block = int(cols[2])
            par = int(cols[3])
            line = int(cols[4])
            left = int(cols[6])
            top = int(cols[7])
            width = int(cols[8])
            height = int(cols[9])
            conf = float(cols[10])
            word = cols[11].strip()
        except Exception:
            continue

        if level != 5 or not word or conf < 20:
            continue

        key = (block, par, line)
        item = lines.setdefault(
            key,
            {
                "words": [],
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            },
        )

        item["words"].append(word)
        item["left"] = min(item["left"], left)
        item["top"] = min(item["top"], top)
        item["right"] = max(item["right"], left + width)
        item["bottom"] = max(item["bottom"], top + height)

    output = []

    for item in lines.values():
        content = " ".join(item["words"]).strip()

        if not content:
            continue

        cx = int((item["left"] + item["right"]) / 2)
        cy = int((item["top"] + item["bottom"]) / 2)

        output.append(f"{content} | {cx},{cy}")

    if not output:
        return "No text found on screen."

    return "\n".join(output)


def find_on_screen(text: str) -> str:
    """Find visible text using OCR and return coordinates."""
    screen_text = read_screen()

    if screen_text == "No text found on screen.":
        return screen_text

    if screen_text.startswith("Could not capture") or screen_text.startswith("OCR failed"):
        return screen_text

    target = text.lower()
    best_match = None
    best_score = 0

    for line in screen_text.split("\n"):
        if " | " not in line:
            continue

        content, coords = line.rsplit(" | ", 1)
        content_lower = content.lower()

        if target in content_lower:
            x, y = coords.split(",")
            return f"Found '{text}' at ({x.strip()}, {y.strip()}). Use click_at to click it."

        words_target = set(target.split())
        words_content = set(content_lower.split())
        overlap = len(words_target & words_content)

        if overlap > best_score:
            best_score = overlap
            best_match = (content, coords)

    if best_match and best_score > 0:
        content, coords = best_match
        x, y = coords.split(",")
        return f"Closest match: '{content}' at ({x.strip()}, {y.strip()}). Use click_at to click it."

    return f"'{text}' not found on screen."


# ──────────────── Window Management ────────────────

def _get_toplevels():
    """Return COSMIC toplevel window data as Python objects."""
    result = subprocess.run(
        [COSMICMSG, "--json", "get-toplevels"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not query windows.")

    return json.loads(result.stdout)


def get_open_windows() -> str:
    """Return titles and identifiers of all open COSMIC windows."""
    try:
        windows = _get_toplevels()
    except Exception as e:
        return f"Could not list windows: {e}"

    if not windows:
        return "No open windows found."

    lines = []

    for window in windows:
        title = window.get("title") or "(untitled)"
        app_id = window.get("app_id") or "unknown"
        identifier = window.get("identifier") or ""
        state = ", ".join(window.get("state") or []) or "normal"

        lines.append(
            f"{title} | app={app_id} | id={identifier} | state={state}"
        )

    return "\n".join(lines)


def focus_window(title: str) -> str:
    """Bring a window to the foreground by partial title match."""
    target = title.lower().strip()

    if platform.system() == "Windows":
        try:
            import pygetwindow as gw
            matches = [w for w in gw.getAllWindows() if w.title and target in w.title.lower()]
            if not matches:
                return f"No window matching '{title}' found."

            matches.sort(key=lambda w: (0 if w.title.lower() == target else 1, len(w.title)))
            window = matches[0]

            if window.isMinimized:
                window.restore()
                time.sleep(0.15)

            window.activate()
            time.sleep(0.2)
            return f"Focused: {window.title}"
        except Exception as e:
            return f"Could not focus '{title}': {e}"

    try:
        windows = _get_toplevels()
    except Exception as e:
        return f"Could not list windows: {e}"

    matches = []
    for window in windows:
        window_title = (window.get("title") or "").lower()
        app_id = (window.get("app_id") or "").lower()
        if target in window_title or target in app_id:
            matches.append(window)

    if not matches:
        return f"No window matching '{title}' found."

    matches.sort(key=lambda w: (0 if (w.get("title") or "").lower() == target else 1, len(w.get("title") or "")))
    window = matches[0]
    identifier = window.get("identifier")

    if not identifier:
        return f"Window matching '{title}' has no identifier."

    state = window.get("state") or []
    if "minimized" in state:
        subprocess.run([COSMICMSG, "window", "unminimize", identifier], capture_output=True, text=True)

    result = subprocess.run([COSMICMSG, "window", "activate", identifier], capture_output=True, text=True)

    if result.returncode != 0:
        return f"Could not focus '{title}': {result.stderr.strip()}"

    return f"Focused: {window.get('title') or title}"

# ──────────────── Media Control ────────────────

def media_control(action: str) -> str:
    """Control media playback on Linux using playerctl/PipeWire."""
    action = action.lower().strip()

    player_commands = {
        "play": ["playerctl", "play"],
        "pause": ["playerctl", "pause"],
        "playpause": ["playerctl", "play-pause"],
        "next": ["playerctl", "next"],
        "skip": ["playerctl", "next"],
        "previous": ["playerctl", "previous"],
        "prev": ["playerctl", "previous"],
    }

    if action == "mute":
        sink = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
        ).stdout.strip()

        if not sink:
            return "Could not find the default audio output."

        result = subprocess.run(
            ["pactl", "set-sink-mute", sink, "toggle"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return f"Could not toggle mute: {result.stderr.strip()}"

        return "Media: mute toggled"

    command = player_commands.get(action)

    if command is None:
        return f"Unknown media action: {action}. Use play/pause/playpause/next/previous/mute."

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        error = result.stderr.strip() or "No controllable media player found."
        return f"Could not control media: {error}"

    return f"Media: {action}"


def screenshot(filename: str = "") -> str:
    """Take a screenshot using the COSMIC compositor and save it to Desktop."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

    if not filename:
        filename = f"screenshot_{int(time.time())}.png"

    if not filename.lower().endswith(".png"):
        filename += ".png"

    # Prevent a filename from escaping the Desktop directory.
    filename = os.path.basename(filename)
    path = os.path.join(desktop, filename)

    result = subprocess.run(
        [COSMICMSG, "capture", "output", "-f", path, "--cursor"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not take screenshot: {result.stderr.strip()}"

    if not os.path.isfile(path):
        return "Screenshot command completed, but the image file was not created."

    return f"Screenshot saved: {path}"
