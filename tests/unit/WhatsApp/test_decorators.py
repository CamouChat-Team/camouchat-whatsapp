from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from camouchat_core import MessageProtocol

from camouchat_whatsapp.decorator.msg_event_hook import RegistryConfig, on_newMsg
from camouchat_whatsapp.decorator.storage_hook import on_storage


@pytest.mark.asyncio
async def test_on_storage_decorator():
    mock_storage = MagicMock()
    mock_storage.start = AsyncMock()
    mock_storage.enqueue_insert = AsyncMock()
    mock_storage._initialized_ = False

    profile = MagicMock()

    with patch(
        "camouchat_whatsapp.decorator.storage_hook.SQLAlchemyStorage.from_profile",
        return_value=mock_storage,
    ):

        @on_storage(profile)
        async def my_handler(msg: MessageProtocol):
            return "ok"

        msg = MagicMock(spec=MessageProtocol)
        result = await my_handler(msg)

        assert result == "ok"
        mock_storage.start.assert_called_once()
        mock_storage.enqueue_insert.assert_called_once_with([msg])


@pytest.mark.asyncio
async def test_on_newMsg_decorator():
    mock_wapi = MagicMock()
    mock_wapi.is_ready = False
    mock_wapi.start = AsyncMock()
    mock_msg_mgr = MagicMock()
    mock_wapi.message_manager = mock_msg_mgr

    @on_newMsg(mock_wapi)
    async def my_handler(msg):
        pass

    await my_handler()  # This is the _register coroutine

    mock_wapi.start.assert_called_once()
    mock_msg_mgr.register_handler.assert_called_once()


def test_on_newMsg_non_async():
    mock_wapi = MagicMock()
    with pytest.raises(TypeError):

        @on_newMsg(mock_wapi)
        def my_handler(msg):
            pass


@pytest.mark.asyncio
async def test_on_newMsg_with_storage():
    mock_wapi = MagicMock()
    mock_wapi.is_ready = True
    mock_msg_mgr = MagicMock()
    mock_wapi.message_manager = mock_msg_mgr

    profile = MagicMock()
    config = RegistryConfig(profile=profile)

    mock_storage = MagicMock()
    mock_storage.start = AsyncMock()
    mock_storage.enqueue_insert = AsyncMock()

    with patch(
        "camouchat_whatsapp.decorator.storage_hook.SQLAlchemyStorage.from_profile",
        return_value=mock_storage,
    ):

        @on_newMsg(mock_wapi, config=config)
        async def my_handler(msg: MessageProtocol):
            pass

        await my_handler()
        mock_msg_mgr.register_handler.assert_called_once()
        # The handler registered should be the wrapped one
        registered_handler = mock_msg_mgr.register_handler.call_args[0][0]

        # Test the wrapped handler actually calls storage
        msg = MagicMock(spec=MessageProtocol)
        await registered_handler(msg)
        mock_storage.enqueue_insert.assert_called_once()


@pytest.mark.asyncio
async def test_on_newMsg_missing_manager():
    mock_wapi = MagicMock()
    mock_wapi.is_ready = True
    mock_wapi.message_manager = None

    @on_newMsg(mock_wapi)
    async def my_handler(msg):
        pass

    with pytest.raises(RuntimeError):
        await my_handler()
