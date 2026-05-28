import asyncio
from datetime import datetime
from functools import cached_property
from itertools import count
from typing import ClassVar, Literal, NamedTuple

from oibot.api.send_message import (
    Ark,
    Embed,
    Keyboard,
    Markdown,
    Media,
    MessageReference,
    SendMessageResponse,
)
from oibot.bot import OiBot
from oibot.event import Context, Event


class GroupMessageCreateEvent(Event):
    class Author(NamedTuple):
        id: str
        username: str
        bot: bool
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

    futures: ClassVar[dict[tuple[str, str], asyncio.Future]] = {}

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        super().__init__(bot, ctx)

        self.msg_seq = count()

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(
            id=author["id"],
            username=author["username"],
            bot=author["bot"],
            member_openid=author["member_openid"],
            union_openid=author["union_openid"],
        )

    @cached_property
    def attachments(self) -> list[Attachment]:
        return [
            self.Attachment(
                content_type=attachment["content_type"],
                filename=attachment["filename"],
                height=attachment["height"],
                size=attachment["size"],
                url=attachment["url"],
                width=attachment["width"],
            )
            for attachment in self.ctx["d"].get("attachments", [])
        ]

    @cached_property
    def message_scene(self) -> MessageScene:
        message_scene = self.ctx["d"]["message_scene"]

        return self.MessageScene(
            source=message_scene["source"], ext=message_scene["ext"]
        )

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
    ) -> "GroupMessageCreateEvent":
        self.bot.plugin_manager.sessions[
            key := (
                self.bot.bot.get(),
                self.group_openid,
                (
                    getattr(author, "member_openid", None)
                    or getattr(author, "user_openid", None)
                )
                if (author := getattr(self, "author", None))
                else None,
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
