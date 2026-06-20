from typing import Any

from pydantic import BaseModel, Field


class EditModelAPI(BaseModel):
    """
    Model representing a message edit event payload.
    """

    chat: str = Field(description="The JID of the chat where the message was edited.")
    id: str = Field(description="The serialized ID of the edited message.")
    msg: dict[str, Any] = Field(
        description="The full raw dictionary of the updated message, ready to be parsed by MessageModelAPI."
    )
