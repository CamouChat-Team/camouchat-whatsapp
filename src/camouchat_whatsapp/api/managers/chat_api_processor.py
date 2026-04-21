import asyncio
import json
import random
from collections.abc import Sequence
from logging import Logger, LoggerAdapter
from typing import Any

from camouchat_core import ChatProcessorProtocol, ChatProtocol
from playwright.async_api import Page

from camouchat_whatsapp.api.models import ChatModelAPI
from camouchat_whatsapp.api.wa_js import WAJS_Scripts, WapiWrapper
from camouchat_whatsapp.logger import w_logger

# todo , Add Auto logger later


class ChatApiManager(ChatProcessorProtocol[ChatModelAPI]):
    def __init__(
        self,
        page: Page,
        bridge: WapiWrapper,
        logger: Logger | LoggerAdapter | None = None,
    ) -> None:
        self.page = page
        self.ui_config = None
        self.log = logger or w_logger
        self._bridge = bridge
        self._last_opened_chat_id: str | None = None

    async def fetch_chats(self, **kwargs) -> Sequence[ChatModelAPI]:
        # Todo , add all the params into it & add docstring
        return await self.get_chat_list(**kwargs)

    async def open_chat(self, chat: ChatProtocol) -> bool:
        """
        Opens a WhatsApp chat with stealth-grade DOM reliability.

        Strategy (3-retry loop):
            1. JS scroll-into-view — scrolls #pane-side to expose the target row.
            2. Humanized mouse arc to estimated center (Camoufox humanize active).
            3. JS re-query after mouse travel — React may have re-rendered during arc.
            4. Micro-correction mouse.move (steps=3) + physical Playwright click.
               → isTrusted=true, coordinates match cursor position.
            5. WPP verify: read active chat JID (no side effects, no click flag).
            6. On 3 failures → mw: fire-and-forget WPP fallback (logged as anomaly).

        Notes:
            scrollIntoView is always required — even under Xvfb (virtual display).
            WhatsApp's chat list virtualizes DOM nodes based on the scroll container's
            CSS height, NOT the physical/virtual screen size. Off-screen nodes simply
            don't exist in the DOM. Xvfb gives a real display to the browser but does
            not change how React decides what to render. No Xvfb detection needed.
        """
        assert self.page is not None
        page = self.page

        if chat is None:
            raise ValueError("Chat is None, cannot open chat")

        # Design Decision: Ignore Newsletters/Channels - DOM interaction unstable
        if "@newsletter" in str(chat.id_serialized):
            self.log.warning(
                f"Skipping open_chat for {chat.id_serialized} — Newsletters/Channels "
                "not supported via DOM interaction."
            )
            return False

        # Fast path: ID cache + WPP verify
        if chat.id_serialized == self._last_opened_chat_id:
            self.log.debug(f"Chat {chat.id_serialized} matches last-opened cache.")
            return True

        name: str | None = getattr(chat, "formattedTitle", None)
        if not name:
            self.log.warning(
                f"No formattedTitle for {chat.id_serialized} — going direct to fallback."
            )
            return await self._wpp_open_fallback(chat)

        safe_title = json.dumps(name)  # handles apostrophes, quotes, emoji

        # ── JS helper: scroll into view + get row center ─────────────────────────
        _find_js = f"""() => {{
            const pane = document.getElementById('pane-side');
            if (!pane) return null;
            const title = {safe_title};
            const spans = pane.querySelectorAll('span[title]');
            for (const span of spans) {{
                if (span.title === title) {{
                    const row = span.closest('[role="listitem"]')
                                || span.closest('[data-testid="cell-frame-container"]')
                                || span;
                    // Scroll inside the WA pane container, not window
                    row.scrollIntoView({{ block: 'nearest', behavior: 'instant' }});
                    const r = row.getBoundingClientRect();
                    // Reject zero-size rects (off-screen or not yet rendered)
                    if (r.width === 0 || r.height === 0) return null;
                    return {{ cx: r.x + r.width / 2, cy: r.y + r.height / 2 }};
                }}
            }}
            return null;
        }}"""

        # ── 3-retry click loop ────────────────────────────────────────────────────
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            self.log.debug(f"open_chat attempt {attempt + 1}/{MAX_RETRIES} — '{name}'")

            # scroll into view + initial rect
            rect = await page.evaluate(_find_js)
            if rect is None:
                self.log.debug(f"'{name}' not in #pane-side DOM (attempt {attempt + 1})")
                await asyncio.sleep(0.1 * (attempt + 1))
                continue

            # humanized arc to estimated center (Camoufox humanize active)
            jitter = random.uniform(-12, 12)
            await page.mouse.move(rect["cx"] + jitter, rect["cy"] + jitter)
            await asyncio.sleep(random.uniform(0.08, 0.2))

            # re-query — React may have shifted the row during mouse travel
            rect2 = await page.evaluate(_find_js)
            if rect2 is None:
                self.log.debug(f"'{name}' vanished after mouse arc (attempt {attempt + 1})")
                await asyncio.sleep(0.15 * (attempt + 1))
                continue

            # micro-correction + physical isTrusted click
            await page.mouse.move(rect2["cx"], rect2["cy"], steps=3)
            await asyncio.sleep(random.uniform(0.05, 0.12))
            await page.mouse.click(rect2["cx"], rect2["cy"])

            # WPP verify (read-only)
            await asyncio.sleep(0.12)
            try:
                active_id = await self._bridge._evaluate_stealth(WAJS_Scripts.get_active_chat_id())
                if active_id == chat.id_serialized:
                    self._last_opened_chat_id = chat.id_serialized
                    self.log.debug(f"open_chat verified OK — '{name}' active.")
                    return True
                self.log.debug(
                    f"Verify miss: active={active_id!r} expected={chat.id_serialized!r} "
                    f"(attempt {attempt + 1})"
                )
            except Exception as e:
                self.log.debug(f"WPP verify failed (attempt {attempt + 1}): {e}")

            await asyncio.sleep(0.2 * (attempt + 1))

        self.log.warning(
            f"open_chat failed after {MAX_RETRIES} retries for '{name}' — WPP fallback."
        )
        return await self._wpp_open_fallback(chat)

    async def _wpp_open_fallback(self, chat: ChatProtocol) -> bool:
        """
        WPP fire-and-forget fallback for open_chat.
        Used when DOM click fails after MAX_RETRIES, or when formattedTitle is missing.
        Logs as anomaly — repeated use flags session (Monitor/Metrics layer).

        Uses mw: direct IIFE (not _evaluate_stealth) — same pattern as send_text_message.
        window.WPP was deleted by Smash & Grab, so we access via _wpp_key descriptor.
        """
        wpp_key = self._bridge._wpp_key
        self.log.warning(f"[ANOMALY] WPP fallback open for {chat.id_serialized} — log for Monitor.")
        # Ambient pointer drift before magical DOM change (humanize)
        await self.page.mouse.move(random.randint(150, 800), random.randint(150, 500))
        await asyncio.sleep(random.uniform(0.8, 1.5))
        try:
            await self.page.evaluate(
                f"mw:(() => {{"
                f"  const wpp = Object.getOwnPropertyDescriptor(window, '{wpp_key}')?.value;"
                f"  if (wpp) setTimeout(() => wpp.chat.openChatBottom('{chat.id_serialized}').catch(() => null), 0);"
                f"}})()"
            )
            self._last_opened_chat_id = chat.id_serialized
            return True
        except Exception as e:
            self.log.error(f"WPP fallback open failed for {chat.id_serialized}: {e}")
            return False

    # ──────────────────────────────────────────────
    # RAM BASED METHODS
    # ──────────────────────────────────────────────

    async def get_chat_by_id(self, chat_id: str) -> ChatModelAPI:
        """
        [Type: RAM]
        Fetch all the scalar data from React memory structured via ChatModelAPI.

        Args:
            chat_id: The @c.us or @g.us ID.
        Returns:
            ChatModelAPI containing the chat metadata.
        """
        if chat_id is None:
            raise ValueError("Chat ID is None, cannot get chat")
        raw_data = await self._bridge._evaluate_stealth(WAJS_Scripts.get_chat(chat_id))
        return ChatModelAPI.from_dict(raw_data)

    async def get_chat_list(
        self,
        count: int | None = None,
        direction: str = "after",
        only_users: bool = False,
        only_groups: bool = False,
        only_communities: bool = False,
        only_unread: bool = False,
        only_archived: bool = False,
        only_newsletter: bool = False,
        with_labels: list | None = None,
        anchor_chat_id: str | None = None,
        ignore_group_metadata: bool = True,
    ) -> Sequence[ChatModelAPI]:
        """
        [Type: RAM]
        Fetch a list of chats from ChatStore in sidebar order directly from React memory.

        Args:
            count:                  Max chats. None = all.
            direction:              'after' (default) or 'before' anchor_chat_id.
            only_users:             Only 1-on-1 personal chats.
            only_groups:            Only group chats.
            only_communities:       Only Community parent groups.
            only_unread:            Only chats with unread messages.
            only_archived:          Only archived chats.
            only_newsletter:        Only WhatsApp Channels.
            with_labels:            filters by label name/ID (Business accounts).
            anchor_chat_id:         Chat ID to paginate from.
            ignore_group_metadata:  Skip group member fetching (faster, True by default).

        Returns:
            List of structured ChatModelAPI objects, same order as WhatsApp sidebar.
        """
        raw_list = await self._bridge._evaluate_stealth(
            WAJS_Scripts.list_chats(
                count=count,
                direction=direction,
                only_users=only_users,
                only_groups=only_groups,
                only_communities=only_communities,
                only_unread=only_unread,
                only_archived=only_archived,
                only_newsletter=only_newsletter,
                with_labels=with_labels,
                anchor_chat_id=anchor_chat_id,
                ignore_group_metadata=ignore_group_metadata,
            )
        )
        return [ChatModelAPI.from_dict(c) for c in (raw_list or [])]

    # ──────────────────────────────────────────────
    # NETWORK BASED METHODS
    # ──────────────────────────────────────────────

    async def mark_is_read(self, chat_id: str) -> Any:
        """
        [Type: NETWORK] -- Only for Experimental bases.
        Force-mark a chat as read. Sends a network read-receipt to WhatsApp servers.
        Only call when using Tier 3 pure API mode.

        Args:
            chat_id: The chat to mark as read.
        """
        return await self._bridge._evaluate_stealth(WAJS_Scripts.mark_is_read(chat_id))
