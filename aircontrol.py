#!/usr/bin/env python3
"""
AirControl - use your phone as an air mouse, touchpad and keyboard for this computer.

Setup (once):   python -m pip install aiohttp pynput qrcode pystray pillow
Run tray app:   python tray.py
Run server:     python aircontrol.py
Pair a phone from the local pairing page at http://127.0.0.1:8765/pair.
Phone and computer must be on the same private Wi-Fi network.
"""
import asyncio, base64, ctypes, hashlib, hmac, html, ipaddress, json, logging, logging.handlers, math, os, pathlib, secrets, socket, time, uuid
from ctypes import wintypes
from aiohttp import web, WSMsgType
from pynput.keyboard import Controller as Keyboard, Key
from pynput.mouse import Button, Controller as Mouse

PORT = 8765
MAX_SESSION_HOURS = 8760
APP_DIR = pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "AirControl"
TRUSTED_PATH = APP_DIR / "trusted.json"
SETTINGS_PATH = APP_DIR / "settings.json"
IDENTITY_PATH = APP_DIR / "identity.json"
APP_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("aircontrol")
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.handlers.RotatingFileHandler(
    APP_DIR / "server.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
))
mouse, kb = Mouse(), Keyboard()
started_at = time.time()
last_event = None
active_clients = {}
live_sockets = {}


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, data):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def dpapi(data, protect):
    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    source_buffer = ctypes.create_string_buffer(data)
    source = DataBlob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    result = DataBlob()
    crypt = ctypes.windll.crypt32
    kernel = ctypes.windll.kernel32
    crypt.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.POINTER(DataBlob),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DataBlob),
    ]
    crypt.CryptProtectData.restype = wintypes.BOOL
    crypt.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DataBlob),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DataBlob),
    ]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    if not fn(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel.LocalFree(result.pbData)


def protect_secret(secret):
    return base64.b64encode(dpapi(bytes.fromhex(secret), True)).decode("ascii")


def unprotect_secret(secret):
    return dpapi(base64.b64decode(secret), False).hex()


def load_trusted():
    devices = load_json(TRUSTED_PATH, {})
    for device in devices.values():
        device["secret"] = unprotect_secret(device.pop("secret_protected"))
    return devices


trusted = load_trusted()
settings = load_json(SETTINGS_PATH, {"session_hours": 3})
session_hours = settings.get("session_hours", 3)
if (
    isinstance(session_hours, bool)
    or not isinstance(session_hours, (int, float))
    or not math.isfinite(session_hours)
    or not 0 <= session_hours <= MAX_SESSION_HOURS
):
    raise ValueError(f"settings.session_hours must be between 0 and {MAX_SESSION_HOURS}")
settings = {"session_hours": session_hours}
if not SETTINGS_PATH.exists():
    save_json(SETTINGS_PATH, settings)
identity = load_json(IDENTITY_PATH, {})
LAPTOP_ID = identity.get("id") or str(uuid.uuid4())
LAPTOP_NAME = identity.get("name") or socket.gethostname()
save_json(IDENTITY_PATH, {"id": LAPTOP_ID, "name": LAPTOP_NAME})


def save_trusted():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    records = {
        device_id: {
            **{k: v for k, v in device.items() if k != "secret"},
            "secret_protected": protect_secret(device["secret"]),
        }
        for device_id, device in trusted.items()
    }
    save_json(TRUSTED_PATH, records)


class Pairing:
    def __init__(self):
        self.codes = {}

    def new(self, ttl=120):
        now = time.time()
        self.codes = {code: expiry for code, expiry in self.codes.items() if expiry > now}
        code = secrets.token_urlsafe(24)
        self.codes[code] = now + ttl
        return code

    def consume(self, code):
        return self.codes.pop(code, 0) > time.time()


pairing = Pairing()
auth_failures = {}

BTN = {"left": Button.left, "right": Button.right, "middle": Button.middle}
MODS = {"ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift, "win": Key.cmd}
KEYS = {
    "enter": Key.enter, "backspace": Key.backspace, "tab": Key.tab, "esc": Key.esc,
    "space": Key.space, "delete": Key.delete, "home": Key.home, "end": Key.end,
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "pageup": Key.page_up, "pagedown": Key.page_down, "win": Key.cmd,
    "volup": Key.media_volume_up, "voldown": Key.media_volume_down,
    "mute": Key.media_volume_mute, "play": Key.media_play_pause,
    "next": Key.media_next, "prev": Key.media_previous,
}
KEYS.update({f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)})


def tap(k, mods=()):
    held = [MODS[m] for m in mods if m in MODS]
    for m in held:
        kb.press(m)
    try:
        key = KEYS.get(k, k if len(k) == 1 else None)
        if key is not None:
            kb.press(key)
            kb.release(key)
    finally:
        for m in reversed(held):
            kb.release(m)


def handle(m):
    t = m["t"]
    if t == "move":
        mouse.move(int(m["dx"]), int(m["dy"]))
    elif t == "click":
        mouse.click(BTN[m["b"]], int(m.get("n", 1)))
    elif t == "down":
        mouse.press(BTN[m["b"]])
    elif t == "up":
        mouse.release(BTN[m["b"]])
    elif t == "scroll":
        mouse.scroll(0, int(m["dy"]))
    elif t == "text":
        kb.type(m["s"])
    elif t == "key":
        tap(m["k"], m.get("mods", []))


def is_private_lan(address):
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


async def recv_json(ws, timeout=5):
    msg = await asyncio.wait_for(ws.receive(), timeout)
    if msg.type != WSMsgType.TEXT:
        raise ValueError("expected a text message")
    value = json.loads(msg.data)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


async def authenticate(ws):
    first = await recv_json(ws)
    if first.get("t") == "pair":
        device_id = first.get("device_id")
        if not isinstance(device_id, str) or not device_id or len(device_id) > 128:
            return None
        if not pairing.consume(first.get("code", "")):
            return None
        secret = secrets.token_hex(32)
        trusted[device_id] = {
            "name": str(first.get("device_name", "Phone"))[:80],
            "secret": secret,
            "paired": time.time(),
        }
        save_trusted()
        record_event("paired", trusted[device_id]["name"])
        await ws.send_json({"t": "paired", "secret": secret})
        return device_id, True
    if first.get("t") == "hello":
        device_id = first.get("device_id")
        device = trusted.get(device_id)
        if not device:
            return None
        nonce = secrets.token_hex(16)
        await ws.send_json({"t": "challenge", "nonce": nonce})
        reply = await recv_json(ws)
        expected = hmac.new(bytes.fromhex(device["secret"]), nonce.encode(), hashlib.sha256).hexdigest()
        if reply.get("t") != "auth" or not hmac.compare_digest(expected, str(reply.get("mac", ""))):
            return None
        return device_id, False
    return None


def record_event(event_type, name):
    global last_event
    last_event = {"type": event_type, "name": name, "ts": time.time()}


async def expire_session(ws, renew):
    hours = settings["session_hours"]
    if not hours:
        return
    while True:
        duration = hours * 3600
        await asyncio.sleep(max(duration - 60, 0))
        await ws.send_json({"t": "expiring", "seconds": 60})
        try:
            await asyncio.wait_for(renew.wait(), timeout=60)
        except asyncio.TimeoutError:
            await ws.send_json({"t": "expired"})
            await ws.close(code=4000, message=b"session expired")
            return
        renew.clear()


async def ws_handler(req):
    remote = req.remote or ""
    if not is_private_lan(remote):
        return web.Response(status=403, text="Private LAN clients only")
    failure = auth_failures.get(remote, {"count": 0, "until": 0})
    if failure["until"] > time.time():
        return web.Response(status=429, text="Too many failed authentication attempts")
    ws = web.WebSocketResponse(heartbeat=15)
    await ws.prepare(req)
    try:
        authentication = await authenticate(ws)
    except (asyncio.TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        authentication = None
    if not authentication:
        failure["count"] += 1
        if failure["count"] >= 5:
            failure = {"count": 0, "until": time.time() + 60}
        auth_failures[remote] = failure
        await ws.close(code=4401, message=b"authentication failed")
        return ws
    device_id, newly_paired = authentication
    auth_failures.pop(remote, None)
    device_name = trusted[device_id]["name"]
    if not newly_paired:
        record_event("connected", device_name)
    if device_id in trusted:
        trusted[device_id]["last_used"] = time.time()
        save_trusted()
    active_clients[ws] = device_id
    live_sockets.setdefault(device_id, set()).add(ws)
    await ws.send_json({"t": "ok", "session_hours": settings["session_hours"]})
    renew = asyncio.Event()
    timer = asyncio.create_task(expire_session(ws, renew))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                message = json.loads(msg.data)
                if not isinstance(message, dict):
                    raise ValueError("expected a JSON object")
                if message.get("t") == "renew":
                    renew.set()
                else:
                    handle(message)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                LOGGER.warning("Input error from %s: %s", device_name, error)
    finally:
        active_clients.pop(ws, None)
        connections = live_sockets.get(device_id)
        if connections:
            connections.discard(ws)
            if not connections:
                live_sockets.pop(device_id, None)
        timer.cancel()
        await asyncio.gather(timer, return_exceptions=True)
    return ws


def localhost_api(req):
    if req.remote != "127.0.0.1":
        raise web.HTTPForbidden(text="This API is available only on 127.0.0.1")


async def api_status(req):
    localhost_api(req)
    return web.json_response({
        "clients": len(active_clients),
        "uptime": max(0, time.time() - started_at),
        "last_event": last_event,
    })


async def api_trusted(req):
    localhost_api(req)
    return web.json_response([
        {"id": device_id, "name": device.get("name", "Phone"), "paired": device.get("paired")}
        for device_id, device in trusted.items()
    ])


async def api_revoke(req):
    localhost_api(req)
    try:
        body = await req.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text="Expected a JSON object with an id")
    device_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(device_id, str) or not device_id:
        raise web.HTTPBadRequest(text="A device id is required")
    device = trusted.pop(device_id, None)
    if device is None:
        raise web.HTTPNotFound(text="Trusted device not found")
    save_trusted()
    for ws in list(live_sockets.get(device_id, ())):
        await ws.close(code=4403, message=b"device revoked")
    return web.json_response({"revoked": device_id})


async def api_settings(req):
    localhost_api(req)
    try:
        body = await req.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text="Expected a JSON object with session_hours")
    hours = body.get("session_hours") if isinstance(body, dict) else None
    if (
        isinstance(hours, bool)
        or not isinstance(hours, (int, float))
        or not math.isfinite(hours)
        or not 0 <= hours <= MAX_SESSION_HOURS
    ):
        raise web.HTTPBadRequest(text=f"session_hours must be between 0 and {MAX_SESSION_HOURS}")
    settings["session_hours"] = hours
    save_json(SETTINGS_PATH, settings)
    return web.json_response(settings)


