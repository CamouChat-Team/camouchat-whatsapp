import asyncio

from camouchat_browser import BrowserConfig, CamoufoxBrowser, ProfileManager
from camouchat_core import MessageProtocol, Platform

from camouchat_whatsapp import Login, RegistryConfig, WapiSession, on_newMsg

pm = ProfileManager()
config = BrowserConfig.from_dict(
    {"platform": Platform.WHATSAPP, "headless": False}  # Rest can be set by default.
)
work = pm.create_profile(platform=Platform.WHATSAPP, profile_id="work")


async def main():
    browser = CamoufoxBrowser(config=config, profile=work)
    page = await browser.get_page()

    login = Login(page=page, profile=work)
    await login.login(method=0)  # Auto Handles saved Persistence.

    wapi = WapiSession(page=page)
    await wapi.start()

    # Simple usage — no storage
    @on_newMsg(wapi)
    async def on_message(msg: MessageProtocol) -> None:
        print(f"New message: {msg.body}")

    # With storage enabled
    @on_newMsg(wapi, config=RegistryConfig(store=True, profile=work))
    async def on_message_stored(msg: MessageProtocol) -> None:
        print(f"Saved and received: {msg.body}")

    @on_newMsg(wapi, config=RegistryConfig(profile=work, encrypt=True))
    async def on_message_encrypted(msg: MessageProtocol) -> None:
        print(f"Encrypted and received: {msg.body}")

    @on_newMsg(wapi, config=RegistryConfig(profile=work, encrypt=True))
    async def on_message_encrypted_storage(msg: MessageProtocol) -> None:
        print(f"Encrypted and stored: {msg.body}")

    await on_message()  # registers the simple handler
    await on_message_stored()  # registers the storage handler
    await on_message_encrypted()  # registers the encrypted handler
    await on_message_encrypted_storage()  # registers the encrypted and storage handler

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc()
    finally:
        asyncio.run(pm.close_profile(profile=work))
