import asyncio
from datetime import datetime
from itertools import count
from typing import ClassVar, Literal, NamedTuple

from oibot.bot import OiBot
from oibot.event import Context, Event
from oibot.mixin.send_message import (
    Ark,
    Embed,
    Keyboard,
    Markdown,
    Media,
    MessageReference,
    SendMessageResponse,
)


class C2CMessageCreateEvent(Event):
    __slots__ = (
        "id",
        "content",
        "timestamp",
        "author",
        "attachments",
        "message_scene",
        "message_type",
        "msg_seq",
    )

    class Author(NamedTuple):
        id: str
        user_openid: str
        union_openid: str

    class Attachment(NamedTuple):
        content_type: str
        filename: str
        height: int
        size: int
        url: str
        width: int

    class MessageScene(NamedTuple):
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

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.id = d["id"]
        self.content = d["content"]
        self.timestamp = d["timestamp"]

        self.author = self.Author(
            id=d["author"]["id"],
            user_openid=d["author"]["user_openid"],
            union_openid=d["author"]["union_openid"],
        )

        self.attachments = [
            self.Attachment(
                content_type=attachment["content_type"],
                filename=attachment["filename"],
                height=attachment["height"],
                size=attachment["size"],
                url=attachment["url"],
                width=attachment["width"],
            )
            for attachment in d.get("attachments", [])
        ]

        self.message_scene = self.MessageScene(
            source=d["message_scene"]["source"],
            callback_data=d["message_scene"]["callback_data"],
        )
        self.message_type = d["message_type"]

        super().__init__(bot, ctx)

        self.msg_seq = count()

    async def reply(
        self,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_seq: int = 0,
    ) -> SendMessageResponse:
        return await self.bot.send_private_message(
            openid=self.author.union_openid,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            embed=embed,
            ark=ark,
            media=media,
            message_reference=message_reference,
            event_id=event_id,
            msg_id=self.id,
            msg_seq=msg_seq or next(self.msg_seq),
        )

    async def defer(
        self,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_seq: int = 0,
    ) -> "C2CMessageCreateEvent":
        self.bot.plugin_manager.sessions[
            key := (
                self.bot.bot.get(),
                getattr(self, "group_openid", None),
                (
                    getattr(self, "author.member_openid", None)
                    or getattr(self, "author.user_openid", None)
                ),
            )
        ] = future = asyncio.get_running_loop().create_future()

        await self.reply(
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            embed=embed,
            ark=ark,
            media=media,
            message_reference=message_reference,
            event_id=event_id,
            msg_seq=msg_seq,
        )

        try:
            return await future

        finally:
            self.bot.plugin_manager.sessions.pop(key, None)
