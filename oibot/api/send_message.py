from base64 import b64encode
from enum import IntEnum
from time import time
from typing import Literal, NotRequired, TypedDict

from oibot.api.upload_file import FileType, upload_group_file, upload_private_file
from oibot.bot import OiBot


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


class Embed(TypedDict, total=False):
    title: str
    prompt: str
    thumbnail: Thumbnail
    fields: list[EmbedField]


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


class Media(TypedDict):
    file_uuid: str
    file_info: str
    ttl: int
    id: NotRequired[str]


class MessageReference(TypedDict): ...


class SendMessageResponse(TypedDict):
    id: str
    timestamp: int


async def send_private_message(
    *,
    openid: str,
    msg_type: MsgType,
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
    return await OiBot.request(
        method="POST",
        url=f"/v2/users/{openid}/messages",
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


async def send_group_message(
    *,
    group_openid: str,
    msg_type: MsgType,
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
    return await OiBot.request(
        method="POST",
        url=f"/v2/groups/{group_openid}/messages",
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
    *,
    openid: str | None = None,
    group_openid: str | None = None,
    content: str | None = None,
    markdown: Markdown | None = None,
    keyboard: Keyboard | None = None,
    embed: Embed | None = None,
    ark: Ark | None = None,
    image: bytes | str | None = None,
    video: bytes | str | None = None,
    voice: bytes | str | None = None,
    message_reference: MessageReference | None = None,
    event_id: str | None = None,
    msg_id: str | None = None,
) -> SendMessageResponse:
    file = None

    if markdown:
        msg_type = MsgType.MARKDOWN
    elif ark:
        msg_type = MsgType.ARK
    elif any((image, video, voice)):
        msg_type = MsgType.MEDIA
    else:
        msg_type = MsgType.PLAINTEXT

    if openid:
        if image:
            if isinstance(image, bytes):
                file = await upload_private_file(
                    openid=openid,
                    file_type=FileType.IMAGE,
                    file_data=b64encode(image).decode("utf-8"),
                )

            elif isinstance(image, str) and image.startswith("http"):
                file = await upload_private_file(
                    openid=openid, file_type=FileType.IMAGE, url=image
                )

            else:
                raise ValueError("invalid file type")

        elif video:
            if isinstance(video, bytes):
                file = await upload_private_file(
                    openid=openid,
                    file_type=FileType.VIDEO,
                    file_data=b64encode(video).decode("utf-8"),
                )

            elif isinstance(video, str) and video.startswith("http"):
                file = await upload_private_file(
                    openid=openid, file_type=FileType.VIDEO, url=video
                )

            else:
                raise ValueError("invalid file type")

        elif voice:
            if isinstance(voice, bytes):
                file = await upload_private_file(
                    openid=openid,
                    file_type=FileType.VOICE,
                    file_data=b64encode(voice).decode("utf-8"),
                )

            elif isinstance(voice, str) and voice.startswith("http"):
                file = await upload_private_file(
                    openid=openid, file_type=FileType.VOICE, url=voice
                )

            else:
                raise ValueError("invalid file type")

        return await send_private_message(
            openid=openid,
            msg_type=msg_type,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            embed=embed,
            ark=ark,
            media=file,
            message_reference=message_reference,
            event_id=event_id,
            msg_id=msg_id,
            msg_seq=int(time()),
        )

    elif group_openid:
        if image:
            if isinstance(image, bytes):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.IMAGE,
                    file_data=b64encode(image).decode("utf-8"),
                )

            elif isinstance(image, str) and image.startswith("http"):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.IMAGE,
                    url=image,
                )

            else:
                raise ValueError("invalid file type")

        elif video:
            if isinstance(video, bytes):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.VIDEO,
                    file_data=b64encode(video).decode("utf-8"),
                )

            elif isinstance(video, str) and video.startswith("http"):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.VIDEO,
                    url=video,
                )

            else:
                raise ValueError("invalid file type")

        elif voice:
            if isinstance(voice, bytes):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.VOICE,
                    file_data=b64encode(voice).decode("utf-8"),
                )

            elif isinstance(voice, str) and voice.startswith("http"):
                file = await upload_group_file(
                    group_openid=group_openid,
                    file_type=FileType.VOICE,
                    url=voice,
                )

            else:
                raise ValueError("invalid file type")

        return await send_group_message(
            group_openid=group_openid,
            msg_type=msg_type,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            embed=embed,
            ark=ark,
            media=file,
            message_reference=message_reference,
            event_id=event_id,
            msg_id=msg_id,
            msg_seq=int(time()),
        )

    else:
        raise ValueError("parameter `openid` or `group_openid` must be specified")
