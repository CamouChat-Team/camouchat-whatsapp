import time

import pytest

from camouchat_whatsapp.exceptions import MessageFilterError
from camouchat_whatsapp.filters.message_filter import MessageFilter, State


class MockMessage:
    def __init__(self, from_chat_id):
        self.from_chat = from_chat_id


def test_message_filter_basic():
    mf = MessageFilter(Max_Messages_Per_Window=2, Window_Seconds=1)
    msgs = [MockMessage("chat_basic"), MockMessage("chat_basic")]

    # First batch should pass
    filtered = mf.apply(msgs)
    assert len(filtered) == 2

    # Second batch should be rate-limited
    msgs2 = [MockMessage("chat_basic")]
    filtered2 = mf.apply(msgs2)
    assert len(filtered2) == 0
    assert not mf.Defer_queue.empty()


def test_message_filter_different_chats():
    mf = MessageFilter()
    msgs = [MockMessage("chat1"), MockMessage("chat2")]

    with pytest.raises(MessageFilterError):
        mf.apply(msgs)


def test_message_filter_empty():
    mf = MessageFilter()
    assert mf.apply([]) == []


def test_message_filter_window_reset():
    mf = MessageFilter(Max_Messages_Per_Window=1, Window_Seconds=0.1)
    msgs = [MockMessage("chat_reset")]

    assert len(mf.apply(msgs)) == 1
    assert len(mf.apply(msgs)) == 0

    time.sleep(0.2)
    assert len(mf.apply(msgs)) == 1


def test_message_filter_hard_drop_reset():
    mf = MessageFilter(Max_Messages_Per_Window=1, LimitTime=0.1)
    msgs = [MockMessage("chat_hard_drop")]

    # Rate limit hit
    mf.apply(msgs)
    assert len(mf.apply(msgs)) == 0

    time.sleep(0.2)
    # LimitTime exceeded, should reset and deliver
    assert len(mf.apply(msgs)) == 1


def test_state_reset():
    state = State(defer_since=100, last_seen=200)
    state.reset()
    assert state.defer_since is None
    assert state.last_seen is None
    assert state.count == 0
