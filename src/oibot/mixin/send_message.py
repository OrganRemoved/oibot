from enum import IntEnum
from typing import Literal, NotRequired, TypedDict

from oibot.mixin import MixinProtocol
from oibot.mixin.upload_file import Media


class MsgType(IntEnum):
    PLAINTEXT = 0
    MIX = 1
    MARKDOWN = 2
    ARK = 3
    EMBED = 4
    MEDIA = 7


class MarkdownParam(TypedDict):
    key: str
    value: list[str]


class Markdown(TypedDict):
    content: NotRequired[str]
    custom_template_id: NotRequired[str]
    params: NotRequired[MarkdownParam]


class ButtonRenderData(TypedDict):
    label: str
    visited_label: str
    style: Literal[0, 1]


class ButtonActionPermission(TypedDict):
    type: Literal[0, 1, 2, 3]
    specify_user_ids: NotRequired[list[str]]
    specify_role_ids: NotRequired[list[str]]


class ButtonAction(TypedDict):
    type: Literal[0, 1, 2]
    data: str
    reply: NotRequired[bool]
    enter: NotRequired[bool]
    anchor: NotRequired[Literal[1]]
    click_limit: NotRequired[int]
    at_bot_show_channel_list: NotRequired[bool]
    unsupport_tips: str


class Button(TypedDict):
    id: NotRequired[str]
    render_data: ButtonRenderData
    action: ButtonAction


class Buttons(TypedDict):
    buttons: list[Button]


class Rows(TypedDict):
    rows: list


class Content(TypedDict):
    content: Rows


class Keyboard(TypedDict):
    id: NotRequired[str]
    content: NotRequired[str]


class Thumbnail(TypedDict):
    url: str


class EmbedField(TypedDict):
    name: str


class Embed(TypedDict):
    title: NotRequired[str]
    prompt: NotRequired[str]
    thumbnail: NotRequired[Thumbnail]
    fields: NotRequired[list[EmbedField]]


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
    kv: list


class MessageReference(TypedDict): ...


class SendMessageResponse(TypedDict):
    id: str
    timestamp: int


class SendMessageMixin:
    async def send_private_message(
        self: MixinProtocol,
        *,
        openid: str,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        msg_seq: int = 0,
    ) -> SendMessageResponse:
        if markdown:
            msg_type = MsgType.MARKDOWN
        elif ark:
            msg_type = MsgType.ARK
        elif media:
            msg_type = MsgType.MEDIA
        else:
            msg_type = MsgType.PLAINTEXT

        file = await self.upload_private_file(openid=openid, **media) if media else None

        return await self(
            "POST",
            f"/v2/users/{openid}/messages",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            json={
                "content": content,
                "msg_type": msg_type,
                "markdown": markdown,
                "keyboard": keyboard,
                "embed": embed,
                "ark": ark,
                "media": file,
                "message_reference": message_reference,
                "event_id": event_id,
                "msg_id": msg_id,
                "msg_seq": msg_seq,
            },
        )

    async def send_group_message(
        self: MixinProtocol,
        *,
        group_openid: str,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        msg_seq: int = 0,
    ) -> SendMessageResponse:
        if markdown:
            msg_type = MsgType.MARKDOWN
        elif ark:
            msg_type = MsgType.ARK
        elif media:
            msg_type = MsgType.MEDIA
        else:
            msg_type = MsgType.PLAINTEXT

        file = (
            await self.upload_group_file(group_openid=group_openid, **media)
            if media
            else None
        )

        return await self(
            "POST",
            f"/v2/groups/{group_openid}/messages",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            json={
                "content": content,
                "msg_type": msg_type,
                "markdown": markdown,
                "keyboard": keyboard,
                "embed": embed,
                "ark": ark,
                "media": file,
                "message_reference": message_reference,
                "event_id": event_id,
                "msg_id": msg_id,
                "msg_seq": msg_seq,
            },
        )
