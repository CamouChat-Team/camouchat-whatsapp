"""
Works on new Wa-js Based api scripts.

Wraps the CHAT api's data into a dataclass
"""

from dataclasses import asdict, dataclass
from typing import Any

from camouchat_core import ChatProtocol

# ──────────────────────────────────────────────
#  Sub-models  (grouped by concern)
# ──────────────────────────────────────────────


@dataclass
class ChatIdentity:
    """
    Who / what this chat is.

    Attributes:
        id_serialized (str | None): The unique serialized JID (WhatsApp ID) of the chat.
        formattedTitle (str | None): The display name or group title shown in the UI.
        groupType (str | None): Type of group (e.g., 'DEFAULT', 'ANNOUNCEMENT', 'PARENT').
        isCommunity (bool | None): Derived property: True if this is a WhatsApp Community
            or Announcement parent.
        proxyName (str | None): Internal Meta proxy type identifier (chat, contact, or msg).
        labels (list | None): Business labels applied to the chat.
    """

    id_serialized: str | None
    formattedTitle: str | None
    groupType: str | None
    isCommunity: bool | None
    proxyName: str | None
    labels: list | None


@dataclass
class ChatActivity:
    """
    Timestamps and read-state counters.

    Attributes:
        timestamp (int | None): The last interaction timestamp (t) of the chat.
        lastChatEntryTimestamp (int | None): Timestamp of the last time someone
            typed/sent something to this chat.
        unreadCount (int | None): Number of unread messages currently in this chat.
        unreadMentionCount (int | None): Number of times you were explicitly
            @mentioned and haven't read it yet.
        unreadMentionsOfMe (list | None): Array of message IDs where you are
            explicitly mentioned but unread.
    """

    timestamp: int | None
    lastChatEntryTimestamp: int | None
    unreadCount: int | None
    unreadMentionCount: int | None
    unreadMentionsOfMe: list | None


@dataclass
class ChatPermissions:
    """
    What you can / cannot do inside this chat.

    Attributes:
        canSend (bool | None): True if you are technically able to type in this chat.
        isReadOnly (bool | None): True if you are not allowed to send messages
            (e.g., Announcements group).
        isAnnounceGrpRestrict (bool | None): True if this is an announcements-only
            group restricting messages.
        isTrusted (bool | None): True if the sender is an existing contact or
            trusted entity.
        isNotSpam (bool | None): True if the chat is marked as known and not spam.
    """

    canSend: bool | None
    isReadOnly: bool | None
    isAnnounceGrpRestrict: bool | None
    isTrusted: bool | None
    isNotSpam: bool | None


@dataclass
class ChatState:
    """
    UI / system state flags.

    Attributes:
        isArchived (bool | None): True if the chat is currently in the archived list.
        isLocked (bool | None): True if the chat is locked with a passcode/biometrics.
        isAutoMuted (bool | None): True if the chat was auto-muted by WhatsApp due to
            size or settings.
        muteExpiration (int | None): Unix timestamp when the chat will be unmuted.
        groupSafetyChecked (bool | None): Internal flag: True if WhatsApp ran a
            scam/safety filter on the group.
    """

    isArchived: bool | None
    isLocked: bool | None
    isAutoMuted: bool | None
    muteExpiration: int | None
    groupSafetyChecked: bool | None


@dataclass
class ChatEphemeral:
    """
    Disappearing-message settings.

    Attributes:
        ephemeralDuration (int | None): The time (in seconds) disappearing messages
            are set to.
        ephemeralSettingTimestamp (int | None): Unix timestamp for when the ephemeral
            setting was toggled.
        disappearingModeTrigger (str | None): How the disappearing mode was triggered
            (e.g., 'chat_settings').
        disappearingModeInitiator (str | None): Who initiated the disappearing mode
            (e.g., 'chat').
    """

    ephemeralDuration: int | None
    ephemeralSettingTimestamp: int | None
    disappearingModeTrigger: str | None
    disappearingModeInitiator: str | None


# ──────────────────────────────────────────────
#  Main model
# ──────────────────────────────────────────────


