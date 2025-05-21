from datetime import datetime
from typing import ClassVar, Literal

from oibot.api.send_message import (
    Ark,
    Keyboard,
    Markdown,
    SendMessageResponse,
    send_message,
)
from oibot.event import Context, Event


class FriendAdd(Event):
    __slots__ = ("__weakref__", "timestamp", "openid", "author")

    class Author:
        __slots__ = ("union_openid",)

        def __init__(self, *, union_openid: str) -> None:
            self.union_openid = union_openid

    event_type: ClassVar[Literal["FRIEND_ADD"]] = "FRIEND_ADD"

    timestamp: datetime
    openid: str
    author: Author

    def __init__(self, *, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.openid = d["openid"]
        self.author = self.Author(union_openid=d["author"]["union_openid"])

        super().__init__(ctx=ctx)

    async def reply(
        self,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        ark: Ark | None = None,
        image: bytes | str | None = None,
        video: bytes | str | None = None,
        voice: bytes | str | None = None,
    ) -> SendMessageResponse:
        return await send_message(
            openid=self.openid,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            ark=ark,
            image=image,
            video=video,
            voice=voice,
            event_id=self._id,
        )
