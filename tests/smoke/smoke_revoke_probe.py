"""
Smoke test to probe chat.msg_revoke WA-JS listener and show its raw output.
"""

import asyncio
import contextlib
import logging

from camouchat_browser import BrowserConfig, CamoufoxBrowser, ProfileManager
from camouchat_core import LoggerFactory, Platform

from camouchat_whatsapp import Login, WapiSession
from camouchat_whatsapp.api.wa_js.wajs_wrapper import EventName, WaJSEvents

LOG_LEVEL = logging.INFO
LoggerFactory.set_level(LOG_LEVEL)


async def main():
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="work")
    config = BrowserConfig.from_dict({"platform": Platform.WHATSAPP, "headless": False})

    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()

    login = Login(page=page, profile=profile)
    await login.login(method=0)

    wapi = WapiSession(page=page)
    await wapi.bridge.wait_for_ready()

    print(f"[*] Registering listener: {WaJSEvents.REVOKE}")
    await wapi.bridge.register_listener(WaJSEvents.REVOKE)

    print("[*] Polling for REVOKE events... Delete a message for everyone in WhatsApp!")
    try:
        while True:
            events = await wapi.bridge.drain_queue_for(EventName.REVOKE_EVENT)
            for e in events:
                print("\n--- New REVOKE Event ---")
                print(e)
            await asyncio.sleep(1)
    finally:
        await CamoufoxBrowser.close_browser_by_profile(profile.profile_id)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
