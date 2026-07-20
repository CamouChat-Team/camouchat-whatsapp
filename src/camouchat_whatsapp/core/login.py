"""WhatsApp Web login handler supporting QR and phone number authentication."""

from __future__ import annotations

import asyncio
import os
import random
import weakref
from logging import Logger, LoggerAdapter

from camouchat_browser import ProfileInfo
from camouchat_core import LoginProtocol
from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    Locator,
    Page,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from camouchat_whatsapp.exceptions import LoginError
from camouchat_whatsapp.logger import w_logger

from .web_ui_config import WebSelectorConfig


class Login(LoginProtocol):
    """Handles WhatsApp Web authentication via QR code or phone number."""

    _instances: weakref.WeakKeyDictionary[Page, Login] = weakref.WeakKeyDictionary()
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> Login:
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
        profile: ProfileInfo,
        ui_config: WebSelectorConfig | None = None,
        log: Logger | LoggerAdapter | None = None,
        **kwargs,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        if profile.is_active:
            w_logger.warning(
                "Already logged in for this profile. To create a new account login consider using a diff profile"
            )

        if ui_config is None:
            ui_config = WebSelectorConfig(page=page)

        self.page = page
        self.ui_config = ui_config
        self.profile = profile
        self.log = log or w_logger
        self._initialized = True

    async def is_login_successful(self, **kwargs) -> bool:
        """Verify if login was successful by checking for chat list visibility."""
        timeout: int = kwargs.get("timeout", 10_000)
        chats = self.ui_config.chat_list()
        try:
            await chats.wait_for(timeout=timeout, state="visible")
            return True
        except PlaywrightTimeoutError as e:
            raise TimeoutError("Timeout while checking for chat list.") from e

    @staticmethod
    def _is_docker() -> bool:
        """Return True when running inside a CamouChat Docker container."""
        return os.getenv("CAMOUCHAT_DOCKER") == "1"

    async def login(self, **kwargs) -> bool:
        """
        Authenticate to WhatsApp Web.

        Method is auto-detected from the runtime environment when not supplied:
        - Docker (CAMOUCHAT_DOCKER=1): phone code login (method=1) is forced.
          QR is impossible headless — no one can scan the screen.
        - Bare metal: defaults to phone code (method=1) unless method=0 passed.

        kwargs:
            method (int): 0 for QR, 1 for phone number.
                          Omit to let the environment decide.
            wait_time (int): QR scan timeout in ms (default: 180_000).
            url (str): WhatsApp Web URL.
            number (int | str): Phone number for code-based login.
                Falls back to env var WA_PHONE_NUMBER if omitted.
            country (str): Country name for phone login.
                Falls back to env var WA_COUNTRY if omitted.
        """
        in_docker = self._is_docker()

        number: int | str | None = (
            kwargs.get("number") or os.getenv("WA_PHONE_NUMBER")
        )
        country: str | None = (
            kwargs.get("country") or os.getenv("WA_COUNTRY")
        )
        wait_time: int = kwargs.get("wait_time", 180_000)
        link: str = kwargs.get("url", "https://web.whatsapp.com")

        # Resolve method
        if "method" not in kwargs:
            # Docker: QR is impossible headless — always use code login
            method = 1
            if in_docker:
                self.log.info(
                    "Docker environment detected — using phone code login. "
                    "Check docker logs for the pairing code."
                )
        else:
            method = int(kwargs["method"])
            if in_docker and method == 0:
                self.log.warning(
                    "method=0 (QR) is not usable in a Docker container "
                    "(no display to scan). Falling back to phone code login."
                )
                method = 1

        _max_retries = 3
        for _attempt in range(_max_retries):
            try:
                await self.page.goto(link, timeout=60_000)
                await self.page.wait_for_load_state("networkidle", timeout=50_000)
                break
            except PlaywrightTimeoutError as e:
                raise LoginError("Timeout while loading WhatsApp Web") from e
            except PlaywrightError as e:
                if "NS_BINDING_ABORTED" in str(e) and _attempt < _max_retries - 1:
                    self.log.warning(
                        "[Login] NS_BINDING_ABORTED on attempt %d/%d — retrying in 2s...",
                        _attempt + 1,
                        _max_retries,
                    )
                    await asyncio.sleep(2)
                    continue
                raise LoginError(f"Navigation failed: {e}") from e

        if method == 0:
            success = await self.__qr_login(wait_time)
        elif method == 1:
            success = await self.__code_login(number, country)
        else:
            raise LoginError(
                "Invalid login method. Use method=0 (QR) or method=1 (Code)."
            )

        if success:
            self.log.info(
                "WhatsApp login session stored via persistent context."
            )

        return success

    async def __qr_login(self, wait_time: int) -> bool:
        """Wait for user to scan QR code."""
        canvas = self.ui_config.qr_canvas()
        self.log.info("Waiting for QR scan (%s seconds)...", wait_time // 1000)

        try:
            await self.ui_config.chat_list().wait_for(timeout=wait_time, state="visible")
            if await canvas.is_visible():
                raise LoginError("QR not scanned within allowed time.")
            return True
        except PlaywrightTimeoutError as e:
            raise LoginError("QR login timeout.") from e

    async def __code_login(
        self, number: int | str | None, country: str | None
    ) -> bool:
        """Perform phone number based login with linking code."""
        if not number or not country:
            hint = (
                " Set WA_PHONE_NUMBER and WA_COUNTRY env vars."
                if self._is_docker()
                else " Pass number= and country= to login()."
            )
            raise LoginError(
                "Both number and country are required for code login." + hint
            )

        self.log.info("Starting code-based login...")

        btn = self.ui_config.link_phone_number_button()
        if await btn.count() == 0:
            raise LoginError("Login-with-phone-number button not found.")

        try:
            await btn.click(timeout=3000)
            await self.page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError as e:
            raise LoginError("Failed to open phone login screen.") from e

        ctl = self.ui_config.country_selector_button()
        if await ctl.count() == 0:
            raise LoginError("Country selector not found.")

        await ctl.click(timeout=3000)
        await self.page.keyboard.type(country, delay=random.randint(80, 120))
        await asyncio.sleep(1)

        countries: Locator = self.ui_config.country_list_items()
        if await countries.count() == 0:
            raise LoginError(f"No countries found for input: {country}")

        def normalize(name: str) -> str:
            """Normalize hte name"""
            return "".join(c for c in name if c.isalpha() or c.isspace()).lower().strip()

        target_country = normalize(country)
        selected = False

        for i in range(await countries.count()):
            el = countries.nth(i)
            name = normalize(await el.inner_text())
            if name == target_country:
                await el.click(timeout=3000)
                selected = True
                break

        if not selected:
            raise LoginError(f"Country '{country}' not selectable.")

        inp = self.ui_config.phone_number_input()
        if await inp.count() == 0:
            raise LoginError("Phone number input not found.")

        await inp.type(str(number), delay=random.randint(80, 120))
        await self.page.keyboard.press("Enter")

        code_el = self.ui_config.link_code_container()
        try:
            await code_el.wait_for(timeout=10_000)
            code = await code_el.get_attribute("data-link-code")
            if not code:
                raise LoginError("Login code missing.")
            self.log.info("WhatsApp Login Code: %s", code)
        except PlaywrightTimeoutError as e:
            raise LoginError("Timeout while waiting for login code.") from e

        return True
