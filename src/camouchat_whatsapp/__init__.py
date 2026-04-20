"""
WhatsApp platform integration for CamouChat.

Provides chat processing, message handling, media operations,
and human-like interaction capabilities for WhatsApp Web automation.
"""

# Public API imports (runtime)

# Wajs
# API models
# API Manager layer
from .api import (
    ChatApiManager,
    ChatModelAPI,
    MessageApiManager,
    MessageModelAPI,
    WapiSession,
    WapiWrapper,
)

# Controllers (interaction layer)
from .core import Login, WebSelectorConfig

# Utils
from .decorator import on_newMsg, RegistryConfig
from .features import FileTyped, InteractionController, MediaController, MediaType
from .filters import MessageFilter

# Infrastructure
from .storage import SQLAlchemyStorage

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
    "RegistryConfig",
    "MessageFilter",
]
