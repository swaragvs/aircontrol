# AirControl Android app

## Build and run

1. Install Node.js and Android Studio with an Android SDK.
2. From the project root, run `npm install`.
3. Start the laptop server with `python aircontrol.py`.
4. On the laptop, open `http://127.0.0.1:8765/pair` and scan its QR code in the app.
5. Run `npm run cap:sync`, then open the `android` folder in Android Studio and build/run the app.

The Android app connects to the saved laptop address and its last-known address. mDNS discovery and message encryption are planned for later phases. Until encryption is implemented, use AirControl only on a trusted private Wi-Fi network.

## Build the Windows tray app and installer

1. Install Python for Windows and Inno Setup.
2. From the project root, run `build_windows.bat`. It installs the packaging dependencies, creates `icon.ico`, and builds `dist\AirControl\AirControl.exe` with PyInstaller in onedir mode.
3. Open `AirControl.iss` in Inno Setup and compile it, or run `ISCC.exe AirControl.iss` from the project root.

### Manual build commands

```powershell
python -m pip install aiohttp pynput qrcode pystray pillow pyinstaller
python make_icon.py
python -m PyInstaller --noconfirm --clean --noconsole --onedir --name AirControl --icon icon.ico --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 tray.py
ISCC.exe AirControl.iss
```

The server management API listens on the same server port but only accepts requests from `127.0.0.1`. The Windows server log is `%APPDATA%\AirControl\server.log`; the tray log is `%APPDATA%\AirControl\tray.log`. The installer adds a Private-profile firewall rule and an autostart entry by default.

### Windows test checklist

1. Run `python tray.py`; confirm the tray icon appears and the server responds at `http://127.0.0.1:8765/api/status`.
2. Select **Pair new phone** and pair a phone from the local pairing page.
3. Confirm `/api/trusted` lists the device without exposing its pairing secret; reconnect from the phone.
4. Change the session limit to 1 hour. Confirm an idle server restarts after the limit, while an active phone connection prevents restart.
5. Revoke a trusted phone and confirm its active socket closes and it can no longer reconnect.
6. Build the executable and installer. Install, reboot, and confirm AirControl starts hidden in the tray.
7. Uninstall and confirm the firewall rule and autostart entry are removed.
