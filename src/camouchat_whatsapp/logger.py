from typing import Optional, Union
from camouchat_core import LoggerFactory


def get_whatsapp_logger(
    name: str, profile_id: str = "GLOBAL", level: Optional[Union[int, str]] = None
):
    """Returns a logger specialized for WhatsApp operations."""
    return LoggerFactory.get_logger(
        name=name, platform="WHATSAPP", profile_id=profile_id, level=level
    )


# Default logger for the module
w_logger = get_whatsapp_logger("whatsapp_init")
