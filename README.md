# CamouChat WhatsApp 🟢

> [!IMPORTANT]
> 🦊 **This is the CamouChat WhatsApp Plugin Repository.**
> If you are looking for the main CamouChat project or full ecosystem documentation, please visit our **[Central Repository](https://github.com/CamouChat-Team/CamouChat)**.

High-stealth WhatsApp automation plugin for the CamouChat ecosystem. Built on top of `camouchat-browser` and `WA-JS`, providing a structured, API-driven pipeline for multi-account automation with end-to-end encrypted message storage.

<p align="center">
  <a href="https://pypi.org/project/camouchat-whatsapp/">
      <img src="https://img.shields.io/badge/PyPI-camouchat--whatsapp-green" alt="PyPI" />
  </a>
  <a href="https://pepy.tech/projects/camouchat-whatsapp">
      <img src="https://static.pepy.tech/personalized-badge/camouchat-whatsapp?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" alt="PyPI Downloads" />
  </a>
  <a href="https://github.com/CamouChat-Team/camouchat-whatsapp/releases">
      <img src="https://img.shields.io/github/v/release/CamouChat-Team/camouchat-whatsapp?include_prereleases&label=Release&color=blue" alt="GitHub Release" />
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

## 🏆 Why Choose CamouChat?

The Python ecosystem has a few options for WhatsApp automation, but many are no longer actively maintained or lack support for modern, headless deployments. We believe in building in public and letting the data speak for itself.

Here is a live look at how CamouChat compares to the alternatives:

| Feature / Metric        | 🦊 CamouChat          | 📦 PyWhatKit          | 💬 whatsapp-python    |
|-------------------------|----------------------|----------------------|----------------------|
| **Last Commit**         | [![Last Commit](https://camo.githubusercontent.com/b480170a75183f3766fe8939072252452e4143e7adeda5c9662d4499de6f9057/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6c6173742d636f6d6d69742f424954532d526f6869742f43616d6f75436861743f7374796c653d666c61742d73717561726526636f6c6f723d73756363657373)](https://github.com/BITS-Rohit/CamouChat) | [![Last Commit](https://camo.githubusercontent.com/47896426c9d7fdb8554dd252d9a8e726fd1c55a4599ba67fd90e8ddce740ef20/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6c6173742d636f6d6d69742f416e6b6974343034627574666f756e642f5079576861744b69743f7374796c653d666c61742d737175617265)](https://github.com/Ankit404butfound/PyWhatKit) | [![Last Commit](https://camo.githubusercontent.com/7425b29d44d2c5e8c745ae3c1223029f517a0f79ed204641503b2a19c7137a97/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6c6173742d636f6d6d69742f6d756b756c686173652f77686174736170702d707974686f6e3f7374796c653d666c61742d737175617265)](https://github.com/mukulhase/whatsapp-python) |
| **Open Issues**         | [![Issues](https://camo.githubusercontent.com/033931882a0fe0eab27247d364791b83b2ae877b6e71b4142acca48df451fbf1/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6973737565732f424954532d526f6869742f43616d6f75436861743f7374796c653d666c61742d73717561726526636f6c6f723d73756363657373)](https://github.com/BITS-Rohit/CamouChat/issues) | [![Issues](https://camo.githubusercontent.com/0e8495cde8573f78376c33e3fdc3f9e8eaf1592def5fac4bbaad2797ae241f88/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6973737565732f416e6b6974343034627574666f756e642f5079576861744b69743f7374796c653d666c61742d737175617265)](https://github.com/Ankit404butfound/PyWhatKit/issues) | [![Issues](https://camo.githubusercontent.com/30d6ca3ce73b9b0b79009e96a799f44d7d6881ce1b7d3f478a195ac6a5cbfa13/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f6973737565732f6d756b756c686173652f77686174736170702d707974686f6e3f7374796c653d666c61742d737175617265)](https://github.com/mukulhase/whatsapp-python/issues) |
| **Headless Support**    | ✅ Native Support      | ❌ No                 | ⚠️ Partial             |
| **Async Support**       | ✅ Yes                | ❌ No                 | ❌ No                  |
| **Multi-Account Isolation** | ✅ Yes            | ❌ No                 | ❌ No                  |
| **E2E Encryption**      | ✅ Yes                | ❌ No                 | ❌ No                  |
| **Virtual Display (Xvfb)** | ✅ Native Support   | ❌ No                 | ⚠️ Partial             |
| **Docker Ready**        | ❌ No                 | ❌ No                 | ✅ Yes                 |
| **Rate Limiting**       | ❌ Manual              | ❌ No                 | ❌ No                  |

> *Note: Repository statistics are fetched live directly from the GitHub API.*


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
import base64
import os

from camouchat_browser import BrowserConfig, CamoufoxBrowser, ProfileManager
from camouchat_core import Platform, KeyManager, MessageDecryptor, MediaType
from camouchat_whatsapp import (
    Login,
    WapiSession,
    InteractionController,
    MediaController,
    MessageModelAPI,
    FileTyped,
    RegistryConfig,
    on_newMsg,
)

async def main():
    # 1. Profile
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="work")

    # 2. Browser
    config = BrowserConfig.from_dict({"platform": Platform.WHATSAPP, "headless": False})
    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()

    # 3. Login (reuses saved session automatically)
    login = Login(page=page, profile=profile)
    await login.login(method=0)

    # 4. API Controllers
    wapi = WapiSession(page=page)
    interaction = InteractionController(page=page, wapi=wapi)
    media = MediaController(page=page, wapi=wapi, profile=profile)

    # 5. Message Hook (Auto-Storage + E2E Encryption)
    registry = RegistryConfig(profile=profile, store=True, encrypt=True)

    @on_newMsg(wapi_session=wapi, config=registry)
    async def handle_message(msg: MessageModelAPI):
        # --- Decrypt message on-the-fly for command processing ---
        plain_body = msg.body
        if msg.encryption_nonce and msg.body:
            key_path = profile.encryption.get("key_file")
            if key_path:
                with open(key_path, "rb") as f:
                    raw_key = KeyManager.decode_key_from_storage(f.read().decode())
                try:
                    nonce_b = base64.b64decode(msg.encryption_nonce)
                    cipher_b = base64.b64decode(msg.body)
                    plain_body = MessageDecryptor(raw_key).decrypt_message(
                        nonce_b, cipher_b, msg.id_serialized or None
                    )
                except Exception as e:
                    print(f"Decryption failed: {e}")

        print(f"\n[+] New Msg from {msg.jid_From}: {plain_body}")

        # --- Command Handling ---
        if plain_body == "!ping":
            # API send (Zero DOM interaction - stealthy)
            await interaction.send_api_text(
                chat_id=msg.jid_From,
                text="🏓 Pong!",
                quoted_msg_id=msg.id_serialized,
            )

        elif plain_body and plain_body.startswith("!echo "):
            # Humanized DOM send (Simulates keyboard typing)
            echo_text = plain_body.replace("!echo ", "")
            await interaction.send_text(
                message=msg,
                text=f"Echo: {echo_text}",
                quote=True,
                send=True,
            )

        elif msg.msgtype in ("image", "video", "document"):
            # Media handling (Save & Re-upload)
            saved_path = await media.save_media(message=msg)
            if saved_path:
                print(f"[✔] Media saved to {saved_path}")

                # Re-upload the same media back
                mtype = MediaType.IMAGE if msg.msgtype == "image" else MediaType.DOCUMENT
                file_obj = FileTyped(uri=saved_path, name=os.path.basename(saved_path), mime_type=msg.mimetype)

                await media.add_media(mtype=mtype, file=file_obj, force=True)

    # 6. Activate listener and wait
    await handle_message()
    print("[\u2714] Hook active. Try sending !ping, !echo <text>, or an image in WhatsApp.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

## Anti-Ban Best Practices

- Use **residential proxies** and enable GeoIP matching.
- Run only **one visible browser** (others auto-switch to headless).
- Respect **rate limits** — avoid burst-sending messages.
- Use **test accounts** before deploying on real numbers.

## ⚠️ Important Beta Information

> [!WARNING]
> This package is currently in **BETA Version**. Errors and inconsistencies are expected.
> - It is **highly recommended** to use test accounts.
> - Start with **one browser** in **headed mode**.
> - Avoid using multi-account automation until the full **1.0.0 release**.

> [!CAUTION]
> **Rate Limiting Patterns**
>
> Rate limiting is currently a manual concern. An inbuilt limiter will be added in a future version with Monitor&Metrics insertion.
>
> Until then, ensure you manually rate limit inside your `@on_newMsg` handler to avoid account bans.

## Documentation

| Guide | Description |
|---|---|
| [WA-JS Integration](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/wa_js.md) | Bridge architecture, stealth engine, ChatStore sync caveats |
| [Core — Login & UI Config](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/core.md) | `Login` (QR + phone code), `WebSelectorConfig` |
| [Chat API Manager](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/chat_api.md) | `get_chat_list`, `open_chat`, all RAM/DOM methods |
| [Message API Manager](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/msg_api.md) | `get_messages`, `extract_media`, push listener |
| [Controllers](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/controllers.md) | `InteractionController`, `MediaController`, `send_api_text` |
| [Event Architecture](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/event_arch.md) | `@on_newMsg`, `@on_storage`, `@on_encrypt` decorator pipeline |
| [Storage](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/storage.md) | `SQLAlchemyStorage`, dialect config, `Query` retrieval layer |
| [API Models](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/docs/api_models.md) | `ChatModelAPI`, `MessageModelAPI` field reference |
| [Agent Reference](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/Agent.md) | 🤖 Full API surface + rules for AI agents / LLM tooling |
| [Core SDK](https://github.com/CamouChat-Team/camouchat-core) | `camouchat-core` protocol definitions |
| [Browser Plugin](https://github.com/CamouChat-Team/camouchat-browser) | `ProfileManager`, `BrowserConfig`, `CamoufoxBrowser` |

## Real-World Test Scripts

For complete, runnable integration examples see the test directories:

- **[E2E Scripts](https://github.com/CamouChat-Team/camouchat-whatsapp/tree/main/tests/E2E)** — full end-to-end integration tests covering message events, media, group operations, and command handling.
- **[Smoke Tests](https://github.com/CamouChat-Team/camouchat-whatsapp/tree/main/tests/smoke)** — lightweight bridge validation script that checks every API surface (messages, chats, groups, media, privacy, labels, newsletters) against a live session.

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
