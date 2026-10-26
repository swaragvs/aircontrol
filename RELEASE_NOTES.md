# AirControl 0.1.0 alpha

AirControl is an early alpha for testing a Windows tray app with an Android phone controller.

## Important security warning

**Traffic is not encrypted yet.** A person able to monitor your Wi-Fi network may be able to read control traffic, including typed text and keystrokes. Use this release only on trusted home Wi-Fi. Do not use public, shared, or untrusted networks.

## Platforms and known issues

- Windows PC and Android phone only.
- The Windows executable is unsigned, so SmartScreen or antivirus software may warn.
- SHA-256 checksums for the release files are attached as `SHA256SUMS.txt`.
- Google Play Services is needed for QR scanning; manual pairing is available.
- Windows lock screen, elevated UAC prompts, Fn, and hardware-specific brightness keys are not supported.
- The laptop must remain awake and reachable on the same Wi-Fi.

This release is experimental and may contain bugs. Please report issues in the repository's issue tracker.
