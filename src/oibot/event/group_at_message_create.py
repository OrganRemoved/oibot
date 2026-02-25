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


class GroupAtMessageCreateEvent(Event):
    __slots__ = (
        "id",
        "content",
        "timestamp",
        "author",
        "attachments",
        "group_id",
        "group_openid",
        "message_scene",
        "message_type",
        "msg_seq",
    )

    class Author(NamedTuple):
        id: str
        member_openid: str
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

    event_type: ClassVar[Literal["GROUP_AT_MESSAGE_CREATE"]] = "GROUP_AT_MESSAGE_CREATE"

    id: str
    content: str
    timestamp: datetime
    author: Author
    attachments: list[Attachment]

    group_id: str
    group_openid: str

    message_scene: MessageScene
    message_type: int

    futures: ClassVar[dict[tuple[str, str], asyncio.Future]] = {}

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.id = d["id"]
        self.content = d["content"]
        self.timestamp = d["timestamp"]

        self.author = self.Author(
            id=d["author"]["id"],
            member_openid=d["author"]["member_openid"],
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

        self.group_id = d["group_id"]
        self.group_openid = d["group_openid"]
        self.message_scene = self.MessageScene(source=d["message_scene"]["source"])
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
        return await self.bot.send_group_message(
            group_openid=self.group_openid,
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
    ) -> "GroupAtMessageCreateEvent":
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
