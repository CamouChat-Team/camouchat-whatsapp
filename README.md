# CamouChat WhatsApp 🟢

High-stealth WhatsApp automation plugin for the CamouChat ecosystem. Built on top of `camouchat-browser` and `WA-JS`, providing a structured, API-driven pipeline for multi-account automation with end-to-end encrypted message storage.

> [!IMPORTANT]
> This package requires a **one-time binary fetch** for the underlying Camoufox browser engine after installation. See [Setup](#setup) below.

## Key Features

- **WA-JS Integration**: Uses the internal WhatsApp Web API via `wa-js` — not fragile DOM selectors.
- **Multi-Account Isolation**: Each account runs in a sandboxed profile with isolated cookies, storage, and fingerprints.
- **E2E Encryption**: All stored messages are encrypted at rest using AES-256-GCM.
- **Async-First**: Fully `asyncio`-native for high-throughput multi-session workloads.
- **Humanized Behavior**: Mouse movements, typing cadence, and delays mimic organic user behavior.
- **Rate Limiting**: Built-in configurable rate-limit support to prevent account bans.

## Installation

### Using `uv` (Recommended)

```bash
uv add camouchat-whatsapp "camoufox[geoip]"
```

### Using `pip`

```bash
pip install camouchat-whatsapp "camoufox[geoip]"
```

## Setup

> [!WARNING]  
> `uv sync` / `pip install` alone are **not enough**. You must fetch the Camoufox browser binary separately.

### With `uv`
```bash
uv run python -m camoufox fetch
```

### With `pip`
```bash
python -m camoufox fetch
```

This downloads the latest hardened Firefox binary used internally by [Camoufox](https://camoufox.com/).

## Quick Start

```python
import asyncio
from camouchat_browser import BrowserConfig, BrowserForge, ProfileManager
from camouchat_whatsapp import WhatsAppBot
from camouchat_core import Platform

async def main():
    pm = ProfileManager()
    profile = pm.create_profile(Platform.WHATSAPP, "my_account")

    config = BrowserConfig.from_dict({
        "platform": Platform.WHATSAPP,
        "headless": False,
        "locale": "en-US",
        "fingerprint_obj": BrowserForge(),
    })

    bot = WhatsAppBot(config=config, profile=profile)
    await bot.start()

asyncio.run(main())
```

## Anti-Ban Best Practices

- Use **residential proxies** and enable GeoIP matching.
- Run only **one visible browser** (others auto-switch to headless).
- Respect **rate limits** — avoid burst-sending messages.
- Use **test accounts** before deploying on real numbers.

## Documentation

- [WA-JS Integration](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/wa_js.md)
- [API Models & Managers](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/api_models.md)
- [Controllers (Login, Interaction, Media)](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/controllers.md)
- [Storage & Filtering](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/storage.md)
- [Core SDK](https://github.com/CamouChat-Team/camouchat-core)
- [Browser Plugin](https://github.com/CamouChat-Team/camouchat-browser)

## Security & Usage

### Acceptable Use
- Research & prototyping
- Personal automation
- Learning

### Prohibited Use
- Spam or bulk messaging
- WhatsApp ToS violations
- Harmful or malicious automation

### Best Practices
- Always use **test accounts** before deploying on real numbers
- Enable **rate limiting** to avoid burst-sending
- Use **residential proxies** with GeoIP matching
- Never store credentials in plaintext

### Data & Privacy
- Local-first — no telemetry, no external transmission
- Messages encrypted at rest with AES-256-GCM

### Disclaimer
- No guarantee of undetectability
- Not responsible for account bans or misuse

---

## Acknowledgements & Third-Party Code

CamouChat WhatsApp uses portions of the [wa-js](https://github.com/wppconnect-team/wa-js) library developed by the [WPPConnect Team](https://github.com/wppconnect-team).

`wa-js` provides the internal WhatsApp Web JavaScript bridge that powers reliable, selector-free automation. It is distributed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

See the [NOTICE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/NOTICE) file for full compliance details.

## License

MIT License. See [LICENSE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/LICENSE) for details.
