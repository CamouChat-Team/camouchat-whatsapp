"""
send_message.py — Send a Text Message via CamouChat
=====================================================
Minimal demo for sending a single WhatsApp text message
to a given phone number using the CamouChat ecosystem.

Prerequisites:
    pip install camouchat-whatsapp "camoufox[geoip]"
    python -m camoufox fetch        # one-time binary download

Usage:
    Edit PHONE_NUMBER and MESSAGE below, then run:
        python send_message.py
"""

import asyncio
from camouchat_browser import BrowserManager
from camouchat_whatsapp import WhatsAppClient

# ── Configuration ─────────────────────────────────────────────────────────────
PHONE_NUMBER = "+91XXXXXXXXXX"   # International format, no spaces
MESSAGE = "Hello from CamouChat! 🦊"
# ──────────────────────────────────────────────────────────────────────────────


async def main():
    async with BrowserManager() as browser:
        client = WhatsAppClient(browser)
        await client.initialize()
        await client.wait_for_login()

        print(f"Sending message to {PHONE_NUMBER}...")
        await client.send_message(PHONE_NUMBER, MESSAGE)
        print(f"✅ Message sent successfully to {PHONE_NUMBER}")


if __name__ == "__main__":
    asyncio.run(main())
