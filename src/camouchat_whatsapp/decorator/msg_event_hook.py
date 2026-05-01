"""
msg_event_hook — the stealth message event decorator.

Wraps any async Python function so that it is called automatically
whenever a new WhatsApp message arrives, with the message already
normalized as a clean MessageModelAPI object.

Usage:
    from camouchat_whatsapp.decorator import on_newMsg, RegistryConfig
    from camouchat_whatsapp.api import WapiSession

    wapi = WapiSession(page)
    await wapi.start()

    # Simple usage — no storage
    @on_newMsg(wapi)
    async def on_message(msg) -> None:
        print(f"New message: {msg.body}")

    # With storage enabled
    @on_newMsg(wapi, config=RegistryConfig(profile=my_profile))
    async def on_message_stored(msg) -> None:
        print(f"Saved and received: {msg.body}")

    await on_message()          # registers the handler
"""

import asyncio
import functools
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from camouchat_browser import ProfileInfo

from camouchat_whatsapp.api import WapiSession

from .encrypt_hook import on_encrypt
from .storage_hook import on_storage


@dataclass
class RegistryConfig:
    """Configuration for on_newMsg decorator pipeline."""

    profile: ProfileInfo | None = None  # required for storage or encrypt
    store: bool = True  # enables DB storage if True AND profile is set
    encrypt: bool = False  # enables encryption if True (requires profile)


def on_newMsg(
    wapi_session: WapiSession,
    config: RegistryConfig | None = None,
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
    """
    Decorator factory that hooks into WhatsApp's real-time message stream.

    Config pipeline (applied in this order when config is set):
        1. storage  — wraps handler with on_storage if config.profile is set
        2. encrypt  — (future) wraps with encryption layer

    Args:
        wapi_session: A fully started WapiSession instance.
        config: Optional RegistryConfig to enable storage, encryption, etc.

    Returns:
        A decorator that, when called, returns a _register() coroutine.
        Await _register() to activate the handler.

    Raises:
        TypeError:    If the decorated function is not async.
        RuntimeError: If the message manager is missing.
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(
                f"@on_newMsg: '{func.__name__}' must be an async function. Got: {type(func)}"
            )

        handler = func

        if config is not None:
            if config.profile is not None and config.store:
                storage_decorator = on_storage(config.profile)
                handler = storage_decorator(handler)
            if config.encrypt:
                encrypt_decorator = on_encrypt(config.profile)
                handler = encrypt_decorator(handler)

        @functools.wraps(func)
        async def _register() -> None:
            """Registration coroutine — await this to activate the handler."""
            is_ready = wapi_session.is_ready
            if not is_ready:
                await wapi_session.start()

            msg_manager = wapi_session.message_manager
            if msg_manager is None:
                raise RuntimeError(
                    "@on_newMsg: wapi_session has no 'message_manager'. "
                    "Ensure WapiSession is fully initialised."
                )

            # Registers Handler internally
            msg_manager.register_handler(handler)

        return _register

    return decorator
