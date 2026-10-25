import atexit
import importlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_previous_appdata = os.environ.get("APPDATA")
_test_appdata = tempfile.TemporaryDirectory(prefix="aircontrol-api-tests-")
os.environ["APPDATA"] = _test_appdata.name
sys.path.insert(0, str(PROJECT_ROOT))
aircontrol = importlib.import_module("aircontrol")


def cleanup_test_files():
    for handler in list(aircontrol.LOGGER.handlers):
        handler.close()
        aircontrol.LOGGER.removeHandler(handler)
    _test_appdata.cleanup()
    if _previous_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _previous_appdata
    sys.path.remove(str(PROJECT_ROOT))


atexit.register(cleanup_test_files)


class ManagementApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app_dir = Path(_test_appdata.name) / f"case-{id(self)}"
        self.app_dir.mkdir()
        aircontrol.APP_DIR = self.app_dir
        aircontrol.TRUSTED_PATH = self.app_dir / "trusted.json"
        aircontrol.SETTINGS_PATH = self.app_dir / "settings.json"
        aircontrol.settings = {"session_hours": 3}
        aircontrol.trusted.clear()
        aircontrol.active_clients.clear()
        aircontrol.live_sockets.clear()
        aircontrol.pairing.codes.clear()
        aircontrol.started_at = time.time()
        aircontrol.last_event = None

        app = web.Application()
        app.add_routes([
            web.get("/api/status", aircontrol.api_status),
            web.get("/api/trusted", aircontrol.api_trusted),
            web.post("/api/revoke", aircontrol.api_revoke),
            web.post("/api/settings", aircontrol.api_settings),
            web.get("/ws", aircontrol.ws_handler),
        ])
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        aircontrol.trusted.clear()
        aircontrol.active_clients.clear()
        aircontrol.live_sockets.clear()
        aircontrol.pairing.codes.clear()

    async def test_status_and_trusted_list_are_local_api_data(self):
        status = await (await self.client.get("/api/status")).json()
        self.assertEqual(status["clients"], 0)
        self.assertIsNone(status["last_event"])
        self.assertEqual(await (await self.client.get("/api/trusted")).json(), [])

        with self.assertRaises(web.HTTPForbidden):
            aircontrol.localhost_api(SimpleNamespace(remote="192.168.1.20"))

    async def test_settings_validate_and_persist_supported_values(self):
        response = await self.client.post("/api/settings", json={"session_hours": 1.5})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["session_hours"], 1.5)
        self.assertEqual(
            json.loads(aircontrol.SETTINGS_PATH.read_text(encoding="utf-8")),
            {"session_hours": 1.5},
        )

        for invalid in (-1, 8761, True, float("nan"), "3"):
            with self.subTest(session_hours=invalid):
                response = await self.client.post(
                    "/api/settings", json={"session_hours": invalid}
                )
                self.assertEqual(response.status, 400)

    async def test_revoke_removes_device_and_closes_its_live_socket(self):
        code = aircontrol.pairing.new()
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "t": "pair",
            "code": code,
            "device_id": "test-phone",
            "device_name": "Test Phone",
        })
        paired = await ws.receive_json()
        self.assertEqual(paired["t"], "paired")
        self.assertEqual((await ws.receive_json())["t"], "ok")

        listed = await (await self.client.get("/api/trusted")).json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], "test-phone")
        self.assertNotIn("secret", json.dumps(listed))
        self.assertEqual((await (await self.client.get("/api/status")).json())["clients"], 1)

        response = await self.client.post("/api/revoke", json={"id": "test-phone"})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["revoked"], "test-phone")
        self.assertEqual((await ws.receive(timeout=2)).type, WSMsgType.CLOSE)
        self.assertEqual(await (await self.client.get("/api/trusted")).json(), [])
        self.assertEqual((await (await self.client.get("/api/status")).json())["clients"], 0)
        await ws.close()


if __name__ == "__main__":
    unittest.main()
