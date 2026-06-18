from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.api.send_message import Message, SendMessageResponse
from oibot.event import Event


class GroupMessageCreateEvent(Event):
    @dataclass(frozen=True, slots=True)
    class Author:
        id: str
        username: str
        bot: bool
        member_openid: str
        union_openid: str
        member_role: Literal["owner", "admin", "member"]

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
        ext: list[str]

    event_type: ClassVar[Literal["GROUP_MESSAGE_CREATE"]] = "GROUP_MESSAGE_CREATE"

    id: str
    content: str
    timestamp: datetime
    author: Author
    attachments: list[Attachment]

    group_id: str
    group_openid: str

    message_scene: MessageScene
    message_type: int

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(
            id=author["id"],
            username=author["username"],
            bot=author["bot"],
            member_openid=author["member_openid"],
            union_openid=author["union_openid"],
            member_role=author["member_role"],
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
            source=message_scene["source"], ext=message_scene["ext"]
        )

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: str | Message, **kwargs) -> SendMessageResponse:
        kwargs.setdefault("msg_id", self.id)

        if isinstance(message, str):
            message = Message.content(content=message)

        return await self.bot.send_message(
            message=message, group_openid=self.group_openid, **kwargs
        )

    async def defer(
        self, message: str | Message, **kwargs
    ) -> "GroupMessageCreateEvent":
        async with self.bot.plugin_manager.session_manager.defer(
            self.member_openid
        ) as future:
            await self.reply(message=message, **kwargs)

            return await future
