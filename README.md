# CamouChat WhatsApp 🟢

> [!IMPORTANT]
> 🦊 **This is the CamouChat WhatsApp Plugin Repository.**
> If you are looking for the main CamouChat project or full ecosystem documentation, please visit our **[Central Repository](https://github.com/CamouChat-Team/CamouChat)**.

High-stealth WhatsApp automation plugin for the CamouChat ecosystem. Built on top of `camouchat-browser` and `WA-JS`, providing a structured, API-driven pipeline for multi-account automation with end-to-end encrypted message storage.

<p align="center">
  <a href="https://pypi.org/project/camouchat-whatsapp/">
      <img src="https://img.shields.io/pypi/v/camouchat-whatsapp?label=camouchat-whatsapp&color=green" />
  </a>
  <a href="https://pepy.tech/projects/camouchat-whatsapp">
      <img src="https://static.pepy.tech/personalized-badge/camouchat-whatsapp?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" alt="PyPI Downloads" />
  </a>
  <a href="https://opensource.org/licenses/MIT">
      <img src="https://img.shields.io/badge/License-MIT-yellow.svg" />
  </a>
</p>

> [!WARNING]
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

from camouchat_browser import BrowserConfig, BrowserForge, CamoufoxBrowser, ProfileManager
from camouchat_core import Platform
from camouchat_whatsapp import (
    Login,
    WebSelectorConfig,
    WapiSession,
    InteractionController,
    MessageModelAPI,
    on_newMsg,
)

async def main():
    # 1. Profile
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="my_account")

    print("Location of saved DIR cookies : ", profile.cache_dir)

    # 2. Browser
    config = BrowserConfig.from_dict({
        "platform": Platform.WHATSAPP,
        "headless": False,
        "locale": "en-US",
        "fingerprint_obj": BrowserForge(),
    })
    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()

    # 3. Login (reuses saved session automatically)
    ui = WebSelectorConfig(page=page)
    login = Login(page=page, UIConfig=ui)
    await login.login(method=0)

    # 4. Message event hook
    wapi = WapiSession(page=page)
    interaction = InteractionController(page=page, ui_config=ui, wapi=wapi)

    cm = wapi.chat_manager

    @on_newMsg(wapi_session=wapi)
    async def handle_message(msg: MessageModelAPI):
        print(f"New message from {msg.jid_From}: {msg.body}")

        # open chat & send msg .
        print(f"Opening Chat... [{msg.author}]")
        chat_id = msg.jid_From # jid is internal WhatsApp used ID system , and _from tells from which chat this came on, so jid_from -> msg came from which chat.
        chat = await cm.get_chat_by_id(chat_id=chat_id)
        await cm.open_chat(chat= chat)

        if msg.body == "!ping":
            await interaction.send_api_text(
                chat_id=msg.jid_From,
                text="🏓 Pong!",
                quoted_msg_id=msg.id_serialized,
            )

    await handle_message()   # start listening
    await asyncio.sleep(3600)  # keep alive


if __name__ == "__main__":
    try :
        asyncio.run(main())
    except KeyboardInterrupt :
        pass
    except Exception  :
        import tracemalloc
        tracemalloc.print_exc()

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

## ⚖️ Security & Ethics

CamouChat's strict policy regarding acceptable automation, anti-spam, and stealth disclaimers can be found in our central ecosystem hub:

👉 **[SECURITY.md](https://github.com/CamouChat-Team/CamouChat/blob/main/SECURITY.md)**

---

## Acknowledgements & Third-Party Code

CamouChat WhatsApp uses portions of the [wa-js](https://github.com/wppconnect-team/wa-js) library developed by the [WPPConnect Team](https://github.com/wppconnect-team).

`wa-js` provides the internal WhatsApp Web JavaScript bridge that powers reliable, selector-free automation. It is distributed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

See the [NOTICE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/NOTICE) file for full compliance details.

## License

MIT License. See [LICENSE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/LICENSE) for details.
