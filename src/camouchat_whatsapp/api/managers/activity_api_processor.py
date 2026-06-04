import asyncio
import contextlib
from collections.abc import Callable
from logging import Logger, LoggerAdapter
from typing import Any

from camouchat_whatsapp.api.models import ActivityEventModel
from camouchat_whatsapp.api.wa_js import WapiWrapper
from camouchat_whatsapp.logger import w_logger


class ActivityApiManager:
    """Real-time activity and presence event manager."""

    def __init__(
        self,
        bridge: WapiWrapper,
        log: Logger | LoggerAdapter | None = None,
    ) -> None:
        self.page = None
        self.ui_config = None
        self.log = log or w_logger
        self._bridge = bridge
        self._bridge_active: bool = False
        self._handlers: list[Callable[[ActivityEventModel], Any]] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._drain_task: asyncio.Task | None = None
        self._poll_task: asyncio.Task | None = None

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
        self._drain_task = asyncio.ensure_future(self._drain_loop())
        self._poll_task = asyncio.ensure_future(self._poll_loop())
        self._bridge_active = True
        self.log.info("ActivityApiManager: DOM bridge active, ready to receive activity events.")

    async def _poll_loop(self) -> None:
        while True:
            try:
                events = await self._bridge.poll_activity_queue()
                for event in events:
                    await self._event_queue.put(event)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.log.error(f"ActivityApiManager: poll error: {exc}")

    async def _drain_loop(self) -> None:
        while True:
            try:
                event_data = await self._event_queue.get()
                try:
                    await self._dispatch_event(event_data)
                except Exception as exc:
                    self.log.error(f"ActivityApiManager: drain loop error: {exc}")
                finally:
                    self._event_queue.task_done()
            except asyncio.CancelledError:
                break

    async def _dispatch_event(self, event_data: dict[str, Any]) -> None:
        if not isinstance(event_data, dict):
            self.log.warning(f"ActivityApiManager: skipping non-dict event: {event_data!r}")
            return

        event = ActivityEventModel.from_dict(event_data)
        for handler in list(self._handlers):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                self.log.error(
                    "ActivityApiManager: handler "
                    f"'{getattr(handler, '__name__', '?')}' raised: {exc}"
                )

    async def stop_bridge(self) -> None:
        for task in (self._poll_task, self._drain_task):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await self._bridge.teardown_activity_bridge()
        self._bridge_active = False
        self._handlers.clear()
        self.log.info("ActivityApiManager: DOM bridge torn down, all handlers cleared.")