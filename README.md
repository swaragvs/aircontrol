# AirControl

**Use your phone as an air mouse, touchpad and keyboard for your Windows PC.**

> **Early alpha:** AirControl is experimental software. LAN control traffic is not encrypted. Use it only on a trusted home Wi-Fi network; do not use it on public, shared, or untrusted networks.

## Screenshots

Screenshots coming soon.

## Features

- Air-mouse control using phone tilt, plus touchpad and keyboard input.
- Pair an Android phone once using a short-lived QR code or manual pairing data.
- Save trusted phones on the PC and revoke their access from the tray menu.
- Set a session expiration limit, including an option to disable expiration.
- A Windows notification-area app supervises the local control server.

## How it works

The Windows tray app starts a local server and displays the laptop's pairing page. Scan its QR code with AirControl on Android. The phone stores a trusted pairing credential and reconnects to that laptop. The tray app provides session-limit, autostart, and trusted-device controls.

Both devices must be on the same private Wi-Fi network. Pairing is restricted to the laptop itself and the management API accepts loopback requests only. These controls do **not** encrypt the phone-to-PC WebSocket traffic.

## Install

### Windows

Download and run the Windows installer from the alpha release. The installer adds an inbound firewall rule for Private networks and can start AirControl at sign-in. The executable is unsigned; Windows SmartScreen or antivirus software may warn about it.

### Android

Download the APK from the alpha release, allow installation from the source you used, and install it. Google Play Services is required for QR scanning; if it is unavailable, use the manual pairing-data fallback.

## Build from source

### Windows tray app

Requirements: Windows, Python 3.11 or newer, and Inno Setup.

1. Run `build_windows.bat` from the project root to build `build\windows-dist\AirControl\AirControl.exe`.
2. Compile `AirControl.iss` using Inno Setup to create `dist\AirControl-Setup.exe`.

The release workflow builds both deliverables when a `v*` tag is pushed. A manual `workflow_dispatch` run builds and uploads artifacts without publishing a GitHub release. Before running the Android release build, generate a dedicated Android release keystore outside the repository and back it up securely; a lost key prevents future Android updates. Configure these GitHub Actions repository secrets yourself:

- `KEYSTORE_B64`
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

Never commit the keystore or put its contents/passwords in source code, chat, or issue reports. The workflow intentionally fails rather than publishing an unsigned release when these secrets are missing.

### Android APK using Docker

Requirements: Docker Desktop configured for Linux containers.

Run `build_apk.bat` from the project root. The script builds the Android app in Docker and writes `dist\app-debug.apk`; Gradle downloads are cached in the Docker volume `aircontrol-gradle`. The debug APK is for testing, not a production-signed release. For repeat installs, keep the generated `.android-keys` directory private and backed up; never commit it.

Equivalent PowerShell command from the project root:

```powershell
$project = (Get-Location).Path
docker run --rm `
  -v "${PWD}:/workspace" `
  -v aircontrol-gradle:/root/.gradle `
  -v "${PWD}\.android-keys:/root/.android" `
  -w /workspace `
  -e "NODE_OPTIONS=--experimental-strip-types" `
  aircontrol-android-builder `
  bash -lc "npm ci && npm run build && npx cap sync android && cd android && chmod +x gradlew && ./gradlew assembleDebug --no-daemon --stacktrace && mkdir -p /workspace/dist && cp app/build/outputs/apk/debug/app-debug.apk /workspace/dist/app-debug.apk"
```

If Gradle stalls or runs out of memory, raise the Docker Desktop/WSL memory limit to about 6 GB and retry.

## Use

1. Start AirControl on Windows, then choose **Pair new phone** from its tray menu.
2. In the Android app, scan the displayed QR code or paste the pairing data.
3. Hold the air-mouse pad and tilt the phone to steer. Tap **Re-center** to set a new neutral pose without releasing the pad.
4. Use the tray menu to set a session limit or revoke a phone.

The laptop must remain awake and signed in. AirControl does not control the Windows lock screen or elevated UAC prompts. The Fn key is handled by laptop hardware and cannot be sent as a software key.

## Known limitations and security

- **Unencrypted LAN traffic (alpha):** control messages, including typed text and keystrokes, can be observed by someone able to monitor the same network. Use trusted home Wi-Fi only. Network isolation and encryption are planned; do not assume pairing or HMAC reconnect authentication encrypts control data.
- Windows PC and Android phone only.
- The laptop must be awake, signed in, and reachable on the same network.
- Windows lock screen and elevated UAC prompts cannot be controlled.
- Unsigned Windows binaries may trigger SmartScreen or antivirus warnings.
- QR scanning requires Google Play Services; manual pairing is available as a fallback.
- The Fn key and hardware-specific brightness keys cannot be sent as software key events.
- Wi-Fi client/AP isolation can prevent the phone from reaching the laptop.

See [SECURITY.md](SECURITY.md) for reporting security issues and additional details.

## Troubleshooting

- Confirm both devices use the same private Wi-Fi network and the Windows network profile is Private.
- Allow AirControl through Windows Firewall on Private networks.
- Check that the router does not enable AP/client isolation between wireless devices.
- If QR scanning cannot download its Google scanner module, connect to the internet and use manual pairing as an alternative.
- If the app cannot reconnect, ensure the laptop is awake and the trusted phone has not been revoked.

## Roadmap

- Encrypt the complete control connection.
- Discover laptops automatically with mDNS.
- iOS and macOS support.

## License

AirControl is licensed under the MIT License; see [LICENSE](LICENSE). Third-party component notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The Google ML Kit scanner is subject to Google's terms.
