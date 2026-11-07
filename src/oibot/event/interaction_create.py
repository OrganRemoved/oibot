import asyncio
import builtins
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Literal, overload

from oibot.api.interaction import Code
from oibot.api.message import Keyboard, Message, MessageResponse, MsgType
from oibot.event import Context, Event, EventType

if TYPE_CHECKING:
    from oibot.event.c2c_message_create import C2CMessageCreateEvent
    from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
    from oibot.event.group_message_create import GroupMessageCreateEvent


class InteractionCreateEvent(Event):
    class Type(IntEnum):
        INLINE_KEYBOARD = 11
        CALLBACK_COMMAND = 12
        MESSAGE_FEEDBACK = 13
        CLEAR_SESSION = 14
        IN_OUT_STORY = 15
        SWITCH_MODEL = 16
        USER_AUTHORIZE = 18
        GROUP_AUTHORIZE = 19
        GROUP_AUTHORIZE_STATUS = 20

    class ChatType(IntEnum):
        CHANNEL = 0
        GROUP = 1
        PRIVATE = 2

    @dataclass(frozen=True, slots=True)
    class MessageScene:
        ext: list[str]

    @dataclass(frozen=True, slots=True)
    class AuthorizeData:
        opt_scene: Literal["setting", "dialog"]
        scope: Literal["c2c_push", "group_push"]

    @dataclass(frozen=True, slots=True)
    class Resolved:
        button_data: str | None = None
        button_id: str | None = None
        user_id: str | None = None
        feature_id: str | None = None
        message_id: str | None = None
        feedback_opt: Literal["LIKE", "UNLIKE"] | None = None
        checked: int | None = None
        action: str | None = None
        message_scene: InteractionCreateEvent.MessageScene | None = None
        authorize_data: InteractionCreateEvent.AuthorizeData | None = None

    @dataclass(frozen=True, slots=True)
    class Data:
        resolved: InteractionCreateEvent.Resolved
        type: InteractionCreateEvent.Type | None = None

    event_type: ClassVar[EventType] = EventType.INTERACTION_CREATE

    scenes: ClassVar[dict[str, builtins.type[InteractionCreateEvent]]] = {}

    id: str
    type: Type
    scene: Literal["c2c", "group", "guild"]
    chat_type: ChatType | None
    timestamp: datetime
    data: Data
    version: int
    application_id: str

    def __init_subclass__(
        cls, *, scene: Literal["c2c", "group", "guild"], **kwargs: Any
    ) -> None:
        super().__init_subclass__(**kwargs)

        InteractionCreateEvent.scenes.setdefault(scene, cls)

    @classmethod
    def dispatch(cls, ctx: Context) -> builtins.type[InteractionCreateEvent]:
        return cls.scenes.get(ctx["d"]["scene"], cls)

    @cached_property
    def type(self) -> Type:
        return self.Type(self.ctx["d"]["type"])

    @cached_property
    def data(self) -> InteractionCreateEvent.Data:
        data = self.ctx["d"]["data"]
        resolved = data["resolved"]

        return self.Data(
            resolved=self.Resolved(
                button_data=resolved.get("button_data"),
                button_id=resolved.get("button_id"),
                user_id=resolved.get("user_id"),
                feature_id=resolved.get("feature_id"),
                message_id=resolved.get("message_id"),
                feedback_opt=resolved.get("feedback_opt"),
                checked=resolved.get("checked"),
                action=resolved.get("action"),
                message_scene=(
                    self.MessageScene(ext=message_scene["ext"])
                    if (message_scene := resolved.get("message_scene"))
                    else None
                ),
                authorize_data=(
                    self.AuthorizeData(
                        opt_scene=authorize_data["opt_scene"],
                        scope=authorize_data["scope"],
                    )
                    if (authorize_data := resolved.get("authorize_data"))
                    else None
                ),
            ),
            type=self.Type(data["type"]) if "type" in data else None,
        )

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.ctx["d"]["timestamp"])

    @cached_property
    def button_data(self) -> dict[str, Any]:
        return json.loads(self.data.resolved.button_data)

    @cached_property
    def button_id(self) -> str:
        return self.data.resolved.button_id

    async def acknowledge(self, code: Code) -> None:
        return await self.bot.acknowledge_interaction(interaction_id=self.id, code=code)


