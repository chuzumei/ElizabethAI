import subprocess
import os
import threading
import time

def _default_sink() -> str:
    result = subprocess.run(
        ["pactl", "get-default-sink"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def set_volume(level: int) -> str:
    """Set system volume (0-100) on Linux/PipeWire."""
    level = max(0, min(100, level))
    sink = _default_sink()

    if not sink:
        return "Could not find the default audio output."

    result = subprocess.run(
        ["pactl", "set-sink-volume", sink, f"{level}%"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not set volume: {result.stderr.strip()}"

    return f"Volume set to {level}%."


def get_volume() -> str:
    """Get current system volume (0-100) on Linux/PipeWire."""
    sink = _default_sink()

    if not sink:
        return "Could not find the default audio output."

    result = subprocess.run(
        ["pactl", "get-sink-volume", sink],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not read volume: {result.stderr.strip()}"

    import re
    match = re.search(r"(\d+)%", result.stdout)

    if not match:
        return "Could not read volume."

    return f"Volume is at {match.group(1)}%."


def get_clipboard() -> str:
    """Read text from the Wayland clipboard."""
    result = subprocess.run(
        ["wl-paste", "--no-newline"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Could not read clipboard: {result.stderr.strip()}"

    return result.stdout


def set_clipboard(text: str) -> str:
    """Write text to the Wayland clipboard without blocking."""
    try:
        proc = subprocess.Popen(
            ["wl-copy"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )

        proc.stdin.write(text)
        proc.stdin.close()

        return "Clipboard updated."
    except Exception as e:
        return f"Could not set clipboard: {e}"



def get_system_info() -> str:
    """Get CPU, RAM, and disk usage on Linux."""
    try:
        # CPU usage from /proc/stat
        def read_cpu():
            with open("/proc/stat", "r") as f:
                values = [int(x) for x in f.readline().split()[1:]]
            idle = values[3] + values[4]
            total = sum(values)
            return idle, total

        import time

        idle1, total1 = read_cpu()
        time.sleep(0.15)
        idle2, total2 = read_cpu()

        total_delta = total2 - total1
        idle_delta = idle2 - idle1
        cpu = 0.0 if total_delta == 0 else (1 - idle_delta / total_delta) * 100

        # RAM from /proc/meminfo
        mem = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, value = line.split(":", 1)
                mem[key] = int(value.strip().split()[0])

        ram_total = mem["MemTotal"] / 1024 / 1024
        ram_available = mem["MemAvailable"] / 1024 / 1024
        ram_used = ram_total - ram_available

        # Root filesystem
        disk = __import__("shutil").disk_usage("/")
        disk_total = disk.total / 1024**3
        disk_free = disk.free / 1024**3

        return (
            f"CPU: {cpu:.0f}% | "
            f"RAM: {ram_used:.1f}/{ram_total:.1f} GB | "
            f"Disco: {disk_free:.1f}/{disk_total:.1f} GB livres"
        )
    except Exception as e:
        return f"Could not read system info: {e}"



def set_brightness(level: int) -> str:
    """Set brightness on all DDC/CI-compatible monitors."""
    level = max(0, min(100, level))

    try:
        detect = subprocess.run(
            ["ddcutil", "detect", "--brief"],
            capture_output=True,
            text=True,
        )

        displays = []
        for line in detect.stdout.splitlines():
            line = line.strip()
            if line.startswith("Display "):
                try:
                    displays.append(int(line.split()[1]))
                except Exception:
                    pass

        if not displays:
            return "No DDC/CI-compatible monitors found."

        changed = []
        failed = []

        for display in displays:
            result = subprocess.run(
                [
                    "ddcutil",
                    "--display",
                    str(display),
                    "setvcp",
                    "10",
                    str(level),
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                import time
                time.sleep(0.2)
                result = subprocess.run(
                    [
                        "ddcutil",
                        "--display",
                        str(display),
                        "setvcp",
                        "10",
                        str(level),
                    ],
                    capture_output=True,
                    text=True,
                )

            if result.returncode == 0:
                changed.append(str(display))
            else:
                failed.append(str(display))

        if changed and not failed:
            return f"Brightness set to {level}% on {len(changed)} monitor(s)."

        if changed:
            return (
                f"Brightness set to {level}% on monitor(s) "
                f"{', '.join(changed)}, but failed on {', '.join(failed)}."
            )

        return "Could not change monitor brightness."

    except FileNotFoundError:
        return "ddcutil is not installed."
    except Exception as e:
        return f"Could not set brightness: {e}"



def lock_screen() -> str:
    """Lock the current Linux session."""
    try:
        result = subprocess.run(
            ["loginctl", "lock-session"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return f"Could not lock screen: {result.stderr.strip()}"

        return "Screen locked."
    except Exception as e:
        return f"Could not lock screen: {e}"


def power_command(action: str) -> str:
    """Shutdown, restart, or suspend the Linux system."""
    action = action.lower().strip()

    commands = {
        "shutdown": ["systemctl", "poweroff"],
        "restart": ["systemctl", "reboot"],
        "sleep": ["systemctl", "suspend"],
    }

    command = commands.get(action)

    if command is None:
        return f"Unknown power action: {action}. Use shutdown/restart/sleep."

    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        if action == "shutdown":
            return "Shutting down."
        if action == "restart":
            return "Restarting."
        return "Going to sleep."

    except Exception as e:
        return f"Could not execute power command: {e}"



def show_notification(title: str, message: str) -> str:
    """Show a desktop notification on Linux."""
    try:
        result = subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return f"Notification shown: {title}"

        return f"Notification failed: {result.stderr.strip()}"

    except FileNotFoundError:
        return "Notification failed: notify-send is not installed."
    except Exception as e:
        return f"Notification failed: {e}"


# --- Timer / Reminder ---
_timers: list = []


def set_timer(seconds: int, message: str = "Timer done!") -> str:
    """Set a timer that shows a notification after N seconds."""
    def _timer_cb():
        show_notification("Elizabeth Timer", message)

    t = threading.Timer(seconds, _timer_cb)
    t.daemon = True
    t.start()
    _timers.append(t)

    if seconds >= 3600:
        time_str = f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    elif seconds >= 60:
        time_str = f"{seconds // 60}m {seconds % 60}s"
    else:
        time_str = f"{seconds}s"
    return f"Timer set for {time_str}: {message}"
