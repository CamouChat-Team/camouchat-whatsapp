from pydantic import BaseModel, Field


class MsgKeyModel(BaseModel):
    """Represents a WhatsApp message key identifier."""

    fromMe: bool | None = Field(
        default=None, description="Indicates if the message was sent by the authenticated user."
    )
    remote: str | None = Field(
        default=None, description="The JID of the chat where the message resides."
    )
    id: str | None = Field(
        default=None, description="The unique 32-character message identifier hash."
    )
    participant: str | None = Field(
        default=None, description="The JID of the sender in a group chat (None for 1-on-1 chats)."
    )
    id_serialized: str | None = Field(
        default=None,
        alias="_serialized",
        description="The fully qualified serialized message ID string.",
    )


class AckModelAPI(BaseModel):
    """
    Model representing an ACK update event payload.
    ACK values: 1=Sent, 2=Delivered, 3=Read, 4=Played.
    """

    ack: int = Field(
        description="The new acknowledgment status code (1=Sent, 2=Delivered, 3=Read, 4=Played)."
    )
    chat: str = Field(description="The JID of the chat where the event occurred.")
    sender: str | None = Field(
        default=None, description="The JID of the person who delivered/read the message."
    )
    ids: list[MsgKeyModel] = Field(
        default_factory=list, description="List of message keys that this ACK update applies to."
    )
