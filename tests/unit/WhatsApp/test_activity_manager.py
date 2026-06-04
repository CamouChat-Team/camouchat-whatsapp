from unittest.mock import AsyncMock, MagicMock

import pytest

from camouchat_whatsapp.api.managers.activity_api_processor import ActivityApiManager
from camouchat_whatsapp.api.models.activity_api import ActivityEventModel


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.setup_activity_bridge = AsyncMock()
    bridge.poll_activity_queue = AsyncMock()
    bridge.teardown_activity_bridge = AsyncMock()
    return bridge


def test_activity_event_model_from_dict():
    event = ActivityEventModel.from_dict(
        {
            "eventName": "chat.presence_change",
            "id": "123@c.us",
            "state": "composing",
            "isOnline": True,
            "shortName": "Test User",
            "t": 1710000000,
            "participants": [{"id": "1", "state": "composing"}],
        }
    )

    assert event.event_name == "chat.presence_change"
    assert event.contact_id == "123@c.us"
    assert event.state == "composing"
    assert event.is_online is True
    assert event.short_name == "Test User"


@pytest.mark.asyncio
async def test_activity_manager_handler_fanout(mock_bridge):
    manager = ActivityApiManager(mock_bridge)
    handler = MagicMock()
    async_handler = AsyncMock()

    manager.register_handler(handler)
    manager.register_handler(async_handler)

    await manager._dispatch_event(
        {
            "eventName": "conn.online",
            "online": True,
            "timestamp": 1710000000,
        }
    )

    handler.assert_called_once()
    async_handler.assert_called_once()


@pytest.mark.asyncio
async def test_activity_manager_listener_lifecycle(mock_bridge):
    manager = ActivityApiManager(mock_bridge)

    await manager._setup_bridge()
    assert manager._bridge_active is True
    mock_bridge.setup_activity_bridge.assert_called_once()

    await manager.stop_bridge()
    assert manager._bridge_active is False
    mock_bridge.teardown_activity_bridge.assert_called_once()