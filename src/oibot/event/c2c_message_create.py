import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Literal, overload

from oibot.api.message import Keyboard, Message, MessageResponse, MsgType
from oibot.event import Event, EventType

if TYPE_CHECKING:
    from oibot.event.interaction_create import C2CInteractionCreateEvent


class C2CMessageCreateEvent(Event):
    class MessageType(IntEnum):
        TEXT = 0
        ARK = 3
        PARALLEL = 101
        CHAT_HISTORY = 102
        REFERENCE = 103

    @dataclass(frozen=True, slots=True)
    class Author:
        id: str
        user_openid: str
        union_openid: str

    @dataclass(frozen=True, slots=True)
    class Attachment:
        content_type: str
        filename: str
        url: str
        asr_refer_text: str | None = None
        voice_wav_url: str | None = None
        height: int | None = None
        width: int | None = None
        size: int | None = None

    @dataclass(frozen=True, slots=True)
    class MessageScene:
        source: str
        ext: dict[str, str]

    @dataclass(frozen=True, slots=True)
    class ArkData:
        prompt: str
        ark_type: Literal[
            "tuwen",
            "feed",
            "miniapp",
            "map",
            "contact_card",
            "video_share",
            "music_together",
            "picture",
        ]
        ark_name: str
        fields: dict[str, Any]

    event_type: ClassVar[EventType] = EventType.C2C_MESSAGE_CREATE

    id: str
    content: str
    timestamp: datetime
    author: Author
    attachments: list[Attachment]
    ark_data: ArkData | None

    message_scene: MessageScene
    message_type: MessageType

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(
            id=author["id"],
            user_openid=author["user_openid"],
            union_openid=author["union_openid"],
        )

    @cached_property
    def attachments(self) -> list[Attachment]:
        return [
            self.Attachment(
                asr_refer_text=attachment.get("asr_refer_text"),
                content_type=attachment["content_type"],
                filename=attachment["filename"],
                height=attachment.get("height"),
                size=attachment.get("size"),
                url=attachment["url"],
                voice_wav_url=attachment.get("voice_wav_url"),
                width=attachment.get("width"),
            )
            for attachment in self.ctx["d"].get("attachments", [])
        ]

    @cached_property
    def message_scene(self) -> MessageScene:
        message_scene = self.ctx["d"]["message_scene"]

        return self.MessageScene(
            source=message_scene["source"],
            ext=dict(item.split("=", 1) for item in message_scene["ext"]),
        )

    @cached_property
    def message_type(self) -> MessageType:
        return self.MessageType(self.ctx["d"]["message_type"])

    @cached_property
    def ark_data(self) -> ArkData | None:
        if ark_data := self.ctx["d"].get("ark_data"):
            return self.ArkData(
                prompt=ark_data["prompt"],
                ark_type=ark_data["ark_type"],
                ark_name=ark_data["ark_name"],
                fields=ark_data["fields"],
            )

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.ctx["d"]["timestamp"])

    async def reply(
        self, message: str | Message | Message[Keyboard]
    ) -> MessageResponse:
        message = Message.content(message) if isinstance(message, str) else message

        return await self.bot.send_user_message(
            openid=self.author.user_openid, message=message
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
                async with self.bot.session_manager.defer(
                    self.author.user_openid
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
                    self.author.user_openid
                ) as future:
                    await self.reply(message)

                    return await asyncio.wait_for(future, timeout=timeout)

            case _:
                raise ValueError(f"unsupport message type {message['msg_type']=}")
