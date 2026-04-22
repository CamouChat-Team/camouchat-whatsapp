"""
Importing Only WAPI Wrapper, All functions requires this to fetch data of any Kind.
"""

from .wajs_scripts import WAJS_Scripts
from .wajs_wrapper import WapiWrapper

__all__ = ["WapiWrapper", "WAJS_Scripts"]
