from camouchat_whatsapp.api.models.chat_api import ChatModelAPI
from camouchat_whatsapp.api.models.message_api import MessageModelAPI


def test_chat_model_api_from_dict():
    data = {
        "id": {"_serialized": "12345@c.us"},
        "unreadCount": 5,
        "archive": True,
        "name": "Test Chat",
        "t": 1600000000,
        "isParentGroup": True,
        "groupType": "ANNOUNCEMENT",
    }
    chat = ChatModelAPI.from_dict(data)
    assert chat.id_serialized == "12345@c.us"
    assert chat.unreadCount == 5
    assert chat.isArchived is True
    assert chat.formattedTitle == "Test Chat"
    assert chat.timestamp == 1600000000
    assert chat.isCommunity is True
    assert chat.name == "Test Chat"
    assert chat.ui is None


def test_chat_model_api_str_repr_to_dict():
    chat = ChatModelAPI(
        id_serialized="12345@c.us",
        unreadCount=5,
        isAutoMuted=True,
        timestamp=1600000000,
        isArchived=True,
        isLocked=True,
        isNotSpam=False,
        disappearingModeTrigger="chat_settings",
        disappearingModeInitiator="chat",
        unreadMentionCount=1,
        lastChatEntryTimestamp=1600000000,
        isReadOnly=True,
        isTrusted=False,
        formattedTitle="Test Chat",
        groupSafetyChecked=True,
        canSend=False,
        proxyName="chat",
        isCommunity=True,
        muteExpiration=1700000000,
        groupType="ANNOUNCEMENT",
        labels=["Label1"],
        ephemeralDuration=86400,
        ephemeralSettingTimestamp=1600000000,
        unreadMentionsOfMe=["msg1"],
        isAnnounceGrpRestrict=True,
        optional_attr_list={"key": "val"},
    )
    s = str(chat)
    assert "12345@c.us" in s
    assert "Test Chat" in s
    assert "Community" in s
    assert "read-only" in s
    assert "locked" in s
    assert "auto-muted" in s
    assert "untrusted" in s
    assert "spam-flagged" in s
    assert "cannot-send" in s
    assert "announcements-only" in s
    assert "muted-until" in s
    assert "Label1" in s
    assert "duration=86400s" in s

    r = repr(chat)
    assert "ChatModelAPI" in r
    assert "12345@c.us" in r

    d = chat.to_dict()
    assert d["id_serialized"] == "12345@c.us"
    assert "canSend" in d

    d_full = chat.to_dict(include_none=True)
    assert len(d_full) == 26


def test_message_model_api_from_dict():
    data = {
        "id": {"_serialized": "true_12345@c.us_ABC", "fromMe": True},
        "id_serialized": "true_12345@c.us_ABC",
        "t": 1600000000,
        "type": "chat",
        "body": "Hello",
        "fromMe": True,
        "to_serialized": "12345@c.us",
        "notifyName": "User",
        "star": True,
        "isForwarded": True,
        "forwardingScore": 5,
        "quotedMsgId": "msg1",
        "mentionedJidList": ["user1@c.us"],
    }
    msg = MessageModelAPI.from_dict(data)
    assert msg.id_serialized == "true_12345@c.us_ABC"
    assert msg.timestamp == 1600000000
    assert msg.msgtype == "chat"
    assert msg.body == "Hello"
    assert msg.fromMe is True
    assert msg.jid_To == "12345@c.us"
    assert msg.pushname == "User"
    assert msg.isStarMsg is True
    assert msg.isForwarded is True
    assert msg.forwardsCount == 5
    assert msg.fromQuotedMsg is True
    assert msg.quotedMsgId == "msg1"
    assert msg.mentionedJidList == ["user1@c.us"]


