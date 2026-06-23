import asyncio
import contextlib
import inspect
from collections.abc import Callable
from logging import Logger, LoggerAdapter
from typing import Any

from camouchat_whatsapp.api.models import ActivityEventModel
from camouchat_whatsapp.api.wa_js import WapiWrapper
from camouchat_whatsapp.logger import w_logger


class ActivityApiManager:
    """Real-time activity and presence event manager.

    Uses the shared WapiWrapper poll infrastructure (setup_activity_bridge +
    poll_activity_queue) — no separate bridge layer or duplicate poll loops.
    A single combined _poll_and_drain_loop replaces the former separate
    _poll_loop / _drain_loop pair, eliminating the extra JS round-trip.

    Page reload recovery: if the page reloads the WapiWrapper
    _activity_bridge_active flag is reset to False, so the next call to
    _setup_bridge() will cleanly re-register the WPP listener without
    double-registering or silently failing.

    stop_bridge() behaviour: all registered @on_activity handlers are cleared
    when the bridge is torn down. Re-apply decorators before calling
    _setup_bridge() again if you need to resume listening.
    """

    def __init__(
        self,
        bridge: WapiWrapper,
        log: Logger | LoggerAdapter | None = None,
    ) -> None:
        self.log = log or w_logger
        self._bridge = bridge
        self._bridge_active: bool = False
        self._handlers: list[Callable[[ActivityEventModel], Any]] = []
        self._poll_drain_task: asyncio.Task | None = None

    def register_handler(self, callback: Callable[[ActivityEventModel], Any]) -> None:
        if callback not in self._handlers:
            self._handlers.append(callback)
            self.log.info(
                "ActivityApiManager: registered handler "
                f"'{getattr(callback, '__name__', repr(callback))}' "
                f"(total={len(self._handlers)})"
            )

    async def _setup_bridge(self) -> None:
        if self._bridge_active:
            self.log.warning("ActivityApiManager: bridge already active, skipping re-setup.")
            return

        await self._bridge.setup_activity_bridge()
        self._poll_drain_task = asyncio.ensure_future(self._poll_and_drain_loop())
        self._bridge_active = True
        self.log.info("ActivityApiManager: bridge active, ready to receive activity events.")

    async def _poll_and_drain_loop(self) -> None:
        """Single loop: poll the WapiWrapper queue and dispatch events inline.

        Collapses the former separate _poll_loop + _drain_loop into one loop,
        which means only one JS round-trip per 100 ms cycle instead of two.
        """
        while True:
            try:
                events = await self._bridge.poll_activity_queue()
                for event_data in events:
                    try:
                        await self._dispatch_event(event_data)
                    except Exception as exc:
                        self.log.error(f"ActivityApiManager: dispatch error: {exc}")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.log.error(f"ActivityApiManager: poll error: {exc}")
            await asyncio.sleep(0.1)

    async def _dispatch_event(self, event_data: dict[str, Any]) -> None:
        if not isinstance(event_data, dict):
            self.log.warning(f"ActivityApiManager: skipping non-dict event: {event_data!r}")
            return

        event = ActivityEventModel.from_dict(event_data)
        for handler in list(self._handlers):
            try:
                result = handler(event)
                # Use inspect.iscoroutinefunction (asyncio.iscoroutinefunction is
                # deprecated and will be removed in Python 3.16 — see PEP 780).
                if inspect.iscoroutinefunction(handler):
                    await result  # type: ignore[misc]
                elif asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                self.log.error(
                    "ActivityApiManager: handler "
                    f"'{getattr(handler, '__name__', '?')}' raised: {exc}"
                )

    async def stop_bridge(self) -> None:
        """Tear down the bridge and cancel the background task.

        .. warning::
            All handlers registered via ``register_handler()`` (including those
            applied with ``@on_activity``) are **cleared** when this method is
            called.  You must re-apply the decorator (or call
            ``register_handler()`` again) before starting the bridge again.
        """
        if self._poll_drain_task and not self._poll_drain_task.done():
            self._poll_drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_drain_task
        await self._bridge.teardown_activity_bridge()
        self._bridge_active = False
        self._handlers.clear()
        self.log.info("ActivityApiManager: bridge torn down, all handlers cleared.")
