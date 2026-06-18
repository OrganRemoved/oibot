import json
from base64 import b64encode
from datetime import datetime
from enum import IntEnum
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal, NotRequired, Self, TypedDict
from urllib.parse import quote

from oibot.api.upload_file import FileType

if TYPE_CHECKING:
    from oibot.bot import OiBot


class MsgType(IntEnum):
    PLAINTEXT = 0
    MIX = 1
    MARKDOWN = 2
    ARK = 3
    EMBED = 4
    MEDIA = 7


# Markdown
class MarkdownParam(TypedDict):
    key: str
    values: list[str]


class Markdown(dict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def content(cls, content: str) -> Self:
        return cls(content=content)

    @classmethod
    def content_template(
        cls, custom_template_id: str, params: list[MarkdownParam] | None = None
    ) -> Self:
        return cls(custom_template_id=custom_template_id, params=params)

    @staticmethod
    def cmd_enter(text: str) -> str:
        return f'<qqbot-cmd-enter text="{quote(text)}" />'

    @staticmethod
    def cmd_input(text: str, show: str, reference: bool = False) -> str:
        return f'<qqbot-cmd-input text="{quote(text)}" show="{quote(show)}" reference="{str(reference).lower()}" />'


# Keyboard
class ButtonRenderDataStyle(IntEnum):
    GRAY = 0
    BLUE = 1


class ButtonRenderData(TypedDict):
    label: str
    visited_label: str
    style: ButtonRenderDataStyle


class ButtonActionPermissionType(IntEnum):
    SPECIFY_USER = 0
    ADMIN = 1
    ALL = 2
    SPECIFY_ROLE = 3


class ButtonActionPermission(dict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def all(cls) -> Self:
        return cls(type=ButtonActionPermissionType.ALL)

    @classmethod
    def admin(cls) -> Self:
        return cls(type=ButtonActionPermissionType.ADMIN)

    @classmethod
    def specify_user_ids(cls, specify_user_ids: list[str]) -> Self:
        return cls(
            type=ButtonActionPermissionType.SPECIFY_USER,
            specify_user_ids=specify_user_ids,
        )

    @classmethod
    def specify_role_ids(cls, specify_role_ids: list[str]) -> Self:
        return cls(
            type=ButtonActionPermissionType.SPECIFY_ROLE,
            specify_role_ids=specify_role_ids,
        )


class ButtonActionType(IntEnum):
    JUMP = 0
    CALLBACK = 1
    INSTRUCTION = 2


class ButtonAction(TypedDict):
    type: ButtonActionType
    permission: ButtonActionPermission
    data: str
    reply: NotRequired[bool]
    enter: NotRequired[bool]
    anchor: NotRequired[Literal[1]]
    unsupport_tips: str


class Button(dict):
    def __init__(self, **kwargs) -> None:
        kwargs["render_data"] = {
            "label": kwargs.pop("label"),
            "visited_label": kwargs.pop("visited_label"),
            "style": kwargs.pop("style"),
        }

        kwargs["action"] = action = {
            "type": kwargs.pop("type"),
            "permission": kwargs.pop("permission"),
            "data": kwargs.pop("data"),
            "unsupport_tips": kwargs.pop("unsupport_tips"),
        }

        if (reply := kwargs.pop("reply", None)) is not None:
            action["reply"] = reply

        if (enter := kwargs.pop("enter", None)) is not None:
            action["enter"] = enter

        if (anchor := kwargs.pop("anchor", None)) is not None:
            action["anchor"] = anchor

        super().__init__(**{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def jump(
        cls,
        label: str,
        visited_label: str,
        data: dict | str,
        unsupport_tips: str,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
    ) -> Self:
        return cls(
            id=id,
            label=label,
            visited_label=visited_label,
            style=style,
            type=ButtonActionType.JUMP,
            permission=permission or ButtonActionPermission.all(),
            data=(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                if isinstance(data, dict)
                else data
            ),
            unsupport_tips=unsupport_tips,
        )

    @classmethod
    def callback(
        cls,
        label: str,
        visited_label: str,
        data: dict | str,
        unsupport_tips: str,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
    ) -> Self:
        return cls(
            id=id,
            label=label,
            visited_label=visited_label,
            style=style,
            type=ButtonActionType.CALLBACK,
            permission=permission or ButtonActionPermission.all(),
            data=(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                if isinstance(data, dict)
                else data
            ),
            unsupport_tips=unsupport_tips,
        )

    @classmethod
    def instruction(
        cls,
        label: str,
        visited_label: str,
        data: dict | str,
        unsupport_tips: str,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
        reply: bool | None = None,
        enter: bool | None = None,
        anchor: Literal[1] | None = None,
    ) -> Self:
        return cls(
            id=id,
            label=label,
            visited_label=visited_label,
            style=style,
            type=ButtonActionType.INSTRUCTION,
            permission=permission or ButtonActionPermission.all(),
            data=(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                if isinstance(data, dict)
                else data
            ),
            reply=reply,
            enter=enter,
            anchor=anchor,
            unsupport_tips=unsupport_tips,
        )


class Buttons(TypedDict):
    buttons: list[Button]


class Rows(TypedDict):
    rows: list[Buttons]


class Keyboard(dict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def id(cls, id: str) -> Self:
        return cls(id=id)

    @classmethod
    def content(cls, *buttons: Buttons) -> Self:
        return cls(content=Rows(rows=list(buttons)))


# Ark
class ArkObjKV(TypedDict):
    key: str
    value: str


class ArkObj(TypedDict):
    obj_kv: list[ArkObjKV]


class ArkKV(TypedDict):
    key: str
    value: NotRequired[str]
    obj: NotRequired[list[ArkObj]]


class Ark(TypedDict):
    template_id: int
    kv: list[ArkKV]


# Embed
class Thumbnail(TypedDict):
    url: str


class Field(TypedDict):
    name: str


class Embed(TypedDict):
    title: str
    prompt: str
    thumbnail: Thumbnail
    fields: list[Field]


class MessageReference(TypedDict):
    message_id: str
    ignore_get_message_error: bool


class Media(dict):
    def __init__(self, **kwargs) -> None:
        if isinstance(file_data := kwargs.get("file_data"), bytes):
            kwargs["file_data"] = b64encode(file_data).decode("utf-8")

        super().__init__({k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def image(
        cls,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> Self:
        return cls(
            file_type=FileType.IMAGE,
            url=url,
            srv_send_msg=srv_send_msg,
            file_data=file_data,
        )

    @classmethod
    def video(
        cls,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> Self:
        return cls(
            file_type=FileType.VIDEO,
            url=url,
            srv_send_msg=srv_send_msg,
            file_data=file_data,
        )

    @classmethod
    def voice(
        cls,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> Self:
        return cls(
            file_type=FileType.VOICE,
            url=url,
            srv_send_msg=srv_send_msg,
            file_data=file_data,
        )

    @classmethod
    def file(
        cls,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> Self:
        return cls(
            file_type=FileType.FILE,
            url=url,
            srv_send_msg=srv_send_msg,
            file_data=file_data,
        )


class Message(dict):
    def __init__(self, **kwargs) -> None:
        super().__init__(**{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def content(cls, content: str) -> Self:
        return cls(msg_type=MsgType.PLAINTEXT, content=content)

    @classmethod
    def media(cls, media: Media, content: str | None = None) -> Self:
        return cls(msg_type=MsgType.MEDIA, media=media, content=content)

    @classmethod
    def markdown(cls, markdown: Markdown, keyboard: Keyboard | None = None) -> Self:
        return cls(msg_type=MsgType.MARKDOWN, markdown=markdown, keyboard=keyboard)

    @classmethod
    def ark(cls, ark: Ark) -> Self:
        return cls(msg_type=MsgType.ARK, ark=ark)


def at(id: str | Literal["all"]) -> str:
    return "<qqbot-at-everyone />" if id == "all" else f'<qqbot-at-user id="{id}" />'


def channel(channel_id: str) -> str:
    return f"<#{channel_id}>"


class ExtInfo(TypedDict):
    ref_idx: str


class SendMessageResponse(TypedDict):
    id: str
    timestamp: int
    ext_info: ExtInfo


class SendMessageMixin:
    async def send_user_message(
        self: "OiBot",
        *,
        openid: str,
        msg_type: MsgType,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: dict | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        is_wakeup: bool | None = None,
        msg_seq: int | None = None,
    ) -> SendMessageResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/messages",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            json={
                "content": content,
                "msg_type": msg_type,
                "markdown": markdown,
                "keyboard": keyboard,
                "embed": embed,
                "ark": ark,
                "media": media,
                "message_reference": message_reference,
                "event_id": event_id,
                "msg_id": msg_id,
                "is_wakeup": is_wakeup,
                "msg_seq": msg_seq,
            },
        )

    async def send_group_message(
        self: "OiBot",
        *,
        group_openid: str,
        msg_type: MsgType,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: dict | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        msg_seq: int | None = None,
    ) -> SendMessageResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/messages",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            json={
                "content": content,
                "msg_type": msg_type,
                "markdown": markdown,
                "keyboard": keyboard,
                "embed": embed,
                "ark": ark,
                "media": media,
                "message_reference": message_reference,
                "event_id": event_id,
                "msg_id": msg_id,
                "msg_seq": msg_seq,
            },
        )

    async def send_message(
        self: "OiBot",
        *,
        message: Message,
        openid: str | None = None,
        group_openid: str | None = None,
        **kwargs,
    ) -> SendMessageResponse:
        kwargs.setdefault("msg_seq", int(datetime.now().timestamp()))

        msg = message.copy()

        if openid:
            if msg["msg_type"] == MsgType.MEDIA:
                kwargs["media"] = {
                    "file_info": (
                        await self.upload_user_file(openid=openid, **msg.pop("media"))
                    )["file_info"]
                }

            return await self.send_user_message(openid=openid, **msg, **kwargs)

        elif group_openid:
            if msg["msg_type"] == MsgType.MEDIA:
                kwargs["media"] = {
                    "file_info": (
                        await self.upload_group_file(
                            group_openid=group_openid, **msg.pop("media")
                        )
                    )["file_info"]
                }

            return await self.send_group_message(
                group_openid=group_openid, **msg, **kwargs
            )

        else:
            raise ValueError("parameter `openid` or `group_openid` must be specified")