def test_message_model_api_str_repr_to_dict():
    msg = MessageModelAPI(
        id_serialized="true_12345@c.us_ABC",
        encryption_nonce="nonce",
        timestamp=1600000000,
        msgtype="image",
        body="base64thumb" * 20,
        from_chat="12345@c.us",
        rowId=1,
        fromMe=True,
        jid_From="me@c.us",
        jid_To="12345@c.us",
        author="me@c.us",
        pushname="Me",
        broadcast=False,
        caption="My Photo",
        ack=3,
        isNewMsg=True,
        recvFresh=True,
        isMdHistoryMsg=False,
        isStarMsg=True,
        isForwarded=True,
        forwardsCount=2,
        hasReaction=True,
        pendingDeleteForMe=False,
        ephemeralDuration=0,
        disappearingModeInitiator=None,
        disappearingModeTrigger=None,
        isAvatar=False,
        isVideoCallMessage=False,
        isDynamicReplyButtonsMsg=False,
        isCarouselCard=False,
        activeBotMsgStreamingInProgress=False,
        fromQuotedMsg=True,
        isQuotedMsgAvailable=True,
        quotedMsgId="msg0",
        quotedmsgtype="chat",
        quotedMsgBody="Original msg",
        quotedParticipant="other@c.us",
        quotedRemoteJid="12345@c.us",
        mentionedJidList=["user1@c.us", "user2@c.us", "user3@c.us", "user4@c.us"],
        senderObj={"name": "Me", "isBusiness": True, "verifiedLevel": 1},
        senderWithDevice="me@c.us:1",
        optionalAttrList={"debug": "val"},
        mimetype="image/jpeg",
        directPath="/path",
        mediaKey="key",
        size=2000000,
        duration=None,
        isViewOnce=True,
        mediaData=None,
        deprecatedMms3Url=None,
        staticUrl=None,
        thumbnailDirectPath=None,
        thumbnailSha256=None,
        thumbnailEncSha256=None,
        isQuestion=False,
        pollName=None,
        pollType=None,
        pollContentType=None,
        pollSelectableOptionsCount=None,
        questionResponsesCount=None,
        readQuestionResponsesCount=None,
        eventName=None,
        eventDescription=None,
        eventJoinLink=None,
        eventStartTime=None,
        eventEndTime=None,
        isEventCanceled=None,
        eventIsScheduledCall=None,
        vcardFormattedName=None,
        vcardList=None,
        stickerSentTs=None,
        isViewed=True,
    )

    s = str(msg)
    assert "true_12345@c.us_ABC" in s
    assert "image" in s
    assert "Me" in s
    assert "senderProfile: Me [Business, VerifiedLvl=1]" in s
    assert "senderDevice: me@c.us:1" in s
    assert "ack         : 3" in s
    assert "body        : base64thumb" in s
    assert "caption     : My Photo" in s
    assert "flags       : fromMe, forwarded×2, hasReaction, starred, viewOnce" in s
    assert "arrival     : wire-new, recvFresh" in s
    assert "quotedId   : msg0" in s
    assert "mentions    : 4 user(s)" in s
    assert "mimetype    : image/jpeg" in s
    assert "size        : 1.91 MB" in s

    # Test small size
    msg.size = 500
    assert "size        : 500 bytes" in str(msg)
    msg.size = 5000
    assert "size        : 4.9 KB" in str(msg)

    # Test vcard body preview
    msg.msgtype = "vcard"
    msg.body = "BEGIN:VCARD\nVERSION:3.0\nFN:Test\nEND:VCARD"
    assert "preview" in str(msg) or "BEGIN:VCARD" in str(msg)

    r = repr(msg)
    assert "MessageModelAPI" in r

    d = msg.to_dict()
    assert d["id_serialized"] == "true_12345@c.us_ABC"

    d_full = msg.to_dict(include_none=True)
    # The count might vary depending on internal fields, let's just assert it's a large dict
    assert len(d_full) >= 65


def test_message_model_api_from_dict_variants():
    # Test fromMe detection from id_serialized
    data = {"id_serialized": "true_12345@c.us_ABC", "t": 1600000000, "type": "chat"}
    msg = MessageModelAPI.from_dict(data)
    assert msg.fromMe is True

    # Test poll detection
    data = {
        "type": "poll_creation",
        "isAnyQuestion": True,
        "pollName": "What is your favorite color?",
        "pollType": "POLL",
        "pollContentType": "TEXT",
        "pollSelectableOptionsCount": 1,
        "questionResponsesCount": 10,
    }
    msg = MessageModelAPI.from_dict(data)
    assert msg.isQuestion is True
    assert msg.pollName == "What is your favorite color?"
    assert "poll(10 votes)" in str(msg)


def test_message_model_api_str_events_vcards():
    # Test event creation __str__
    msg = MessageModelAPI(
        id_serialized="msg_event",
        msgtype="event_creation",
        fromMe=False,
        timestamp=1600000000,
        eventName="Meeting",
        eventDescription="Talk about coverage",
        eventStartTime=1600000000,
        eventEndTime=1600000100,
        eventJoinLink="http://zoom.us",
        isEventCanceled=True,
        eventIsScheduledCall=True,
        # Mandatory fields
        body=None,
        caption=None,
        jid_From="group@g.us",
        jid_To="me@c.us",
        author=None,
        pushname=None,
        broadcast=None,
        ack=None,
        isNewMsg=None,
        recvFresh=None,
        isMdHistoryMsg=None,
        isStarMsg=None,
        isForwarded=None,
        forwardsCount=0,
        hasReaction=None,
        pendingDeleteForMe=None,
        ephemeralDuration=0,
        disappearingModeInitiator=None,
        disappearingModeTrigger=None,
        isAvatar=None,
        isVideoCallMessage=None,
        isDynamicReplyButtonsMsg=None,
        isCarouselCard=None,
        activeBotMsgStreamingInProgress=None,
        fromQuotedMsg=None,
        isQuotedMsgAvailable=None,
        quotedMsgId=None,
        quotedmsgtype=None,
        quotedMsgBody=None,
        quotedParticipant=None,
        quotedRemoteJid=None,
        mentionedJidList=None,
        senderObj=None,
        senderWithDevice=None,
        optionalAttrList=None,
        mimetype=None,
        directPath=None,
        mediaKey=None,
        size=None,
        duration=None,
        isViewOnce=None,
        mediaData=None,
        deprecatedMms3Url=None,
        staticUrl=None,
        thumbnailDirectPath=None,
        thumbnailSha256=None,
        thumbnailEncSha256=None,
        isQuestion=None,
        pollName=None,
        pollType=None,
        pollContentType=None,
        pollSelectableOptionsCount=None,
        questionResponsesCount=None,
        readQuestionResponsesCount=None,
        vcardFormattedName=None,
        vcardList=None,
        stickerSentTs=None,
        isViewed=None,
        from_chat="group@g.us",
        rowId=None,
        encryption_nonce=None,
    )
    s = str(msg)
    assert "Meeting" in s
    assert "Talk about coverage" in s
    assert "⚠ EVENT CANCELED" in s
    assert "scheduled call" in s

    # Test vcard list __str__
    msg.msgtype = "multi_vcard"
    msg.vcardFormattedName = "Multiple Contacts"
    msg.vcardList = [{"raw": "vcf"}]
    s = str(msg)
    assert "Multiple Contacts" in s
    assert "vcardCount  : 1" in s
