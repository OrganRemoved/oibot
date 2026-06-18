from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from functools import cached_property
from typing import Any, ClassVar, Literal

from oibot.api.interaction import Code
from oibot.api.send_message import Message, SendMessageResponse
from oibot.event import Event


class InteractionCreateEvent(Event):
    class Type(IntEnum):
        MESSAGE_BUTTON = 11
        PRIVATE_MESSAGE_QUICK_MENU = 12

    class ChatType(IntEnum):
        CHANNEL = 0
        GROUP = 1
        PRIVATE = 2

    @dataclass(frozen=True, slots=True)
    class Resolved:
        button_data: str
        button_id: str
        user_id: str | None = None
        feature_id: str | None = None
        message_id: str | None = None

    @dataclass(frozen=True, slots=True)
    class Data:
        resolved: "InteractionCreateEvent.Resolved"
        type: "InteractionCreateEvent.Type"

    event_type: ClassVar[Literal["INTERACTION_CREATE"]] = "INTERACTION_CREATE"

    id: str
    type: Type
    scene: Literal["c2c", "group", "guild"]
    chat_type: ChatType
    timestamp: datetime
    guild_id: str
    channel_id: str
    user_openid: str
    group_openid: str
    group_member_openid: str
    data: Data
    version: Literal[1]

    @cached_property
    def data(self) -> "InteractionCreateEvent.Data":
        data = self.ctx["d"]["data"]

        resolved = data["resolved"]

        return self.Data(
            resolved=self.Resolved(
                button_data=resolved["button_data"],
                button_id=resolved.get("button_id"),
                user_id=resolved.get("user_id"),
                feature_id=resolved.get("feature_id"),
                message_id=resolved.get("message_id"),
            ),
            type=self.Type(data["type"]),
        )

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.ctx["d"]["timestamp"])

    async def interaction(self, code: Code) -> Any:
        return await self.bot.interaction(interaction_id=self.id, code=code)

    async def reply(self, message: str | Message, **kwargs) -> SendMessageResponse:
        kwargs.setdefault("msg_id", self.id)

        if isinstance(message, str):
            message = Message.content(content=message)

        return await self.bot.send_message(
            message=message,
            openid=getattr(self, "user_openid", None),
            group_openid=getattr(self, "group_openid", None),
            **kwargs,
        )
