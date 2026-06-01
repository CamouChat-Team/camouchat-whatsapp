# CamouChat Examples

This directory contains minimal, well-commented starter scripts to help you get up and running with the CamouChat ecosystem quickly.

## Prerequisites

Install the full ecosystem and fetch the required Firefox binaries:

```bash
pip install camouchat-whatsapp "camoufox[geoip]"
python -m camoufox fetch
```

> ⚠️ `python -m camoufox fetch` is a **mandatory one-time step**. It downloads the compiled Camoufox Firefox binaries. The automation will not start without this.

---

## Examples

| File | What it does |
|---|---|
| `getting_started.py` | Launches a browser session, connects to WhatsApp Web, and verifies your setup is working |
| `send_message.py` | Sends a single text message to a given phone number |
| `receive_message.py` | Listens for incoming messages and prints them to the console |

---

## Running an Example

```bash
# 1. Basic setup verification
python getting_started.py

# 2. Send a message (edit PHONE_NUMBER and MESSAGE inside the file first)
python send_message.py

# 3. Listen for incoming messages (Ctrl+C to stop)
python receive_message.py
```

---

## Common Setup Errors

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: camouchat_browser` | Package not installed | Run `pip install camouchat-whatsapp` |
| `camoufox binaries not found` | `camoufox fetch` was skipped | Run `python -m camoufox fetch` |
| `BrowserManager failed to start` | Firefox binary missing or corrupted | Re-run `python -m camoufox fetch` |
| `QR code not appearing` | Display/headless environment issue | Ensure you're running in a GUI environment or use a VNC/display server |
| `Connection timeout on initialize()` | Slow network or WhatsApp Web outage | Retry after a moment; check your internet connection |

---

## Package Roles (Quick Reference)

- **`camouchat-core`** — Foundational interfaces, logging engine, and AES-256 encrypted storage contracts. Required by all other plugins.
- **`camouchat-browser`** — Stealth browser layer powered by Camoufox. Handles fingerprint spoofing, sandboxed profiles, and hardware profile generation.
- **`camouchat-whatsapp`** — WhatsApp-specific plugin. Bridges to WhatsApp Web via `wa-js`, zero DOM scraping, fully async.

For detailed API references, see the [main README](../README.md).
