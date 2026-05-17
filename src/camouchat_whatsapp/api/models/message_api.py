from dataclasses import asdict, dataclass
from typing import Any

from camouchat_core import MessageProtocol
from playwright.async_api import ElementHandle, Locator

# ──────────────────────────────────────────────
#  Sub-models  (grouped by concern)
# ──────────────────────────────────────────────


@dataclass
class MessageIdentity:
    """
    Core identity fields of the message.

    Attributes:
        id_serialized (str | None): Full unique ID (e.g., 'false_1234@c.us_ABCDEF').
        encryption_nonce (str | None): Encryption nonce for the message.
        rowId (int | None): IndexedDB row ID (useful for pagination/anchors).
        fromMe (bool | None): True if the message was sent by the authenticated user.
        jid_From (str | None): JID of the sender (or the Group JID if received in a group).
        jid_To (str | None): JID of the recipient.
        author (str | None): JID of the specific person who sent it (ONLY present in group chats).
        pushname (str | None): The notification name of the sender.
        broadcast (bool | None): True if sent via a Broadcast List.
        msgtype (str | None): Message type: 'chat','image','video','ptt','document','revoked', etc.
        body (str | None): Text content, or base64 thumbnail for media.
        caption (str | None): Text caption attached to media.
        timestamp (int | None): Unix timestamp of the message.
        ack (int | None): 0=Pending, 1=Sent, 2=Delivered, 3=Read(Blue Ticks), 4=Played.
        from_chat (str): The chat JID this message belongs to.
    """

    id_serialized: str | None
    encryption_nonce: str | None  # type: ignore[assignment]
    rowId: int | None
    fromMe: bool | None
    jid_From: str | None
    jid_To: str | None
    author: str | None
    pushname: str | None
    broadcast: bool | None
    msgtype: str | None
    body: str | None
    caption: str | None
    timestamp: int | None
    ack: int | None
    from_chat: str


@dataclass
class MessageArrival:
    """
    Presence / arrival flags — how and when the message reached this device.

    Attributes:
        isNewMsg (bool | None): True if the message arrived on the wire in this session.
        recvFresh (bool | None): True when the message arrived in real-time, False when
                                 it was replayed from history-sync on reconnect.
        isMdHistoryMsg (bool | None): True if this is a message synced from history
                                      (multi-device history sync), not a live wire message.
    """

    isNewMsg: bool | None
    recvFresh: bool | None
    isMdHistoryMsg: bool | None


@dataclass
class MessageSocial:
    """
    Social interaction flags.

    Attributes:
        isStarMsg (bool | None): True if the message is starred/favorited.
        isForwarded (bool | None): True if the message has the "Forwarded" tag.
        forwardsCount (int | None): Number of times this message was forwarded.
        hasReaction (bool | None): True if someone reacted to this message.
        pendingDeleteForMe (bool | None): True if a "Delete for me" operation is in flight.
    """

    isStarMsg: bool | None
    isForwarded: bool | None
    forwardsCount: int | None
    hasReaction: bool | None
    pendingDeleteForMe: bool | None


@dataclass
class MessageEphemeral:
    """
    Disappearing / ephemeral message settings.

    Attributes:
        ephemeralDuration (int | None): Disappearing message duration in seconds (0 if off).
        disappearingModeInitiator (str | None): Who triggered disappearing mode ('chat', 'admin', etc).
        disappearingModeTrigger (str | None): What triggered it ('chat_settings', 'admin', etc).
    """

    ephemeralDuration: int | None
    disappearingModeInitiator: str | None
    disappearingModeTrigger: str | None


@dataclass
class MessageSpecialFlags:
    """
    Special message type flags.

    Attributes:
        isAvatar (bool | None): True if message is an avatar sticker.
        isVideoCallMessage (bool | None): True if the message is a call log/missed call alert.
        isDynamicReplyButtonsMsg (bool | None): True if message has WA Business dynamic reply buttons.
        isCarouselCard (bool | None): True if message is a WA Business carousel card.
        activeBotMsgStreamingInProgress (bool | None): True while a WA AI/bot reply is being streamed.
    """

    isAvatar: bool | None
    isVideoCallMessage: bool | None
    isDynamicReplyButtonsMsg: bool | None
    isCarouselCard: bool | None
    activeBotMsgStreamingInProgress: bool | None


