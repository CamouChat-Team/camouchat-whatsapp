"""WhatsApp media upload and download functionality."""

from __future__ import annotations

import asyncio
import os
import random
import re
import weakref
from logging import Logger, LoggerAdapter
from pathlib import Path
from typing import Any

from camouchat_browser import ProfileInfo
from camouchat_core import FileTyped, MediaControllerProtocol, MediaType
from playwright.async_api import (
    FileChooser,
    Locator,
    Page,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from camouchat_whatsapp.api import WapiSession
from camouchat_whatsapp.api.models import MessageModelAPI
from camouchat_whatsapp.core.web_ui_config import WebSelectorConfig
from camouchat_whatsapp.exceptions import WhatsAppError, WhatsappMediaError
from camouchat_whatsapp.logger import w_logger

# Todo add logger later.


# ── Media-type → category bucket ──────────────────────────────────────────────
_WA_TYPE_TO_CATEGORY: dict[str, str] = {
    "image": "image",
    "sticker": "image",
    "video": "video",
    "gif": "video",
    "audio": "audio",
    "ptt": "audio",
    "document": "document",
    "vcard": "document",
    "product": "document",
}

# Category → ProfileInfo attribute name for the save directory
_CATEGORY_TO_PROFILE_ATTR: dict[str, str] = {
    "image": "media_images_dir",
    "video": "media_videos_dir",
    "audio": "media_voice_dir",
    "document": "media_documents_dir",
}


class MediaController(MediaControllerProtocol[WebSelectorConfig]):
    """Handles media file uploads and downloads for WhatsApp chats.

    Upload (add_media):
        Works standalone — no wapi or profile required.

    Download (save_media):
        Requires both ``wapi`` (a started WapiSession) and ``profile``
        (a ProfileInfo instance) injected at construction time.
        Uses Cache API only — no CDN/network calls from our side.
        Retries every second until WA's render cycle caches the blob.
    """

    _instances: weakref.WeakKeyDictionary[Page, MediaController] = weakref.WeakKeyDictionary()
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> MediaController:
        page = kwargs.get("page") or (args[0] if args else None)
        if page is None:
            return super().__new__(cls)
        if page not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[page] = instance
        return cls._instances[page]

    def __init__(
        self,
        page: Page,
        ui_config: WebSelectorConfig | None = None,
        log: Logger | LoggerAdapter | None = None,
        wapi: WapiSession | None = None,
        profile: ProfileInfo | None = None,
        **kwargs,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.page = page
        self.ui_config = ui_config or WebSelectorConfig(page=page)
        self.log = log or w_logger
        if self.page is None:
            raise ValueError("page must not be None")
        self._wapi: WapiSession | None = wapi
        self._profile: ProfileInfo | None = profile
        self._initialized = True

    # ─────────────────────────────────────────────────────────────────────────
    # UPLOAD
    # ─────────────────────────────────────────────────────────────────────────

    async def menu_clicker(self) -> None:
        """Open the attachment menu."""
        try:
            menu_icon = await self.ui_config.plus_rounded_icon().element_handle(timeout=1000)

            if not menu_icon:
                raise WhatsappMediaError(
                    "Menu Locator return None/Empty / menu_clicker / MediaCapable"
                )

            await menu_icon.click(timeout=3000)
            await asyncio.sleep(random.uniform(1.0, 1.5))

        except PlaywrightTimeoutError as e:
            await self.page.keyboard.press("Escape", delay=0.5)
            raise WhatsappMediaError("Time out while clicking menu") from e

    async def add_media(self, file: FileTyped, **kwargs: Any) -> bool:
        """Upload a media file to the current chat."""
        mtype: Any = kwargs.get("mtype") or None
        if mtype is None:
            raise ValueError("mtype is None.")

        if not isinstance(mtype, MediaType):
            raise TypeError("mtype must be a MediaType")

        force = kwargs.get("force", False)
        await self.menu_clicker()
        self.log.debug("Menu Clicked.")

        try:
            target = await self._getOperational(mtype=mtype)
            if not await target.is_visible(timeout=3000):
                raise WhatsappMediaError("Attach option not visible")

            async with self.page.expect_file_chooser() as fc:
                await target.click(timeout=3000)
            chooser: FileChooser = await fc.value

            p_str = str(file.uri)
            if not await asyncio.to_thread(os.path.exists, p_str) or not await asyncio.to_thread(
                os.path.isfile, p_str
            ):
                raise WhatsappMediaError(f"Invalid file path: {file.uri}")

            abs_path = await asyncio.to_thread(os.path.abspath, p_str)
            await chooser.set_files(abs_path)
            if force:
                await asyncio.sleep(random.uniform(0.6, 1.0))
                try:
                    send_btn = self.page.get_by_role("button", name=re.compile(r"send", re.I)).last
                    await send_btn.click(timeout=4000)
                    self.log.debug("Media preview send button clicked.")
                except Exception:
                    # Fallback: simple Enter key press if button not found
                    await self.page.keyboard.press("Enter")
                    self.log.debug("Media preview closed via Enter key.")

            self.log.info(f" --- Sent {abs_path} , [Mtype] = [{mtype}] ")
            return True

        except PlaywrightTimeoutError as e:
            raise WhatsappMediaError("Timeout while resolving media option") from e

        except WhatsAppError as e:
            if isinstance(e, WhatsappMediaError):
                raise e
            raise WhatsappMediaError("Unexpected Error in add_media") from e

    async def _getOperational(self, mtype: MediaType) -> Locator:
        """Get the appropriate menu locator for the media type."""
        sc = self.ui_config
        if mtype in (MediaType.TEXT, MediaType.IMAGE, MediaType.VIDEO):
            self.log.debug("photo&Video locator selected")
            return sc.photos_videos()

        if mtype == MediaType.AUDIO:
            self.log.debug("Audio locator selected")
            return sc.audio()

        self.log.debug("Document locator selected")
        return sc.document()

    # ─────────────────────────────────────────────────────────────────────────
    # DOWNLOAD
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_save_dir(self, wa_type: str | None) -> Path:
        """Map a WhatsApp MsgType string to the correct ProfileInfo directory."""
        if self._profile is None:
            raise WhatsappMediaError(
                "save_media requires a ProfileInfo instance. "
                "Pass profile=<ProfileInfo> when constructing MediaCapable."
            )
        category = _WA_TYPE_TO_CATEGORY.get(wa_type or "", "document")
        attr = _CATEGORY_TO_PROFILE_ATTR[category]
        return getattr(self._profile, attr)

    async def save_media(
        self,
        message: MessageModelAPI,
        filename: str | None = None,
    ) -> str | None:
        """
        Download and save media from a MessageModelAPI message — Cache API only.

        XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        You Must set on the Auto-Media Download for all type of media inside
        the Camoufox's Browser WhatsApp to make it possible to download all types
        else may hit CDN , Use with caution.
        XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

        When open_chat renders the chat, WhatsApp Web downloads the encrypted
        media blob into the browser Cache API as part of its normal render cycle.
        This method retries the cache lookup every second for up to poll_secs
        seconds — zero CDN calls, zero network requests from our side.

        Args:
            message:   MessageModelAPI with MsgType, directPath, mediaKey.
            filename:  Optional filename override (basename, no directory).
                       If None, auto-generated as <type>_<safe_id><ext>.
            poll_secs: Max seconds to wait for WA to cache the blob (default 15).
                       Set to 1 to try exactly once without retrying.

        Returns:
            Absolute path string on success, or None if blob did not appear
            in cache within the poll window.

        Raises:
            MediaCapableError: If wapi or profile were not injected.
        """
        if self._wapi is None:
            raise WhatsappMediaError(
                "save_media requires a WapiSession. "
                "Pass wapi=<WapiSession> (after .start()) when constructing MediaCapable."
            )

        wa_type = message.msgtype or ""
        category = _WA_TYPE_TO_CATEGORY.get(wa_type, "document")
        save_dir = self._resolve_save_dir(wa_type)
        save_dir.mkdir(parents=True, exist_ok=True)

        raw: dict[str, Any] = {
            "type": wa_type,
            "directPath": message.directPath,
            "mediaKey": message.mediaKey,
            "id_serialized": message.id_serialized,
            "mimetype": message.mimetype,
            "viewOnce": message.isViewOnce or False,
        }

        # Debug: dump raw media fields so we can verify what arrived from JS bridge
        self.log.debug(
            f"[save_media] raw fields — "
            f"directPath={message.directPath!r} "
            f"mediaKey={'<set>' if message.mediaKey else None!r} "
            f"mimetype={message.mimetype!r} "
            f"id={message.id_serialized!r}"
        )

        save_path = (
            str(save_dir / filename)
            if filename
            else self._wapi.bridge.media_save_path(raw, str(save_dir))
        )

        result = await self._wapi.bridge.extract_media(
            message=raw,
            save_path=save_path,
        )

        path = result.get("path") if result.get("success") else None
        self.log.debug(f"[save_media] type={wa_type!r} category={category!r} path={path!r}")
        return path
