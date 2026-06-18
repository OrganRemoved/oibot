from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.api.send_message import Message, SendMessageResponse
from oibot.event import Event


class C2CMessageCreateEvent(Event):
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
        callback_data: str

    event_type: ClassVar[Literal["C2C_MESSAGE_CREATE"]] = "C2C_MESSAGE_CREATE"

    id: str
    content: str
    timestamp: datetime
    author: Author
    attachments: list[Attachment]

    message_scene: MessageScene
    message_type: int

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
            source=message_scene["source"], callback_data=message_scene["callback_data"]
        )

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: str | Message, **kwargs) -> SendMessageResponse:
        kwargs.setdefault("msg_id", self.id)

        if isinstance(message, str):
            message = Message.content(content=message)

        return await self.bot.send_message(
            message=message, openid=self.author.user_openid, **kwargs
        )

    async def defer(self, message: str | Message, **kwargs) -> "C2CMessageCreateEvent":
        async with self.bot.plugin_manager.session_manager.defer(self.openid) as future:
            await self.reply(message=message, **kwargs)

            return await future
