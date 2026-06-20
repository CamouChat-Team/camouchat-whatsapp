from pydantic import BaseModel, Field

from .ack_api import MsgKeyModel


class RevokeModelAPI(BaseModel):
    """
    Model representing a message revoke event payload.
    """

    author: str | None = Field(
        default=None, description="The JID of the user who revoked the message."
    )
    from_jid: str = Field(
        alias="from", description="The JID of the chat where the revoke happened."
    )
    id: MsgKeyModel = Field(description="The key of the actual revoke protocol message itself.")
    refId: MsgKeyModel = Field(description="The key of the original message that was deleted.")
    to: str | None = Field(default=None, description="The recipient JID.")
    type: str = Field(description="Type of revoke, e.g., 'sender_revoke' or 'admin_revoke'.")
