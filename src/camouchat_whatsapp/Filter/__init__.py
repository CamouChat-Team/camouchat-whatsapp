"""
Message filtering utilities for camouchat.

Provides configurable filters to process, sort, and select
messages based on content, sender, timestamp, and custom criteria.
"""

from .message_filter import MessageFilter

__all__ = ["MessageFilter"]
