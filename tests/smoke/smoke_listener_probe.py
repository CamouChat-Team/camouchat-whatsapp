"""
Smoke test to probe arbitrary WA-JS listeners and show their output.
This bypasses the decorators to test the raw WapiWrapper queue.
"""

import asyncio
import contextlib
import logging

from camouchat_browser import BrowserConfig, CamoufoxBrowser, ProfileManager
from camouchat_core import LoggerFactory, Platform

from camouchat_whatsapp import Login, WapiSession
from camouchat_whatsapp.api.wa_js.wajs_wrapper import WaJSEvents

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

    print(f"[*] Registering listener: {WaJSEvents.ACK}")
    await wapi.bridge.register_listener(WaJSEvents.ACK)

    print("[*] Polling for ACK events... Send a message from the host number!")
    try:
        while True:
            events = await wapi.bridge.drain_queue_for(WaJSEvents.ACK.event_name)
            for e in events:
                print("\n--- New ACK Event ---")
                print(e)
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("[*] Exiting probe.")
    finally:
        await CamoufoxBrowser.close_browser_by_profile(profile.profile_id)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