class C2CInteractionCreateEvent(InteractionCreateEvent, scene="c2c"):
    scene: Literal["c2c"]

    user_openid: str

    async def reply(
        self, message: str | Message | Message[Keyboard]
    ) -> MessageResponse:
        message = Message.content(message) if isinstance(message, str) else message

        return await self.bot.send_user_message(
            openid=self.user_openid, message=message
        )

    @overload
    async def chat(
        self, message: Message[Keyboard], *, timeout: float | timedelta | None = None
    ) -> C2CInteractionCreateEvent: ...

    @overload
    async def chat(
        self, message: str | Message, *, timeout: float | timedelta | None = None
    ) -> C2CMessageCreateEvent: ...

    async def chat(
        self,
        message: str | Message | Message[Keyboard],
        *,
        timeout: float | timedelta | None = None,
    ) -> C2CMessageCreateEvent | C2CInteractionCreateEvent:
        message = (
            Message.content(message) if isinstance(message, str) else deepcopy(message)
        )

        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()

        match message["msg_type"]:
            case MsgType.PLAINTEXT | MsgType.MEDIA:
                async with self.bot.session_manager.defer(self.user_openid) as future:
                    await self.reply(message)

                    return await asyncio.wait_for(future, timeout=timeout)

            case MsgType.MARKDOWN | MsgType.CARD:
                if "keyboard" in message:
                    button_ids = []

                    for row in message["keyboard"]["content"]["rows"]:
                        for button in row["buttons"]:
                            button["id"] = button_id = f"{button['id']}_{self.id}"
                            button_ids.append(button_id)

                    async with self.bot.session_manager.defer(*button_ids) as future:
                        await self.reply(message)

                        return await asyncio.wait_for(future, timeout=timeout)

                async with self.bot.session_manager.defer(self.user_openid) as future:
                    await self.reply(message)

                    return await asyncio.wait_for(future, timeout=timeout)

            case _:
                raise ValueError(f"unsupport message type {message['msg_type']=}")


class GroupInteractionCreateEvent(InteractionCreateEvent, scene="group"):
    scene: Literal["group"]

    group_openid: str
    group_member_openid: str

    async def reply(
        self, message: str | Message | Message[Keyboard]
    ) -> MessageResponse:
        message = Message.content(message) if isinstance(message, str) else message

        return await self.bot.send_group_message(
            group_openid=self.group_openid, message=message
        )

    @overload
    async def chat(
        self, message: Message[Keyboard], *, timeout: float | timedelta | None = None
    ) -> GroupInteractionCreateEvent: ...

    @overload
    async def chat(
        self, message: str | Message, *, timeout: float | timedelta | None = None
    ) -> GroupAtMessageCreateEvent | GroupMessageCreateEvent: ...

    async def chat(
        self,
        message: str | Message | Message[Keyboard],
        *,
        timeout: float | timedelta | None = None,
    ) -> (
        GroupAtMessageCreateEvent
        | GroupMessageCreateEvent
        | GroupInteractionCreateEvent
    ):
        message = (
            Message.content(message) if isinstance(message, str) else deepcopy(message)
        )

        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()

        match message["msg_type"]:
            case MsgType.PLAINTEXT | MsgType.MEDIA:
                async with self.bot.session_manager.defer(
                    self.group_member_openid
                ) as future:
                    await self.reply(message)

                    return await asyncio.wait_for(future, timeout=timeout)

            case MsgType.MARKDOWN | MsgType.CARD:
                if "keyboard" in message:
                    button_ids = []

                    for row in message["keyboard"]["content"]["rows"]:
                        for button in row["buttons"]:
                            button["id"] = button_id = f"{button['id']}_{self.id}"
                            button_ids.append(button_id)

                    async with self.bot.session_manager.defer(*button_ids) as future:
                        await self.reply(message)

                        return await asyncio.wait_for(future, timeout=timeout)

                async with self.bot.session_manager.defer(
                    self.group_member_openid
                ) as future:
                    await self.reply(message)

                    return await asyncio.wait_for(future, timeout=timeout)

            case _:
                raise ValueError(f"unsupport message type {message['msg_type']=}")


class GuildInteractionCreateEvent(InteractionCreateEvent, scene="guild"):
    scene: Literal["guild"]

    guild_id: str
    channel_id: str
