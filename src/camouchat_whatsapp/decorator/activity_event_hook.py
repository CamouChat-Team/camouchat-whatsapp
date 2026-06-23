import functools
import inspect
from collections.abc import Callable, Coroutine
from typing import Any

from camouchat_whatsapp.api import WapiSession


def on_activity(
    wapi_session: WapiSession,
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
    """
    Decorator factory that hooks into WhatsApp real-time activity / presence events.

    Use this to drive notifications, online badges, typing indicators, and other
    UI feedback from the existing WA-JS presence stream.

    The check uses ``inspect.iscoroutinefunction`` instead of the deprecated
    ``asyncio.iscoroutinefunction`` (removed in Python 3.16).
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"@on_activity: '{func.__name__}' must be an async function.")

        @functools.wraps(func)
        async def _register() -> None:
            if not wapi_session.is_ready:
                await wapi_session.start()

            activity_manager = getattr(wapi_session, "activity_manager", None)
            if activity_manager is None:
                raise RuntimeError(
                    "@on_activity: wapi_session has no 'activity_manager'. "
                    "Ensure WapiSession is fully initialised."
                )

            activity_manager.register_handler(func)

        return _register

    return decorator
