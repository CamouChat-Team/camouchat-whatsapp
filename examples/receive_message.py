"""
receive_message.py — Receive & Read Incoming Messages via CamouChat
====================================================================
Minimal demo for listening to incoming WhatsApp messages
using CamouChat's event-driven async architecture.

Prerequisites:
    pip install camouchat-whatsapp "camoufox[geoip]"
    python -m camoufox fetch        # one-time binary download

Usage:
    python receive_message.py
    (Press Ctrl+C to stop listening)
"""

import asyncio
from camouchat_browser import BrowserManager
from camouchat_whatsapp import WhatsAppClient
from camouchat_whatsapp.models import Message


async def on_message(message: Message) -> None:
    """Callback fired for every incoming message."""
    print(f"📩 New message from {message.sender}")
    print(f"   Content : {message.body}")
    print(f"   Time    : {message.timestamp}")
    print("-" * 40)


async def main():
    async with BrowserManager() as browser:
        client = WhatsAppClient(browser)
        await client.initialize()
        await client.wait_for_login()

        # Register the message handler
        client.on_message(on_message)

        print("👂 Listening for incoming messages... (Ctrl+C to stop)")
        # Keep the event loop running indefinitely
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped listening.")
