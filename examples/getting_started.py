"""
getting_started.py — CamouChat Basic Setup & Initialization
============================================================
This script walks you through the minimal setup required to launch
a CamouChat browser session and verify your installation is working.

Prerequisites:
    pip install camouchat-whatsapp "camoufox[geoip]"
    python -m camoufox fetch        # one-time binary download
"""

import asyncio
from camouchat_browser import BrowserManager
from camouchat_whatsapp import WhatsAppClient


async def main():
    print("[1/3] Initializing CamouChat browser session...")

    # BrowserManager handles stealth profile creation, fingerprint spoofing,
    # and sandboxed session storage automatically.
    async with BrowserManager() as browser:
        print("[2/3] Browser session started. Launching WhatsApp client...")

        # WhatsAppClient connects to WhatsApp Web via the internal wa-js bridge.
        # No DOM scraping — all interactions go through secure JS APIs.
        client = WhatsAppClient(browser)
        await client.initialize()

        print("[3/3] Setup complete! Your CamouChat session is ready.")
        print("      Scan the QR code in the browser window to log in.")

        # Keep session alive until QR is scanned and WhatsApp loads
        await client.wait_for_login()
        print("✅ Logged in successfully. CamouChat is ready to automate.")


if __name__ == "__main__":
    asyncio.run(main())
