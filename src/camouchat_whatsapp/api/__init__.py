"""
WapiSession maintains all the other Core Internal Managers.
Managers :
    - ChatApiManager
    - MessageApiManager
    - CoreBridge
"""

from playwright.async_api import Page

from .managers import ChatApiManager, MessageApiManager
from .models import ChatModelAPI, MessageModelAPI
from .wa_js import WapiWrapper
from camouchat_whatsapp.logger import w_logger

__all__ = ["WapiSession", "ChatApiManager", "MessageApiManager", "WapiWrapper", "ChatModelAPI", "MessageModelAPI"]


# todo add logger later

class WapiSession:
    """
    WapiSession maintains all the other Core Internal Managers.
    """

    # Todo , Initiate WapiSession with weakref to maintain Obj Singleton
    def __init__(self, page: Page):
        self.page = page
        self.bridge = WapiWrapper(page)
        self.chat_manager = ChatApiManager(self.page, self.bridge)
        self.message_manager = MessageApiManager(self.bridge)
        self.log = w_logger
        self.is_ready = False

    async def start(self) -> None:
        """
        starts the wapi session and initiates the link & Message based Listeners Connections.
        """
        self.log.info("WapiSession starting...")
        flag = await self.bridge.wait_for_ready()

        if flag:
            self.is_ready = True
            await self.message_manager._setup_bridge()
            self.log.info("WapiSession is ready to use.")
        else:
            self.log.error("""
            Wapi Session failed to establish the connection. Please consider restarting the browser.
            If issuer persists consider creating a new profile.
            """)

    async def stop(self):
        """
        De-Auth the webpack connection & tear down all listeners.
        :return:
        """
        await self.message_manager.stop_bridge()
        self.is_ready = False
        self.log.info("WapiSession stopped successfully")