async def index(_):
    return web.Response(
        text="AirControl server is running. Use the AirControl phone app to connect.",
        content_type="text/plain",
    )


def localhost_only(req):
    try:
        return ipaddress.ip_address(req.remote).is_loopback
    except (ValueError, TypeError):
        return False


async def pair_page(req):
    if not localhost_only(req):
        return web.Response(status=403, text="Pairing is available only on this computer")
    code = pairing.new()
    payload = {
        "v": 1, "id": LAPTOP_ID, "name": LAPTOP_NAME, "host": lan_ip(),
        "port": PORT, "code": code,
    }
    import qrcode
    from qrcode.image.svg import SvgPathImage
    pairing_json = json.dumps(payload, separators=(",", ":"))
    qr = qrcode.make(pairing_json, image_factory=SvgPathImage)
    svg = qr.to_string(encoding="unicode")
    page = f"""<!doctype html><meta charset="utf-8"><title>Pair AirControl</title>
<style>body{{font:16px system-ui;max-width:36rem;margin:3rem auto;text-align:center}}svg{{width:min(80vw,22rem)}}</style>
<h1>Pair a phone</h1><p>Scan this QR code in the AirControl app within 2 minutes.</p>{svg}
<p>If scanning does not work, copy and paste this pairing JSON into the app:</p>
<textarea readonly onclick="this.select()" style="width:min(90vw,34rem);height:7rem;font:13px monospace">{html.escape(pairing_json)}</textarea>
<p>This pairing code is single-use and expires in 120 seconds.</p>"""
    return web.Response(text=page, content_type="text/html")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    LOGGER.info("AirControl server listening on port %s", PORT)
    LOGGER.info("Pair a phone at http://127.0.0.1:%s/pair", PORT)
    LOGGER.warning("Traffic is unencrypted; use only on a trusted private Wi-Fi network")
    app = web.Application()
    app.add_routes([
        web.get("/", index),
        web.get("/pair", pair_page),
        web.get("/ws", ws_handler),
        web.get("/api/status", api_status),
        web.get("/api/trusted", api_trusted),
        web.post("/api/revoke", api_revoke),
        web.post("/api/settings", api_settings),
    ])
    web.run_app(app, host="0.0.0.0", port=PORT, print=None, access_log=LOGGER)


if __name__ == "__main__":
    main()
