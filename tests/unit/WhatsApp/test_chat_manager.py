from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camouchat_whatsapp.api.managers.chat_api_processor import ChatApiManager


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge._evaluate_stealth = AsyncMock()
    bridge._wpp_key = "secret_key"
    return bridge


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.evaluate = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.click = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_chat_manager_fetch_chats(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    mock_bridge._evaluate_stealth.return_value = [{"id_serialized": "123@c.us"}]

    chats = await cm.fetch_chats(count=10)
    assert len(chats) == 1
    assert chats[0].id_serialized == "123@c.us"
    mock_bridge._evaluate_stealth.assert_called_once()


@pytest.mark.asyncio
async def test_chat_manager_get_chat_by_id(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    mock_bridge._evaluate_stealth.return_value = {"id_serialized": "123@c.us"}

    chat = await cm.get_chat_by_id("123@c.us")
    assert chat.id_serialized == "123@c.us"


@pytest.mark.asyncio
async def test_chat_manager_open_chat_cached(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    cm._last_opened_chat_id = "123@c.us"
    chat = MagicMock()
    chat.id_serialized = "123@c.us"

    assert await cm.open_chat(chat) is True
    mock_page.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_chat_manager_open_chat_newsletter(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    chat = MagicMock()
    chat.id_serialized = "123@newsletter"

    assert await cm.open_chat(chat) is False


@pytest.mark.asyncio
async def test_chat_manager_open_chat_success(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    chat = MagicMock()
    chat.id_serialized = "123@c.us"
    chat.formattedTitle = "Test User"

    # Mock JS evaluations
    mock_page.evaluate.side_effect = [
        {"cx": 100, "cy": 100},  # _find_js 1
        {"cx": 100, "cy": 100},  # _find_js 2
        None,  # verification call to _evaluate_stealth? No, that's bridge
    ]
    mock_bridge._evaluate_stealth.return_value = "123@c.us"  # verification success

    assert await cm.open_chat(chat) is True
    assert cm._last_opened_chat_id == "123@c.us"


@pytest.mark.asyncio
async def test_chat_manager_open_chat_fallback(mock_page, mock_bridge):
    cm = ChatApiManager(mock_page, mock_bridge)
    chat = MagicMock()
    chat.id_serialized = "123@c.us"
    chat.formattedTitle = "Test User"

    # All 3 attempts fail to find rect
    mock_page.evaluate.return_value = None

    # Fallback success
    with patch.object(cm, "_wpp_open_fallback", return_value=True) as mock_fallback:
        assert await cm.open_chat(chat) is True
        mock_fallback.assert_called_once_with(chat)