@dataclass
class ChatModelAPI(ChatProtocol):
    """
    Normalized Data Model for a WhatsApp Chat.

    Attributes are grouped into focused sub-models:
        identity    – who/what the chat is (id, title, group type …)
        activity    – timestamps and unread counters
        permissions – what you can/cannot do in this chat
        state       – UI/system flags (archived, locked, muted …)
        ephemeral   – disappearing-message configuration

    If a field is None it mostly means the webpack was not successfully patched,
    or the webpack IDs changed due to a silent WhatsApp update.
    """

    identity: ChatIdentity
    activity: ChatActivity
    permissions: ChatPermissions
    state: ChatState
    ephemeral: ChatEphemeral
    optional_attr_list: dict[str, str] | None

    # ── convenience properties ──────────────────

    @property
    def name(self) -> str:  # type: ignore[override]
        return self.identity.formattedTitle or self.identity.id_serialized or "Unknown"

    @property
    def ui(self):  # type: ignore[override]
        return None

    # ── backwards-compat flat properties ────────
    #  Allows existing code using chat.isArchived,
    #  chat.unreadCount, etc. to keep working unchanged.

    # identity
    @property
    def id_serialized(self):
        return self.identity.id_serialized

    @property
    def formattedTitle(self):
        return self.identity.formattedTitle

    @property
    def groupType(self):
        return self.identity.groupType

    @property
    def isCommunity(self):
        return self.identity.isCommunity

    @property
    def proxyName(self):
        return self.identity.proxyName

    @property
    def labels(self):
        return self.identity.labels

    # activity
    @property
    def timestamp(self):
        return self.activity.timestamp

    @property
    def lastChatEntryTimestamp(self):
        return self.activity.lastChatEntryTimestamp

    @property
    def unreadCount(self):
        return self.activity.unreadCount

    @property
    def unreadMentionCount(self):
        return self.activity.unreadMentionCount

    @property
    def unreadMentionsOfMe(self):
        return self.activity.unreadMentionsOfMe

    # permissions
    @property
    def canSend(self):
        return self.permissions.canSend

    @property
    def isReadOnly(self):
        return self.permissions.isReadOnly

    @property
    def isAnnounceGrpRestrict(self):
        return self.permissions.isAnnounceGrpRestrict

    @property
    def isTrusted(self):
        return self.permissions.isTrusted

    @property
    def isNotSpam(self):
        return self.permissions.isNotSpam

    # state
    @property
    def isArchived(self):
        return self.state.isArchived

    @property
    def isLocked(self):
        return self.state.isLocked

    @property
    def isAutoMuted(self):
        return self.state.isAutoMuted

    @property
    def muteExpiration(self):
        return self.state.muteExpiration

    @property
    def groupSafetyChecked(self):
        return self.state.groupSafetyChecked

    # ephemeral
    @property
    def ephemeralDuration(self):
        return self.ephemeral.ephemeralDuration

    @property
    def ephemeralSettingTimestamp(self):
        return self.ephemeral.ephemeralSettingTimestamp

    @property
    def disappearingModeTrigger(self):
        return self.ephemeral.disappearingModeTrigger

    @property
    def disappearingModeInitiator(self):
        return self.ephemeral.disappearingModeInitiator

    # ── constructors ────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> "ChatModelAPI":
        """
        Build a ChatModelAPI from a raw WA-JS dict.

        :param data: Raw dict from the WhatsApp webpack.
        :return: ChatModelAPI
        """

        def get_val(key: str, default: Any = None):
            return data.get(key, data.get(f"__x_{key}", default))

        id_data = data.get("id") or {}
        is_parent = get_val("isParentGroup", False)
        group_type = get_val("groupType", "DEFAULT")
        t_val = get_val("t")

        return cls(
            identity=ChatIdentity(
                id_serialized=get_val("id_serialized") or id_data.get("_serialized"),
                formattedTitle=get_val("formattedTitle") or get_val("name"),
                groupType=group_type,
                isCommunity=(is_parent is True) or (group_type == "ANNOUNCEMENT"),
                proxyName=get_val("proxyName"),
                labels=get_val("labels"),
            ),
            activity=ChatActivity(
                timestamp=t_val if t_val is not None else get_val("timestamp"),
                lastChatEntryTimestamp=get_val("lastChatEntryTimestamp"),
                unreadCount=get_val("unreadCount"),
                unreadMentionCount=get_val("unreadMentionCount"),
                unreadMentionsOfMe=get_val("unreadMentionsOfMe"),
            ),
            permissions=ChatPermissions(
                canSend=get_val("canSend"),
                isReadOnly=get_val("isReadOnly"),
                isAnnounceGrpRestrict=get_val("isAnnounceGrpRestrict"),
                isTrusted=get_val("trusted"),
                isNotSpam=get_val("notSpam"),
            ),
            state=ChatState(
                isArchived=get_val("archive"),
                isLocked=get_val("isLocked"),
                isAutoMuted=get_val("isAutoMuted"),
                muteExpiration=get_val("muteExpiration"),
                groupSafetyChecked=get_val("groupSafetyChecked"),
            ),
            ephemeral=ChatEphemeral(
                ephemeralDuration=get_val("ephemeralDuration"),
                ephemeralSettingTimestamp=get_val("ephemeralSettingTimestamp"),
                disappearingModeTrigger=get_val("disappearingModeTrigger"),
                disappearingModeInitiator=get_val("disappearingModeInitiator"),
            ),
            optional_attr_list=get_val("optionalAttrList"),
        )

    # ── serialisation ───────────────────────────

    def to_dict(self, include_none: bool = False) -> dict:
        """
        Export this ChatModelAPI as a flat Python dict.

        :param include_none: When True, keys whose value is None are included.
        :return: dict
        """
        raw = {
            **asdict(self.identity),
            **asdict(self.activity),
            **asdict(self.permissions),
            **asdict(self.state),
            **asdict(self.ephemeral),
            "optional_attr_list": self.optional_attr_list,
        }
        if include_none:
            return raw
        return {k: v for k, v in raw.items() if v is not None}

    # ── dunder helpers ──────────────────────────

    def __str__(self) -> str:
        i = self.identity
        a = self.activity
        p = self.permissions
        s = self.state
        e = self.ephemeral

        lines = [
            "─── ChatModelAPI ──────────────────────────────────",
            f"  id          : {i.id_serialized}",
            f"  title       : {i.formattedTitle or '(empty name)'}",
            f"  type        : {'Community' if i.isCommunity else 'Chat'}",
            f"  timestamp   : {a.timestamp}",
            f"  unread      : {a.unreadCount or 0}  (@mentions: {a.unreadMentionCount or 0})",
            f"  status      : {'Archived' if s.isArchived else 'Active'}",
        ]

        flags = []
        if p.isReadOnly:
            flags.append("read-only")
        if s.isLocked:
            flags.append("locked")
        if s.isAutoMuted:
            flags.append("auto-muted")
        if p.isTrusted is False:
            flags.append("untrusted(not-in-contacts)")
        if p.isNotSpam is False:
            flags.append("spam-flagged")
        if p.canSend is False:
            flags.append("cannot-send")

        if flags:
            lines.append(f"  flags       : {', '.join(flags)}")

        if p.isAnnounceGrpRestrict:
            lines.append("  permissions : announcements-only (restricted)")

        if s.muteExpiration:
            lines.append(f"  muted-until : {s.muteExpiration}")

        if i.labels:
            lines.append(f"  labels      : {', '.join(i.labels)}")

        if e.ephemeralDuration or e.disappearingModeTrigger:
            dur = f" duration={e.ephemeralDuration}s" if e.ephemeralDuration else ""
            init = (
                f" initiator={e.disappearingModeInitiator}"
                if e.disappearingModeInitiator
                else ""
            )
            trig = (
                f" trigger={e.disappearingModeTrigger}"
                if e.disappearingModeTrigger
                else ""
            )
            lines.append(f"  ephemeral   :{dur}{init}{trig}")

        lines.append("───────────────────────────────────────────────────")
        return "\n".join(lines)

    def __repr__(self) -> str:
        i = self.identity
        return (
            f"ChatModelAPI("
            f"id='{i.id_serialized}', "
            f"title='{i.formattedTitle}', "
            f"unread={self.activity.unreadCount}, "
            f"archived={self.state.isArchived}, "
            f"community={i.isCommunity}"
            f")"
        )
