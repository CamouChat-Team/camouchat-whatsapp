"""
Introduces decorator based storage integration.
"""

# Later after this we will introduce StorageType in the ProfileInfo,
# as that will help us give more data & flexibility.

import asyncio
import functools
import inspect
from collections.abc import Callable, Coroutine
from typing import Any

from camouchat_browser import ProfileInfo
from camouchat_core import MessageProtocol

from camouchat_whatsapp.logger import w_logger
from camouchat_whatsapp.storage import SQLAlchemyStorage


def on_storage(profile: ProfileInfo) -> Callable:
    """
    Decorator factory that saves incoming messages to storage.
    """
    _ref = SQLAlchemyStorage.from_profile(profile=profile)

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"@on_storage: '{func.__name__}' must be async.")

        sig = inspect.signature(func)
        msg_param_name = None

        # First try: find param annotated with MessageProtocol
        for name, param in sig.parameters.items():
            if param.annotation == MessageProtocol:
                msg_param_name = name
                w_logger.debug(
                    f"@on_storage: '{func.__name__}' — "
                    f"MessageProtocol annotated param '{name}' found."
                )
                break

        # Fallback: use first positional param (handles unannotated handlers)
        if msg_param_name is None:
            params = list(sig.parameters.keys())
            if params:
                msg_param_name = params[0]
                w_logger.warning(
                    f"@on_storage: '{func.__name__}' — no MessageProtocol annotation found. "
                    f"Using first param '{msg_param_name}' as message. "
                    f"Tip: annotate it with 'msg: MessageProtocol' from camouchat_core "
                    f"for explicit resolution."
                )

        if msg_param_name is None:
            raise TypeError(
                f"@on_storage: '{func.__name__}' must have at least one parameter for the message."
            )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Lazy start if not already running
            if not getattr(_ref, "_initialized_", False):
                await _ref.start()

            # Bind arguments to find the message object
            bound = sig.bind(*args, **kwargs)
            msg_obj = bound.arguments.get(msg_param_name)

            if msg_obj:
                await _ref.enqueue_insert([msg_obj])

            return await func(*args, **kwargs)

        return wrapper

    def _get_storage() -> SQLAlchemyStorage:
        return _ref

    decorator.get_storage = _get_storage  # type: ignore
    return decorator
