"""
WhatsApp platform integration for CamouChat.

Provides chat processing, message handling, media operations,
and human-like interaction capabilities for WhatsApp Web automation.
"""

# Public API imports (runtime)

# API models
from .api import ChatModelAPI, MessageModelAPI

# API Manager layer
from .api import MessageApiManager, ChatApiManager

# Controllers (interaction layer)
from .core import Login, WebSelectorConfig
from .features import MediaController, InteractionController

# Infrastructure
from .storage import SQLAlchemyStorage

# Utils
from .decorator import on_newMsg
from .filters import MessageFilter


__all__ = [
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

    # Infra
    "SQLAlchemyStorage",

    # Utils
    "on_newMsg",
    "MessageFilter",
]