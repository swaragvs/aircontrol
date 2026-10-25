import ctypes
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
import winreg
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8765"
APPDATA = Path(os.environ["APPDATA"]) / "AirControl"
SETTINGS = APPDATA / "settings.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
FROZEN = getattr(sys, "frozen", False)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

APPDATA.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("aircontrol.tray")
logger.setLevel(logging.INFO)
logger.addHandler(logging.handlers.RotatingFileHandler(
    APPDATA / "tray.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
))

if "--server" in sys.argv:
    import aircontrol

    aircontrol.main()
    raise SystemExit(0)

mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AirControlTray")
if ctypes.windll.kernel32.GetLastError() == 183:
    raise SystemExit(0)

stop_event = threading.Event()
server = None
supervisor_thread = None
icon = None


def api(path, data=None, timeout=2):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"null")
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def get_hours():
    try:
        value = json.loads(SETTINGS.read_text(encoding="utf-8")).get("session_hours", 3)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 8760:
            raise ValueError("invalid session_hours value")
        return value
    except FileNotFoundError:
        return 3
    except (OSError, json.JSONDecodeError, ValueError) as error:
        logger.warning("Could not read session limit: %s", error)
        return 3


def set_hours(hours):
    result = api("/api/settings", {"session_hours": hours})
    if result is None:
        notify("Could not update the session limit. Is the server running?")
        return
    if icon:
        icon.update_menu()


def autostart_on():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "AirControl")
            return True
    except FileNotFoundError:
        return False


def set_autostart(enabled):
    if FROZEN:
        launcher = sys.executable
        command = f'"{launcher}" --background'
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        launcher = str(pythonw if pythonw.exists() else Path(sys.executable))
        command = f'"{launcher}" "{Path(__file__).resolve()}" --background'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "AirControl", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "AirControl")
            except FileNotFoundError:
                pass
    if icon:
        icon.update_menu()


def notify(message):
    if icon:
        try:
            icon.notify(message, "AirControl")
        except Exception:
            logger.exception("Could not show tray notification")


def launch_server():
    global server
    command = (
        [sys.executable, "--server"]
        if FROZEN else
        [sys.executable, str(Path(__file__).resolve()), "--server"]
    )
    server = subprocess.Popen(
        command,
        creationflags=CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent),
    )
    logger.info("Started AirControl server process %s", server.pid)


def stop_server():
    global server
    child = server
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)
    logger.info("Stopped AirControl server process")
    server = None


def supervise():
    failures = 0
    last_event_ts = 0
    while not stop_event.is_set():
        if server is None or server.poll() is not None:
            delay = min(2 ** failures, 30)
            if failures:
                logger.warning("Server exited; retrying in %s seconds", delay)
            failures += 1
            if stop_event.wait(delay):
                break
            try:
                launch_server()
            except OSError:
                logger.exception("Could not start AirControl server")
            continue

        failures = 0
        status = api("/api/status")
        if status:
            event = status.get("last_event") or {}
            timestamp = event.get("ts", 0)
            if timestamp > last_event_ts:
                last_event_ts = timestamp
                notify(f'{event.get("name", "Phone")} {event.get("type", "connected")}')
            hours = get_hours()
            if hours and status.get("clients") == 0 and status.get("uptime", 0) > hours * 3600:
                logger.info("Restarting idle server after configured uptime limit")
                stop_server()
                if not stop_event.is_set():
                    try:
                        launch_server()
                    except OSError:
                        logger.exception("Could not restart AirControl server")
        stop_event.wait(10)


def ask_yes_no(title, message):
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        return messagebox.askyesno(title, message, parent=root)
    finally:
        root.destroy()


def ask_custom_hours():
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        hours = simpledialog.askfloat(
            "Custom session limit",
            "Enter session length in hours (0 means never):",
            minvalue=0,
            maxvalue=8760,
            initialvalue=get_hours(),
            parent=root,
        )
        if hours is not None:
            set_hours(hours)
    finally:
        root.destroy()


def revoke_device(device_id, name):
    try:
        confirmed = ask_yes_no("Revoke trusted phone", f"Revoke access for {name}?")
    except Exception:
        logger.exception("Could not display revocation confirmation")
        return
    if not confirmed:
        return
    if api("/api/revoke", {"id": device_id}) is None:
        notify(f"Could not revoke {name}. Is the server running?")
    elif icon:
        icon.update_menu()


def trusted_items():
    devices = api("/api/trusted")
    if devices is None:
        return [pystray.MenuItem("Server unavailable", None, enabled=False)]
    if not devices:
        return [pystray.MenuItem("No paired phones", None, enabled=False)]

    def action(device_id, name):
        def revoke(_icon, _item):
            revoke_device(device_id, name)
        return revoke

    return [
        pystray.MenuItem(
            f'Revoke {device.get("name", "Phone")}',
            action(device["id"], device.get("name", "Phone")),
        )
        for device in devices
    ]


def hours_item(label, hours):
    return pystray.MenuItem(
        label,
        lambda: set_hours(hours),
        checked=lambda _item: get_hours() == hours,
        radio=True,
    )


def custom_hours_item():
    return pystray.MenuItem("Custom...", lambda: ask_custom_hours())


def toggle_autostart(_item):
    try:
        set_autostart(not autostart_on())
    except OSError:
        logger.exception("Could not update Windows autostart")
        notify("Could not update Start with Windows.")


def quit_app(icon_, _item):
    stop_event.set()
    icon_.stop()


def make_icon():
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), 14, fill=(245, 185, 66, 255))
    draw.ellipse((24, 20, 40, 36), fill=(28, 37, 48, 255))
    return image


def build_menu():
    return pystray.Menu(
        pystray.MenuItem("Pair new phone", lambda: webbrowser.open(BASE + "/pair"), default=True),
        pystray.MenuItem("Trusted phones", pystray.Menu(lambda: trusted_items())),
        pystray.MenuItem(
            "Session limit",
            pystray.Menu(
                hours_item("1 hour", 1),
                hours_item("3 hours (default)", 3),
                hours_item("6 hours", 6),
                hours_item("12 hours", 12),
                custom_hours_item(),
                hours_item("Never", 0),
            ),
        ),
        pystray.MenuItem("Start with Windows", toggle_autostart, checked=lambda _item: autostart_on()),
        pystray.MenuItem("Open log folder", lambda: os.startfile(APPDATA)),
        pystray.MenuItem("Quit", quit_app),
    )


def main():
    global icon, supervisor_thread
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "AirControl")
    except FileNotFoundError:
        marker = APPDATA / ".autostart_set"
        if not marker.exists():
            set_autostart(True)
            marker.touch()

    icon = pystray.Icon("AirControl", make_icon(), "AirControl", build_menu())
    supervisor_thread = threading.Thread(target=supervise, name="AirControl supervisor", daemon=True)
    supervisor_thread.start()
    try:
        icon.run()
    finally:
        stop_event.set()
        supervisor_thread.join(timeout=5)
        stop_server()
        ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
