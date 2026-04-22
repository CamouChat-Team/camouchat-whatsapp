import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camouchat_whatsapp.api.managers.msg_api_processor import MessageApiManager
from camouchat_whatsapp.api.models.message_api import MessageModelAPI


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge._evaluate_stealth = AsyncMock()
    bridge.setup_message_bridge = AsyncMock()
    bridge.poll_message_queue = AsyncMock()
    bridge.teardown_message_bridge = AsyncMock()
    return bridge


@pytest.mark.asyncio
async def test_message_manager_get_messages(mock_bridge):
    mm = MessageApiManager(mock_bridge)
    mock_bridge._evaluate_stealth.return_value = [{"id_serialized": "msg1"}]

    msgs = await mm.get_messages("chat1")
    assert len(msgs) == 1
    assert msgs[0].id_serialized == "msg1"


@pytest.mark.asyncio
async def test_message_manager_extract_media(mock_bridge):
    mm = MessageApiManager(mock_bridge)
    msg = MagicMock(spec=MessageModelAPI)
    msg.msgtype = "image"
    msg.id_serialized = "msg1"
    msg.directPath = "/some/path"
    msg.mimetype = "image/jpeg"
    msg.isViewOnce = False

    mock_bridge._evaluate_stealth.return_value = {
        "b64": base64.b64encode(b"hello").decode(),
        "isCached": True,
    }

    with patch("os.makedirs"), patch("builtins.open", MagicMock()):
        result = await mm.extract_media(msg, "/tmp/test.jpg")
        assert result["success"] is True
        assert result["size_bytes"] == 5
        assert result["used_fallback"] is False


@pytest.mark.asyncio
async def test_message_manager_listener_lifecycle(mock_bridge):
    mm = MessageApiManager(mock_bridge)

    # Setup bridge
    await mm._setup_bridge()
    assert mm._bridge_active is True
    mock_bridge.setup_message_bridge.assert_called_once()

    # Stop bridge
    await mm.stop_bridge()
    assert mm._bridge_active is False
    mock_bridge.teardown_message_bridge.assert_called_once()


@pytest.mark.asyncio
async def test_message_manager_handler_fanout(mock_bridge):
    mm = MessageApiManager(mock_bridge)
    handler1 = MagicMock()
    handler2 = AsyncMock()

    mm.register_handler(handler1)
    mm.register_handler(handler2)

    mock_bridge._evaluate_stealth.return_value = {"id_serialized": "msg1", "type": "chat"}

    await mm.__get_new_message__("msg1")

    handler1.assert_called_once()
    handler2.assert_called_once()


@pytest.mark.asyncio
async def test_message_manager_skip_own_msg(mock_bridge):
    mm = MessageApiManager(mock_bridge)
    handler = MagicMock()
    mm.register_handler(handler)

    # Own message (true_ prefix) and NOT recvFresh
    mock_bridge._evaluate_stealth.return_value = {"id_serialized": "true_msg1", "recvFresh": False}

    await mm.__get_new_message__("true_msg1")
    handler.assert_not_called()
