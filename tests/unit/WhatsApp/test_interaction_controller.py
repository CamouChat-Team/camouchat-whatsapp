"""
Unit tests for HumanInteractionController class.
Tests cover typing simulation, clipboard usage, and fallback mechanisms.
"""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from camouchat_whatsapp.core.web_ui_config import WebSelectorConfig
from camouchat_whatsapp.exceptions import WhatsAppInteractionError
from camouchat_whatsapp.features.interaction_controller import (
    InteractionController as HumanInteractionController,
)
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_page():
    page = AsyncMock(spec=Page)
    page.keyboard = AsyncMock()
    return page


@pytest.fixture
def mock_ui_config():
    config = Mock(spec=WebSelectorConfig)
    config.message_box.return_value = AsyncMock(spec=Locator)
    return config


@pytest.fixture
def humanize_fixture(mock_page, mock_logger, mock_ui_config):
    with patch(
        "camouchat_whatsapp.features.interaction_controller.pyperclip"
    ) as mock_clip:
        humanize = HumanInteractionController(
            page=mock_page, log=mock_logger, ui_config=mock_ui_config
        )
        yield humanize, mock_clip


# ============================================================================
# TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_init_page_none(mock_logger, mock_ui_config):
    with pytest.raises(ValueError, match="page must not be None"):
        HumanInteractionController(page=None, log=mock_logger, ui_config=mock_ui_config)


@pytest.mark.asyncio
async def test_typing_success_short(humanize_fixture):
    """Test typing short text uses keyboard typing."""
    humanize, mock_clip = humanize_fixture
    mock_source = AsyncMock(spec=Locator)
    mock_source.inner_text.return_value = "stale text"

    result = await humanize.type_text(text="Hello World", source=mock_source)

    assert result is True
    assert mock_source.click.call_count == 2
    mock_source.press.assert_any_call("Control+A")
    mock_source.press.assert_any_call("Backspace")
    humanize.page.keyboard.type.assert_called_with(
        text="Hello World", delay=pytest.approx(90, abs=10)
    )
    mock_clip.copy.assert_not_called()


@pytest.mark.asyncio
async def test_typing_success_long(humanize_fixture):
    """Test typing long text uses clipboard."""
    humanize, mock_clip = humanize_fixture
    mock_source = AsyncMock(spec=Locator)

    # Text > 50 chars
    long_text = "A" * 60 + "\n" + "B" * 60

    # Configure mock_clip to not fail
    mock_clip.copy = Mock()

    result = await humanize.type_text(text=long_text, source=mock_source)

    assert result is True

    assert mock_clip.copy.call_count == 4
    humanize.page.keyboard.press.assert_any_call("Control+V")
    humanize.page.keyboard.press.assert_any_call("Shift+Enter")  # Newline handling


@pytest.mark.asyncio
async def test_typing_timeout_fallback(humanize_fixture):
    """Test fallback to instant fill on timeout."""
    humanize, _ = humanize_fixture
    mock_source = AsyncMock(spec=Locator)
    mock_source.click.side_effect = PlaywrightTimeoutError("Timeout")

    result = await humanize.type_text(text="test", source=mock_source, send=True)

    assert result is True
    mock_source.fill.assert_called_with("test")
    humanize.page.keyboard.press.assert_called_with("Enter")


@pytest.mark.asyncio
async def test_instant_fill_success(humanize_fixture):
    """Test _Instant_fill works correctly."""
    humanize, _ = humanize_fixture
    mock_source = AsyncMock(spec=Locator)

    result = await humanize._Instant_fill(
        text="failover", source=mock_source, send=True
    )

    assert result is True
    mock_source.fill.assert_called_with("failover")
    humanize.page.keyboard.press.assert_called_with("Enter")


@pytest.mark.asyncio
async def test_instant_fill_failure(humanize_fixture):
    """Test _Instant_fill returns False on exception."""
    humanize, _ = humanize_fixture
    mock_source = AsyncMock(spec=Locator)
    mock_source.fill.side_effect = Exception("Fill Error")
    mock_source.fill.side_effect = PlaywrightTimeoutError("Time")

    with pytest.raises(WhatsAppInteractionError):
        await humanize._Instant_fill(text="failover", source=mock_source)


@pytest.mark.asyncio
async def test_typing_no_source(humanize_fixture):
    """Test typing raises error if source is None and message_box is not found."""
    humanize, _ = humanize_fixture
    humanize.ui_config.message_box.return_value = None
    with pytest.raises(WhatsAppInteractionError):
        await humanize.type_text(text="test", source=None)
