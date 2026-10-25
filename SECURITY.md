# Security policy

## Current release status

AirControl is an early alpha. Phone-to-PC WebSocket control traffic is not encrypted. A person who can monitor the local network may be able to observe control messages, including typed text and key events. Use AirControl only on a trusted private home network. Do not use it on public, shared, or otherwise untrusted Wi-Fi.

Pairing codes are short-lived and single-use, and reconnect authentication uses a challenge-response HMAC. These controls authenticate pairing/reconnection; they do not provide confidentiality for control traffic.

## Reporting a vulnerability

Please do not disclose an unpatched vulnerability publicly. Use GitHub's private vulnerability reporting for the AirControl repository when it is enabled, or contact the maintainers privately. Include affected versions, impact, and reproducible steps. Do not include real pairing secrets or personal data.

## Supported versions

Only the latest alpha is currently supported. This project does not yet make a security-support or response-time commitment.
