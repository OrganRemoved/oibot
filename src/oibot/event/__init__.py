import logging
from enum import StrEnum
from typing import ClassVar, TypedDict

from oibot.bot import OiBot


class EventType(StrEnum):
    AT_MESSAGE_CREATE = "AT_MESSAGE_CREATE"
    AUDIO_FINISH = "AUDIO_FINISH"
    AUDIO_OR_LIVE_CHANNEL_MEMBER_ENTER = "AUDIO_OR_LIVE_CHANNEL_MEMBER_ENTER"
    AUDIO_OR_LIVE_CHANNEL_MEMBER_EXIT = "AUDIO_OR_LIVE_CHANNEL_MEMBER_EXIT"
    AUDIO_START = "AUDIO_START"
    C2C_MESSAGE_CREATE = "C2C_MESSAGE_CREATE"
    C2C_MSG_RECEIVE = "C2C_MSG_RECEIVE"
    C2C_MSG_REJECT = "C2C_MSG_REJECT"
    CHANNEL_CREATE = "CHANNEL_CREATE"
    CHANNEL_DELETE = "CHANNEL_DELETE"
    CHANNEL_UPDATE = "CHANNEL_UPDATE"
    DIRECT_MESSAGE_CREATE = "DIRECT_MESSAGE_CREATE"
    DIRECT_MESSAGE_DELETE = "DIRECT_MESSAGE_DELETE"
    FORUM_POST_CREATE = "FORUM_POST_CREATE"
    FORUM_POST_DELETE = "FORUM_POST_DELETE"
    FORUM_PUBLISH_AUDIT_RESULT = "FORUM_PUBLISH_AUDIT_RESULT"
    FORUM_REPLY_CREATE = "FORUM_REPLY_CREATE"
    FORUM_REPLY_DELETE = "FORUM_REPLY_DELETE"
    FORUM_THREAD_CREATE = "FORUM_THREAD_CREATE"
    FORUM_THREAD_DELETE = "FORUM_THREAD_DELETE"
    FORUM_THREAD_UPDATE = "FORUM_THREAD_UPDATE"
    FRIEND_ADD = "FRIEND_ADD"
    FRIEND_DEL = "FRIEND_DEL"
    GROUP_ADD_ROBOT = "GROUP_ADD_ROBOT"
    GROUP_AT_MESSAGE_CREATE = "GROUP_AT_MESSAGE_CREATE"
    GROUP_DEL_ROBOT = "GROUP_DEL_ROBOT"
    GROUP_MSG_RECEIVE = "GROUP_MSG_RECEIVE"
    GROUP_MSG_REJECT = "GROUP_MSG_REJECT"
    GUILD_CREATE = "GUILD_CREATE"
    GUILD_DELETE = "GUILD_DELETE"
    GUILD_MEMBER_ADD = "GUILD_MEMBER_ADD"
    GUILD_MEMBER_REMOVE = "GUILD_MEMBER_REMOVE"
    GUILD_MEMBER_UPDATE = "GUILD_MEMBER_UPDATE"
    GUILD_UPDATE = "GUILD_UPDATE"
    INTERACTION_CREATE = "INTERACTION_CREATE"
    MESSAGE_AUDIT_PASS = "MESSAGE_AUDIT_PASS"
    MESSAGE_AUDIT_REJECT = "MESSAGE_AUDIT_REJECT"
    MESSAGE_CREATE = "MESSAGE_CREATE"
    MESSAGE_DELETE = "MESSAGE_DELETE"
    MESSAGE_REACTION_ADD = "MESSAGE_REACTION_ADD"
    MESSAGE_REACTION_REMOVE = "MESSAGE_REACTION_REMOVE"
    OFF_MIC = "OFF_MIC"
    ON_MIC = "ON_MIC"
    OPEN_FORUM_POST_CREATE = "OPEN_FORUM_POST_CREATE"
    OPEN_FORUM_POST_DELETE = "OPEN_FORUM_POST_DELETE"
    OPEN_FORUM_REPLY_CREATE = "OPEN_FORUM_REPLY_CREATE"
    OPEN_FORUM_REPLY_DELETE = "OPEN_FORUM_REPLY_DELETE"
    OPEN_FORUM_THREAD_CREATE = "OPEN_FORUM_THREAD_CREATE"
    OPEN_FORUM_THREAD_DELETE = "OPEN_FORUM_THREAD_DELETE"
    OPEN_FORUM_THREAD_UPDATE = "OPEN_FORUM_THREAD_UPDATE"
    PUBLIC_MESSAGE_DELETE = "PUBLIC_MESSAGE_DELETE"


class Context(TypedDict):
    d: dict
    id: str
    op: int
    s: int
    t: str


class Event:
    __slots__ = ("bot", "_d", "_id", "_op", "_s", "_t")

    _d: dict
    _id: str
    _op: int
    _s: int
    _t: str

    event_type: ClassVar[EventType]

    event: ClassVar[dict[str, type["Event"]]] = {}

    def __new__(cls, bot: OiBot, ctx: Context) -> "Event":
        return (
            event.__new__(event, bot, ctx)
            if (event := cls.dispatch(ctx)) is not cls
            else super().__new__(cls)
        )

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        self.bot = bot

        self._d = ctx["d"]
        self._id = ctx["id"]
        self._op = ctx["op"]
        # self._s = ctx["s"]
        self._t = ctx["t"]

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        logging.debug(f"registered {cls} as type {cls._t}")

        Event.event[cls.event_type] = cls

    def __repr__(self) -> str:
        return f"""{self.__class__.__name__}({
            ", ".join(
                f"{item}={value}"
                for item in self.__slots__
                if (not item.startswith("__")) and (value := getattr(self, item, None))
            )
        })"""

    @classmethod
    def dispatch(cls, ctx: Context) -> type["Event"]:
        return cls.event.get(ctx["t"], cls)