@dataclass
class MessageQuoted:
    """
    Quoted / reply context fields.

    Attributes:
        fromQuotedMsg (bool | None): True if this message is a reply to another message.
        isQuotedMsgAvailable (bool | None): True if the quoted message still exists in local DB.
        quotedMsgId (str | None): The serialized ID of the message being replied to.
        quotedmsgtype (str | None): Type of the quoted message (e.g. 'image', 'chat').
        quotedMsgBody (str | None): First 120 chars of quoted message body/caption.
        quotedParticipant (str | None): JID of the person who sent the original quoted message.
        quotedRemoteJid (str | None): Chat JID where the quoted message lives.
    """

    fromQuotedMsg: bool | None
    isQuotedMsgAvailable: bool | None
    quotedMsgId: str | None
    quotedmsgtype: str | None
    quotedMsgBody: str | None
    quotedParticipant: str | None
    quotedRemoteJid: str | None


@dataclass
class MessageMedia:
    """
    Media attachment fields.

    Attributes:
        mimetype (str | None): e.g., 'image/jpeg', 'audio/ogg; codecs=opus'.
        directPath (str | None): Decryption URL path for the CDN.
        mediaKey (str | None): Base64 encryption key for downloading media.
        size (int | None): Size of the media in bytes.
        duration (int | None): Duration in seconds (for audio/video).
        isViewOnce (bool | None): True if sent as "View Once" media.
        mediaData (dict | None): Raw media data dict.
        deprecatedMms3Url (str | None): Legacy MMS3 URL.
        staticUrl (str | None): Static CDN URL.
        thumbnailDirectPath (str | None): CDN path for the thumbnail.
        thumbnailSha256 (str | None): SHA256 of the thumbnail.
        thumbnailEncSha256 (str | None): Encrypted SHA256 of the thumbnail.
    """

    mimetype: str | None
    directPath: str | None
    mediaKey: str | None
    size: int | None
    duration: int | None
    isViewOnce: bool | None
    mediaData: dict[str, Any] | None
    deprecatedMms3Url: str | None
    staticUrl: str | None
    thumbnailDirectPath: str | None
    thumbnailSha256: str | None
    thumbnailEncSha256: str | None


@dataclass
class MessagePoll:
    """
    Poll / quiz fields.

    Attributes:
        isQuestion (bool | None): True if this is a Poll message.
        pollName (str | None): The question / title text of the poll.
        pollType (str | None): 'POLL' or 'QUIZ' etc.
        pollContentType (str | None): 'TEXT' or 'IMAGE' etc.
        pollSelectableOptionsCount (int | None): Max options a voter may select (0 = unlimited).
        questionResponsesCount (int | None): Number of people who voted (from wire field).
        readQuestionResponsesCount (int | None): Read question responses count (internal WA field).
    """

    isQuestion: bool | None
    pollName: str | None
    pollType: str | None
    pollContentType: str | None
    pollSelectableOptionsCount: int | None
    questionResponsesCount: int | None
    readQuestionResponsesCount: int | None


@dataclass
class MessageEvent:
    """
    Event message fields.

    Attributes:
        eventName (str | None): Title of the event (type='event_creation').
        eventDescription (str | None): Body/description of the event.
        eventJoinLink (str | None): WhatsApp call or external join URL.
        eventStartTime (int | None): Unix timestamp of the event start.
        eventEndTime (int | None): Unix timestamp of the event end.
        isEventCanceled (bool | None): True if the event was subsequently canceled.
        eventIsScheduledCall (bool | None): True if the event is a scheduled WA call.
    """

    eventName: str | None
    eventDescription: str | None
    eventJoinLink: str | None
    eventStartTime: int | None
    eventEndTime: int | None
    isEventCanceled: bool | None
    eventIsScheduledCall: bool | None


