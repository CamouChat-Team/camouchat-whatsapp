"""
Contains new API Models for WhatsApp.
"""

from .ack_api import AckModelAPI
from .chat_api import ChatModelAPI
from .edit_api import EditModelAPI
from .message_api import MessageModelAPI
from .revoke_api import RevokeModelAPI

__all__ = ["ChatModelAPI", "MessageModelAPI", "AckModelAPI", "RevokeModelAPI", "EditModelAPI"]
