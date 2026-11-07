import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, ClassVar, Literal, overload

from oibot.api.message import (
    Keyboard,
    Message,
    MessageReference,
    MessageResponse,
    MsgType,
)
from oibot.event import Event, EventType

if TYPE_CHECKING:
    from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
    from oibot.event.interaction_create import GroupInteractionCreateEvent


class GroupMessageCreateEvent(Event):
    class MessageType(IntEnum):
        TEXT = 0
        ARK = 3
        PARALLEL = 101
        CHAT_HISTORY = 102
        REFERENCE = 103

    @dataclass(frozen=True, slots=True)
    class Author:
        id: str
        username: str
        bot: bool
        member_openid: str
        member_role: Literal["owner", "admin", "member"]
        union_openid: str | None = None
        union_user_account: str | None = None
        user_openid: str | None = None

    @dataclass(frozen=True, slots=True)
    class Attachment:
        content_type: str
        filename: str
        url: str
        size: int
        asr_refer_text: str | None = None
        voice_wav_url: str | None = None
        height: int | None = None
        width: int | None = None

    @dataclass(frozen=True, slots=True)
    class Mention:
        id: str
        username: str
        bot: bool
        member_openid: str
        scope: str
        is_you: bool
        member_role: Literal["owner", "admin", "member"]

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

    @dataclass(frozen=True, slots=True)
    class MsgElement:
        content: str
        msg_idx: str | None = None
        author: GroupMessageCreateEvent.Author | None = None
        message_type: GroupMessageCreateEvent.MessageType | None = None
        attachments: list[GroupMessageCreateEvent.Attachment] = field(
            default_factory=list
        )
        ark_data: GroupMessageCreateEvent.ArkData | None = None
        msg_elements: list[GroupMessageCreateEvent.MsgElement] = field(
            default_factory=list
        )

    event_type: ClassVar[EventType] = EventType.GROUP_MESSAGE_CREATE

    id: str
    content: str
    timestamp: datetime
    author: Author
    attachments: list[Attachment]
    mentions: list[Mention]
    ark_data: ArkData | None
    msg_elements: list[MsgElement]

    group_openid: str

    message_scene: MessageScene
    message_type: MessageType

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(
            id=author["id"],
            username=author["username"],
            bot=author["bot"],
            member_openid=author["member_openid"],
            member_role=author["member_role"],
            union_openid=author.get("union_openid"),
            union_user_account=author.get("union_user_account"),
            user_openid=author.get("user_openid"),
        )

    @cached_property
    def attachments(self) -> list[Attachment]:
        return [
            self.Attachment(
                asr_refer_text=attachment.get("asr_refer_text"),
                content_type=attachment["content_type"],
                filename=attachment["filename"],
                height=attachment.get("height"),
                size=attachment["size"],
                url=attachment["url"],
                voice_wav_url=attachment.get("voice_wav_url"),
                width=attachment.get("width"),
            )
            for attachment in self.ctx["d"].get("attachments", [])
        ]

    @cached_property
    def mentions(self) -> list[Mention]:
        return [
            self.Mention(
                id=mention["id"],
                username=mention["username"],
                bot=mention["bot"],
                member_openid=mention["member_openid"],
                scope=mention["scope"],
                is_you=mention["is_you"],
                member_role=mention["member_role"],
            )
            for mention in self.ctx["d"].get("mentions", [])
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
    def msg_elements(self) -> list[MsgElement]:
        msg_elements: list[GroupMessageCreateEvent.MsgElement] = []

        stack: list[tuple[dict[str, Any], list[GroupMessageCreateEvent.MsgElement]]] = [
            (element, msg_elements)
            for element in reversed(self.ctx["d"].get("msg_elements", []))
        ]

        while stack:
            element, target = stack.pop()

            children: list[GroupMessageCreateEvent.MsgElement] = []

            target.append(
                self.MsgElement(
                    content=element["content"],
                    msg_idx=element.get("msg_idx"),
                    author=(
                        self.Author(
                            id=author["id"],
                            username=author["username"],
                            bot=author["bot"],
                            member_openid=author["member_openid"],
                            member_role=author["member_role"],
                            union_openid=author.get("union_openid"),
                            union_user_account=author.get("union_user_account"),
                            user_openid=author.get("user_openid"),
                        )
                        if (author := element.get("author"))
                        else None
                    ),
                    message_type=(
                        self.MessageType(message_type)
                        if (message_type := element.get("message_type")) is not None
                        else None
                    ),
                    attachments=[
                        self.Attachment(
                            asr_refer_text=attachment.get("asr_refer_text"),
                            content_type=attachment["content_type"],
                            filename=attachment["filename"],
                            height=attachment.get("height"),
                            size=attachment["size"],
                            url=attachment["url"],
                            voice_wav_url=attachment.get("voice_wav_url"),
                            width=attachment.get("width"),
                        )
                        for attachment in element.get("attachments", [])
                    ],
                    ark_data=(
                        self.ArkData(
                            prompt=ark_data["prompt"],
                            ark_type=ark_data["ark_type"],
                            ark_name=ark_data["ark_name"],
                            fields=ark_data["fields"],
                        )
                        if (ark_data := element.get("ark_data"))
                        else None
                    ),
                    msg_elements=children,
                )
            )

            stack.extend(
                (child, children) for child in reversed(element.get("msg_elements", []))
            )

        return msg_elements

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.ctx["d"]["timestamp"])

    async def reply(
        self, message: str | Message | Message[Keyboard], *, quote: bool = False
    ) -> MessageResponse:
        message = Message.content(message) if isinstance(message, str) else message

        if quote:
            message["message_reference"] = MessageReference(
                message_id=self.message_scene.ext["msg_idx"]
            )

        return await self.bot.send_group_message(
            group_openid=self.group_openid, message=message
        )

    @overload
    async def chat(
        self,
        message: Message[Keyboard],
        *,
        quote: bool = False,
        timeout: float | timedelta | None = None,
    ) -> GroupInteractionCreateEvent: ...

    @overload
    async def chat(
        self,
        message: str | Message,
        *,
        quote: bool = False,
        timeout: float | timedelta | None = None,
    ) -> GroupAtMessageCreateEvent | GroupMessageCreateEvent: ...

    async def chat(
        self,
        message: str | Message | Message[Keyboard],
        *,
        quote: bool = False,
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
                    self.author.member_openid
                ) as future:
                    await self.reply(message, quote=quote)

                    return await asyncio.wait_for(future, timeout=timeout)

            case MsgType.MARKDOWN | MsgType.CARD:
                if "keyboard" in message:
                    button_ids = []

                    for row in message["keyboard"]["content"]["rows"]:
                        for button in row["buttons"]:
                            button["id"] = button_id = f"{button['id']}_{self.id}"

                            button_ids.append(button_id)

                    async with self.bot.session_manager.defer(*button_ids) as future:
                        await self.reply(message, quote=quote)

                        return await asyncio.wait_for(future, timeout=timeout)

                async with self.bot.session_manager.defer(
                    self.author.member_openid
                ) as future:
                    await self.reply(message, quote=quote)

                    return await asyncio.wait_for(future, timeout=timeout)

            case _:
                raise ValueError(f"unsupport message type {message['msg_type']=}")
