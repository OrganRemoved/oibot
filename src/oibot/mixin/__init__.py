from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Literal, Optional, Protocol

if TYPE_CHECKING:
    from oibot.bot import Bot
    from oibot.mixin.send_message import (
        Ark,
        Embed,
        Keyboard,
        Markdown,
        Media,
        MessageReference,
        SendMessageResponse,
    )
    from oibot.mixin.upload_file import FileType, UploadFileResponse


class MixinProtocol(Protocol):
    bot: ContextVar["Bot"]

    async def __call__(
        self,
        method: Literal[
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
            "TRACE",
            "CONNECT",
        ],
        url: str,
        **kwargs,
    ) -> Any:
        pass

    async def get_app_access_token(
        self, app_id: str | None = None, app_secret: str | None = None
    ) -> str: ...

    async def recall_private_message(self, *, openid: str, message_id: str) -> None: ...

    async def recall_group_message(
        self, *, group_openid: str, message_id: str
    ) -> None: ...

    async def recall_channel_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        hide_tip: bool = False,
    ) -> None: ...

    async def recall_guild_message(
        self, *, guild_id: str, message_id, hide_tip: bool = False
    ) -> None: ...

    async def upload_private_file(
        self,
        *,
        openid: str,
        file_type: "FileType",
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> "UploadFileResponse": ...

    async def upload_group_file(
        self,
        *,
        group_openid: str,
        file_type: "FileType",
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> "UploadFileResponse": ...

    async def send_private_message(
        self,
        *,
        openid: str,
        content: str | None = None,
        markdown: Optional["Markdown"] = None,
        keyboard: Optional["Keyboard"] = None,
        embed: Optional["Embed"] = None,
        ark: Optional["Ark"] = None,
        media: Optional["Media"] = None,
        message_reference: Optional["MessageReference"] = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        msg_seq: int = 0,
    ) -> "SendMessageResponse": ...
