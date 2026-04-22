from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camouchat_whatsapp.api.wa_js.wajs_wrapper import WapiWrapper
from camouchat_whatsapp.exceptions import WAJSError


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.evaluate = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_wajs_wrapper_evaluate_stealth_success(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": "some_data"}

    result = await wrapper._evaluate_stealth("WPP.chat.list()")
    assert result == "some_data"
    mock_page.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_wajs_wrapper_evaluate_stealth_failure(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": False, "error": "JS Error"}

    with pytest.raises(WAJSError, match="JS Error"):
        await wrapper._evaluate_stealth("WPP.chat.list()")


@pytest.mark.asyncio
async def test_wajs_wrapper_wait_for_ready(mock_page):
    wrapper = WapiWrapper(mock_page)

    # Mocking read_text and abspath to avoid disk access
    with (
        patch.object(WapiWrapper, "_read_text", return_value="console.log('wpp')"),
        patch("os.path.abspath", return_value="/fake/path"),
    ):
        # Mocking evaluate responses
        mock_page.evaluate.side_effect = [
            False,  # has_global
            None,  # injection script
            True,  # is_ready
            None,  # Smash & Grab setup
            True,  # sweep_ok verification
        ]

        assert await wrapper.wait_for_ready() is True
        assert wrapper._wpp_key.startswith("__react_devtools_")


@pytest.mark.asyncio
async def test_wajs_wrapper_api_methods(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": "ok"}

    # Test more representative methods
    await wrapper.send_text_message("123", "hi")
    await wrapper.contact_get_profile_picture_url("123")
    await wrapper.group_get_participants("123")
    await wrapper.conn_get_platform()
    await wrapper.conn_is_online()
    await wrapper.group_create("New Group", ["123"])
    await wrapper.group_leave("123")
    await wrapper.conn_is_main_ready()
    await wrapper.contact_get_status("123")
    await wrapper.mark_is_read("123")
    await wrapper.mark_is_composing("123")
    await wrapper.newsletter_list()
    await wrapper.newsletter_search("test")
    await wrapper.newsletter_follow("123")
    await wrapper.newsletter_unfollow("123")
    await wrapper.newsletter_mute("123")
    await wrapper.newsletter_unmute("123")
    await wrapper.conn_get_my_user_id()
    await wrapper.conn_get_my_user_lid()
    await wrapper.conn_get_my_user_wid()
    await wrapper.conn_get_my_device_id()
    await wrapper.conn_is_multi_device()
    await wrapper.conn_is_idle()
    await wrapper.conn_get_theme()
    await wrapper.contact_list()
    await wrapper.contact_query_exists("123")
    await wrapper.contact_get_business_profile("123")
    await wrapper.contact_get_common_groups("123")
    await wrapper.group_get_all()
    await wrapper.group_get_invite_code("123")


@pytest.mark.asyncio
async def test_wajs_wrapper_setup_message_bridge(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": True}

    await wrapper.setup_message_bridge()
    assert wrapper._bridge_active is True
    assert wrapper._queue_key is not None


@pytest.mark.asyncio
async def test_wajs_wrapper_poll_message_queue(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"
    wrapper._bridge_active = True
    wrapper._queue_key = "__camou_queue__"

    mock_page.evaluate.return_value = ["id1", "id2"]

    ids = await wrapper.poll_message_queue()
    assert ids == ["id1", "id2"]
    mock_page.evaluate.assert_called_once()
