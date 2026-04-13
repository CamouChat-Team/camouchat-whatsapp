"""
WhatsApp platform integration for CamouChat.

Provides chat processing, message handling, media operations,
and human-like interaction capabilities for WhatsApp Web automation.
"""

# Public API imports (runtime)

# Wajs
from .api import WapiSession, WapiWrapper

# API models
from .api import ChatModelAPI, MessageModelAPI

# API Manager layer
from .api import MessageApiManager, ChatApiManager

# Controllers (interaction layer)
from .core import Login, WebSelectorConfig
from .features import MediaController, InteractionController, MediaType, FileTyped

# Infrastructure
from .storage import SQLAlchemyStorage

# Utils
from .decorator import on_newMsg
from .filters import MessageFilter

__all__ = [
    # wajs
    "WapiSession",
    "WapiWrapper",
    # API models
    "ChatModelAPI",
    "MessageModelAPI",
    # API Managers
    "ChatApiManager",
    "MessageApiManager",
    # Controllers
    "Login",
    "WebSelectorConfig",
    "MediaController",
    "InteractionController",
    "MediaType",
    "FileTyped",
    # Infra
    "SQLAlchemyStorage",
    # Utils
    "on_newMsg",
    "MessageFilter",
]