@dataclass
class MessageVCard:
    """
    vCard contact fields.

    Attributes:
        vcardFormattedName (str | None): Human-readable display name from the vCard (FN field).
        vcardList (list | None): Raw vCard payloads if msgtype == 'vcard' / 'multi_vcard'.
    """

    vcardFormattedName: str | None
    vcardList: list[Any] | None


@dataclass
class MessageSender:
    """
    Deep sender identity fields.

    Attributes:
        senderObj (dict | None): Full sender profile object from WA internals.
        senderWithDevice (str | None): Sender JID with device suffix.
        mentionedJidList (list | None): List of JIDs @mentioned in the message.
    """

    senderObj: dict[str, Any] | None
    senderWithDevice: str | None
    mentionedJidList: list[str] | None


# ──────────────────────────────────────────────
#  Main model
# ──────────────────────────────────────────────


@dataclass
class MessageModelAPI(MessageProtocol):
    """
    Normalized Data Model for a WhatsApp Message.
    Parses the raw Webpack dictionary into a clean, predictable Python object.

    Attributes are grouped into focused sub-models:
        identity      – core fields (id, type, body, timestamp, ack …)
        arrival       – how/when the message reached this device
        social        – stars, forwards, reactions, pending deletes
        ephemeral     – disappearing message configuration
        special_flags – avatar, call log, bot streaming, business buttons
        quoted        – reply/quote context
        media         – attachments (mimetype, key, size, duration …)
        poll          – poll/quiz fields
        event         – event_creation message fields
        vcard         – contact card fields
        sender        – deep sender identity and mentions

    Note:
        1. If a field is None it most likely means the webpack patch did not expose
           that property, or WhatsApp silently changed internal key names.

        2. 'ack', 'timestamp', and delivery-state fields reflect the snapshot at the
           moment chat.new_message fired. Real-time updates (ack=2/3/4) arrive via
           separate msg.ack events and are not captured here. Re-fetch by id if
           current delivery state is needed.
    """

    identity: MessageIdentity
    arrival: MessageArrival
    social: MessageSocial
    ephemeral: MessageEphemeral
    special_flags: MessageSpecialFlags
    quoted: MessageQuoted
    media: MessageMedia
    poll: MessagePoll
    event: MessageEvent
    vcard: MessageVCard
    sender: MessageSender
    optionalAttrList: dict[str, str] | None
    stickerSentTs: int | None
    isViewed: bool | None

    # ─────────────────────────────────────────────────────────────────────────
    ui: ElementHandle | Locator | None = None  # type: ignore[assignment]
    _MEDIA_THUMB_TYPES: frozenset = frozenset(
        {
            "image",
            "video",
            "sticker",
            "document",
            "audio",
            "ptt",
            "gif",
            "product",
            "order",
        }
    )

    # ── backwards-compat flat properties ────────
    #  Allows existing code using msg.timestamp,
    #  msg.fromMe, etc. to keep working unchanged.

    # identity
    @property
    def id_serialized(self):
        return self.identity.id_serialized

    @property
    def encryption_nonce(self):
        return self.identity.encryption_nonce

    @property
    def rowId(self):
        return self.identity.rowId

    @property
    def fromMe(self):
        return self.identity.fromMe

    @property
    def jid_From(self):
        return self.identity.jid_From

    @property
    def jid_To(self):
        return self.identity.jid_To

    @property
    def author(self):
        return self.identity.author

    @property
    def pushname(self):
        return self.identity.pushname

    @property
    def broadcast(self):
        return self.identity.broadcast

    @property
    def msgtype(self):
        return self.identity.msgtype

    @property
    def body(self):
        return self.identity.body

    @property
    def caption(self):
        return self.identity.caption

    @property
    def timestamp(self):
        return self.identity.timestamp

    @property
    def ack(self):
        return self.identity.ack

    @property
    def from_chat(self):
        return self.identity.from_chat

    # arrival
    @property
    def isNewMsg(self):
        return self.arrival.isNewMsg

    @property
    def recvFresh(self):
        return self.arrival.recvFresh

    @property
    def isMdHistoryMsg(self):
        return self.arrival.isMdHistoryMsg

    # social
    @property
    def isStarMsg(self):
        return self.social.isStarMsg

    @property
    def isForwarded(self):
        return self.social.isForwarded

    @property
    def forwardsCount(self):
        return self.social.forwardsCount

    @property
    def hasReaction(self):
        return self.social.hasReaction

    @property
    def pendingDeleteForMe(self):
        return self.social.pendingDeleteForMe

    # ephemeral
    @property
    def ephemeralDuration(self):
        return self.ephemeral.ephemeralDuration

    @property
    def disappearingModeInitiator(self):
        return self.ephemeral.disappearingModeInitiator

    @property
    def disappearingModeTrigger(self):
        return self.ephemeral.disappearingModeTrigger

    # special_flags
    @property
    def isAvatar(self):
        return self.special_flags.isAvatar

    @property
    def isVideoCallMessage(self):
        return self.special_flags.isVideoCallMessage

    @property
    def isDynamicReplyButtonsMsg(self):
        return self.special_flags.isDynamicReplyButtonsMsg

    @property
    def isCarouselCard(self):
        return self.special_flags.isCarouselCard

    @property
    def activeBotMsgStreamingInProgress(self):
        return self.special_flags.activeBotMsgStreamingInProgress

    # quoted
    @property
    def fromQuotedMsg(self):
        return self.quoted.fromQuotedMsg

    @property
    def isQuotedMsgAvailable(self):
        return self.quoted.isQuotedMsgAvailable

    @property
    def quotedMsgId(self):
        return self.quoted.quotedMsgId

    @property
    def quotedmsgtype(self):
        return self.quoted.quotedmsgtype

    @property
    def quotedMsgBody(self):
        return self.quoted.quotedMsgBody

    @property
    def quotedParticipant(self):
        return self.quoted.quotedParticipant

    @property
    def quotedRemoteJid(self):
        return self.quoted.quotedRemoteJid

    # media
    @property
    def mimetype(self):
        return self.media.mimetype

    @property
    def directPath(self):
        return self.media.directPath

    @property
    def mediaKey(self):
        return self.media.mediaKey

    @property
    def size(self):
        return self.media.size

    @property
    def duration(self):
        return self.media.duration

    @property
    def isViewOnce(self):
        return self.media.isViewOnce

    @property
    def mediaData(self):
        return self.media.mediaData

    @property
    def deprecatedMms3Url(self):
        return self.media.deprecatedMms3Url

    @property
    def staticUrl(self):
        return self.media.staticUrl

    @property
    def thumbnailDirectPath(self):
        return self.media.thumbnailDirectPath

    @property
    def thumbnailSha256(self):
        return self.media.thumbnailSha256

    @property
    def thumbnailEncSha256(self):
        return self.media.thumbnailEncSha256

    # poll
    @property
    def isQuestion(self):
        return self.poll.isQuestion

    @property
    def pollName(self):
        return self.poll.pollName

    @property
    def pollType(self):
        return self.poll.pollType

    @property
    def pollContentType(self):
        return self.poll.pollContentType

    @property
    def pollSelectableOptionsCount(self):
        return self.poll.pollSelectableOptionsCount

    @property
    def questionResponsesCount(self):
        return self.poll.questionResponsesCount

    @property
    def readQuestionResponsesCount(self):
        return self.poll.readQuestionResponsesCount

    # event
    @property
    def eventName(self):
        return self.event.eventName

    @property
    def eventDescription(self):
        return self.event.eventDescription

    @property
    def eventJoinLink(self):
        return self.event.eventJoinLink

    @property
    def eventStartTime(self):
        return self.event.eventStartTime

    @property
    def eventEndTime(self):
        return self.event.eventEndTime

    @property
    def isEventCanceled(self):
        return self.event.isEventCanceled

    @property
    def eventIsScheduledCall(self):
        return self.event.eventIsScheduledCall

    # vcard
    @property
    def vcardFormattedName(self):
        return self.vcard.vcardFormattedName

    @property
    def vcardList(self):
        return self.vcard.vcardList

    # sender
    @property
    def senderObj(self):
        return self.sender.senderObj

    @property
    def senderWithDevice(self):
        return self.sender.senderWithDevice

    @property
    def mentionedJidList(self):
        return self.sender.mentionedJidList

    # ── constructors ────────────────────────────

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageModelAPI":
        """
        Build MessageModelAPI from the raw dict returned by WAJS_Scripts.get_message_by_id().

        Key mapping (JS dump → Python field):
          id_serialized      → id_serialized
          from_serialized    → jid_From   (WID._serialized pre-extracted by JS)
          to_serialized      → jid_To     (WID._serialized pre-extracted by JS)
          author_serialized  → author     (group messages only)
          t                  → timestamp  (Unix seconds)
          type               → msgtype
          body               → body
          notifyName         → pushname
          star               → isStarMsg
          isForwarded        → isForwarded
          forwardingScore    → forwardsCount
          viewed             → isViewed
          isVideoCall        → isVideoCallMessage
        """

        def g(key: str, default: Any = None) -> Any:
            return data.get(key, data.get(f"__x_{key}", default))

        # ── timestamp ─────────────────────────────────────────────────────────
        t_val = g("t")
        timestamp = t_val if t_val is not None else g("timestamp")

        # ── media size ────────────────────────────────────────────────────────
        size_val = g("size")
        size = size_val if size_val is not None else g("fileLength")

        question_responses = g("questionResponsesCount", 0)

        # ── Poll type detection ───────────────────────────────────────────────
        is_poll = g("type") == "poll_creation"
        is_question = g("isAnyQuestion") or is_poll

        # ── fromMe resolution ─────────────────────────────────────────────────
        id_obj = g("id", {})
        is_from_me = g("fromMe")
        if is_from_me is None:
            if isinstance(id_obj, dict) and "fromMe" in id_obj:
                is_from_me = id_obj.get("fromMe")
            elif g("id_serialized") and str(g("id_serialized")).startswith("true_"):
                is_from_me = True
            else:
                is_from_me = False
        is_from_me = bool(is_from_me)

        return cls(
            identity=MessageIdentity(
                id_serialized=g("id_serialized"),
                encryption_nonce=g("encryption_nonce"),
                rowId=g("rowId"),
                fromMe=is_from_me,
                jid_From=g("to_serialized") if is_from_me else g("from_serialized"),
                jid_To=g("to_serialized"),
                author=g("author_serialized"),
                pushname=g("notifyName") or g("pushname"),
                broadcast=g("broadcast"),
                msgtype=g("type"),
                body=g("body"),
                caption=g("caption"),
                timestamp=timestamp,
                ack=g("ack", 0),
                from_chat="",  # personally invoked via get_chat_by_id; empty saves RAM on init
            ),
            arrival=MessageArrival(
                isNewMsg=g("isNewMsg"),
                recvFresh=g("recvFresh"),
                isMdHistoryMsg=g("isMdHistoryMsg"),
            ),
            social=MessageSocial(
                isStarMsg=g("star"),
                isForwarded=g("isForwarded"),
                forwardsCount=(
                    g("forwardingScore")
                    if g("forwardingScore") is not None
                    else g("forwardsCount", 0)
                ),
                hasReaction=g("hasReaction"),
                pendingDeleteForMe=g("pendingDeleteForMe"),
            ),
            ephemeral=MessageEphemeral(
                ephemeralDuration=g("ephemeralDuration", 0),
                disappearingModeInitiator=g("disappearingModeInitiator"),
                disappearingModeTrigger=g("disappearingModeTrigger"),
            ),
            special_flags=MessageSpecialFlags(
                isAvatar=g("isAvatar"),
                isVideoCallMessage=g("isVideoCall"),
                isDynamicReplyButtonsMsg=g("isDynamicReplyButtonsMsg"),
                isCarouselCard=g("isCarouselCard"),
                activeBotMsgStreamingInProgress=g("activeBotMsgStreamingInProgress"),
            ),
            quoted=MessageQuoted(
                fromQuotedMsg=bool(
                    g("quotedMsg") or g("quotedMsgId") or g("quotedStanzaID")
                ),
                isQuotedMsgAvailable=bool(g("quotedMsg")),
                quotedMsgId=g("quotedMsgId") or g("quotedStanzaID"),
                quotedmsgtype=g("quotedmsgtype"),
                quotedMsgBody=g("quotedMsgBody"),
                quotedParticipant=g("quotedParticipant"),
                quotedRemoteJid=g("quotedRemoteJid"),
            ),
            media=MessageMedia(
                mimetype=g("mimetype"),
                directPath=g("directPath"),
                mediaKey=g("mediaKey"),
                size=size,
                duration=g("duration"),
                isViewOnce=g("isViewOnce", False),
                mediaData=g("mediaData"),
                deprecatedMms3Url=g("deprecatedMms3Url"),
                staticUrl=g("staticUrl"),
                thumbnailDirectPath=g("thumbnailDirectPath"),
                thumbnailSha256=g("thumbnailSha256"),
                thumbnailEncSha256=g("thumbnailEncSha256"),
            ),
            poll=MessagePoll(
                isQuestion=is_question,
                pollName=g("pollName"),
                pollType=g("pollType"),
                pollContentType=g("pollContentType"),
                pollSelectableOptionsCount=g("pollSelectableOptionsCount"),
                questionResponsesCount=question_responses,
                readQuestionResponsesCount=g("readQuestionResponsesCount"),
            ),
            event=MessageEvent(
                eventName=g("eventName"),
                eventDescription=g("eventDescription"),
                eventJoinLink=g("eventJoinLink"),
                eventStartTime=g("eventStartTime"),
                eventEndTime=g("eventEndTime"),
                isEventCanceled=g("isEventCanceled"),
                eventIsScheduledCall=g("eventIsScheduledCall"),
            ),
            vcard=MessageVCard(
                vcardFormattedName=g("vcardFormattedName"),
                vcardList=g("vcardList") or None,
            ),
            sender=MessageSender(
                senderObj=g("senderObj") or None,
                senderWithDevice=g("senderWithDevice") or None,
                mentionedJidList=(
                    [
                        j if isinstance(j, str) else j.get("_serialized", str(j))
                        for j in m_list
                    ]
                    if (m_list := g("mentionedJidList"))
                    else None
                ),
            ),
            optionalAttrList=g("optionalAttrList") or {},
            stickerSentTs=g("stickerSentTs"),
            isViewed=g("viewed"),
        )

    # ── serialisation ───────────────────────────

    def to_dict(self, include_none: bool = False) -> dict[str, Any]:
        """
        Export this MessageModelAPI as a flat Python dict.

        Useful for:
        - JSON serialization  → json.dumps(msg.to_dict())
        - Structured logging  → logger.info("msg", extra=msg.to_dict())
        - Custom DB storage   → db.insert(msg.to_dict())
        - Forwarding to APIs  → requests.post(url, json=msg.to_dict())
        - Equality comparison → msg_a.to_dict() == msg_b.to_dict()

        Args:
            include_none: If False (default), keys whose value is None are
                          omitted to keep the output compact. Set to True to
                          get a fixed-schema dict with every field present.

        Returns:
            Dict[str, Any] — all fields as a flat dict, matching original schema.
        """
        raw: dict[str, Any] = {
            **asdict(self.identity),
            **asdict(self.arrival),
            **asdict(self.social),
            **asdict(self.ephemeral),
            **asdict(self.special_flags),
            **asdict(self.quoted),
            **asdict(self.media),
            **asdict(self.poll),
            **asdict(self.event),
            **asdict(self.vcard),
            **asdict(self.sender),
            "optionalAttrList": self.optionalAttrList,
            "stickerSentTs": self.stickerSentTs,
            "isViewed": self.isViewed,
        }
        if include_none:
            return raw
        return {k: v for k, v in raw.items() if v is not None}

    # ── dunder helpers ──────────────────────────

    def __str__(self) -> str:
        id_ = self.identity
        lines = [
            "─── MessageModelAPI ───────────────────────────────",
            f"  id          : {id_.id_serialized}",
            f"  type        : {id_.msgtype}",
            f"  from        : {'Me' if id_.fromMe else id_.jid_From}",
            f"  to          : {id_.jid_To}",
        ]

        if id_.author:
            lines.append(f"  author      : {id_.author}  (group sender)")
        if id_.pushname:
            lines.append(f"  pushname    : {id_.pushname}")

        # Deep Sender Profiling display
        so = self.sender.senderObj
        if so:
            badges = []
            if so.get("isBusiness"):
                badges.append("Business")
            if so.get("isEnterprise"):
                badges.append("Enterprise")
            if so.get("verifiedLevel"):
                badges.append(f"VerifiedLvl={so.get('verifiedLevel')}")
            badge_str = f" [{', '.join(badges)}]" if badges else ""
            display_name = (
                so.get("__x_name")
                or so.get("name")
                or so.get("__x_pushname")
                or so.get("pushname")
                or "Unknown"
            )
            lines.append(f"  senderProfile: {display_name}{badge_str}")

        if self.sender.senderWithDevice:
            lines.append(f"  senderDevice: {self.sender.senderWithDevice}")

        lines.append(f"  timestamp   : {id_.timestamp}")
        lines.append(
            f"  ack         : {id_.ack}  (0=pending 1=sent 2=delivered 3=read 4=played)"
        )

        # ── Body / caption ────────────────────────────────────────────────────
        if id_.body:
            body = id_.body
            if id_.msgtype == "vcard":
                preview = "\n         ".join(body.splitlines()[:3])
                body_display = preview + ("…[vCard]" if len(body) > 120 else "")
            elif id_.msgtype in self._MEDIA_THUMB_TYPES and len(body) > 100:
                body_display = f"{body[:40]}…[thumbnail b64, {len(body)} chars]"
            elif len(body) > 200:
                body_display = f"{body[:200]}…"
            else:
                body_display = body
            lines.append(f"  body        : {body_display}")
        if id_.caption:
            lines.append(f"  caption     : {id_.caption}")

        # ── Flags ─────────────────────────────────────────────────────────────
        flags = []
        if id_.fromMe:
            flags.append("fromMe")
        if self.social.isForwarded:
            flags.append(f"forwarded×{self.social.forwardsCount}")
        if self.social.hasReaction:
            flags.append("hasReaction")
        if self.social.isStarMsg:
            flags.append("starred")
        if id_.broadcast:
            flags.append("broadcast")
        if self.media.isViewOnce:
            flags.append("viewOnce")
        if self.special_flags.isVideoCallMessage:
            flags.append("callLog")
        if self.poll.isQuestion:
            flags.append(f"poll({self.poll.questionResponsesCount} votes)")
        if self.ephemeral.ephemeralDuration:
            flags.append(f"ephemeral={self.ephemeral.ephemeralDuration}s")
        if self.special_flags.isDynamicReplyButtonsMsg:
            flags.append("dynamicReplyButtons")
        if self.special_flags.isCarouselCard:
            flags.append("carouselCard")
        if self.special_flags.activeBotMsgStreamingInProgress:
            flags.append("botStreaming")
        if self.social.pendingDeleteForMe:
            flags.append("pendingDelete")
        if id_.msgtype == "ciphertext":
            flags.append("⚠ ciphertext(pending-decrypt)")
        if flags:
            lines.append(f"  flags       : {', '.join(flags)}")

        # ── Arrival / sync info ───────────────────────────────────────────────
        arrival_flags = []
        if self.arrival.isNewMsg:
            arrival_flags.append("wire-new")
        if self.arrival.recvFresh:
            arrival_flags.append("recvFresh")
        if self.arrival.isMdHistoryMsg:
            arrival_flags.append("history-sync")
        if arrival_flags:
            lines.append(f"  arrival     : {', '.join(arrival_flags)}")

        # ── Ephemeral detail ──────────────────────────────────────────────────
        ep = self.ephemeral
        if ep.disappearingModeInitiator or ep.disappearingModeTrigger:
            lines.append(
                f"  ephemeral   : initiator={ep.disappearingModeInitiator}"
                f"  trigger={ep.disappearingModeTrigger}"
            )

        # ── Quoted message ────────────────────────────────────────────────────
        q = self.quoted
        if q.fromQuotedMsg:
            lines.append(f"  ↩ quotedId   : {q.quotedMsgId}")
            if q.quotedmsgtype:
                lines.append(f"  ↩ quotedType : {q.quotedmsgtype}")
            if q.quotedMsgBody:
                lines.append(
                    f"  ↩ quotedBody : {q.quotedMsgBody[:80]}"
                    f"{'…' if len(q.quotedMsgBody or '') > 80 else ''}"
                )
            if q.quotedParticipant:
                lines.append(f"  ↩ quotedFrom : {q.quotedParticipant}")
            if q.quotedRemoteJid:
                lines.append(f"  ↩ quotedChat : {q.quotedRemoteJid}")

        # ── Mentions ──────────────────────────────────────────────────────────
        mentions = self.sender.mentionedJidList
        if mentions:
            lines.append(f"  mentions    : {len(mentions)} user(s)")
            if len(mentions) <= 3:
                lines.append(f"                {', '.join(mentions)}")
            else:
                lines.append(
                    f"                {', '.join(mentions[:3])} (+{len(mentions) - 3} more)"
                )

        # ── Media ─────────────────────────────────────────────────────────────
        m = self.media
        if m.mimetype:
            lines.append(f"  mimetype    : {m.mimetype}")
        if m.size:
            sz = m.size
            if sz >= 1_048_576:
                size_str = f"{sz / 1_048_576:.2f} MB"
            elif sz >= 1024:
                size_str = f"{sz / 1024:.1f} KB"
            else:
                size_str = f"{sz} bytes"
            lines.append(f"  size        : {size_str}")
        if m.duration:
            lines.append(f"  duration    : {m.duration}s")

        # ── Poll detail ───────────────────────────────────────────────────────
        p = self.poll
        if p.isQuestion:
            if p.pollName:
                lines.append(f"  pollName    : {p.pollName}")
            if p.pollType:
                lines.append(
                    f"  pollType    : {p.pollType}  content={p.pollContentType}"
                )
            if p.pollSelectableOptionsCount is not None:
                sel = p.pollSelectableOptionsCount
                lines.append(
                    f"  pollSelect  : {sel if sel else 'unlimited'} option(s) per voter"
                )

        # ── Event detail ──────────────────────────────────────────────────────
        ev = self.event
        if id_.msgtype == "event_creation":
            if ev.eventName:
                lines.append(f"  eventName   : {ev.eventName}")
            if ev.eventDescription:
                desc = ev.eventDescription
                lines.append(
                    f"  eventDesc   : {desc[:80]}{'…' if len(desc) > 80 else ''}"
                )
            if ev.eventStartTime:
                lines.append(f"  eventTime   : {ev.eventStartTime} → {ev.eventEndTime}")
            if ev.eventJoinLink:
                lines.append(f"  eventLink   : {ev.eventJoinLink}")
            if ev.isEventCanceled:
                lines.append("  ⚠ EVENT CANCELED")
            if ev.eventIsScheduledCall:
                lines.append("  eventKind   : scheduled call")

        # ── vCard detail ──────────────────────────────────────────────────────
        vc = self.vcard
        if id_.msgtype in ("vcard", "multi_vcard"):
            if vc.vcardFormattedName:
                lines.append(f"  vcardName   : {vc.vcardFormattedName}")
            if vc.vcardList:
                lines.append(f"  vcardCount  : {len(vc.vcardList)} contact(s)")

        lines.append("───────────────────────────────────────────────────")
        return "\n".join(lines)

    def __repr__(self) -> str:
        id_ = self.identity
        return (
            f"MessageModelAPI("
            f"id='{id_.id_serialized}', "
            f"type='{id_.msgtype}', "
            f"fromMe={id_.fromMe}, "
            f"timestamp={id_.timestamp}"
            f")"
        )
