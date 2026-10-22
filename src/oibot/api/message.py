import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from datetime import timedelta
from enum import IntEnum
from functools import wraps
from hashlib import md5, sha1
from http import HTTPMethod
from itertools import count
from textwrap import indent as text_indent
from typing import (
    TYPE_CHECKING,
    Concatenate,
    Literal,
    NotRequired,
    Self,
    TypedDict,
    overload,
)
from urllib.parse import quote

from oibot.api import CompactDict, sliding_window_rate_limit
from oibot.api.rich_media import FileType
from oibot.plugin import QuotaPool

if TYPE_CHECKING:
    from oibot.bot import OiBot


class MsgType(IntEnum):
    PLAINTEXT = 0
    MARKDOWN = 2
    INPUT_NOTIFY = 6
    MEDIA = 7


class StreamInputState(IntEnum):
    GENERATING = 1
    FINISHED = 10


class Markdown(dict):
    def __init__(
        self,
        *elements: str | Markdown,
        separator: str = "\n",
        indent: bool = False,
        force_verify_image_resource: bool | None = None,
    ) -> None:
        super().__init__(content=separator.join(map(str, elements)))

        if force_verify_image_resource is not None:
            self["force_verify_image_resource"] = force_verify_image_resource

        self.separator = separator
        self.indent = indent

    def __str__(self) -> str:
        return self["content"]

    @classmethod
    def autolink(cls, destination: str) -> Self:
        return cls(f"<{destination}>")

    @classmethod
    def block_quote(cls, content: str | Markdown) -> Self:
        return cls(
            text_indent(
                text_indent(str(content), ">", lambda line: line.startswith(">")),
                "> ",
                lambda line: not line.startswith(">"),
            )
        )

    @classmethod
    def bullet_list(cls, *items: str | Markdown) -> Self:
        return cls(
            *(
                text_indent(str(item), " " * 4)
                if isinstance(item, Markdown) and item.indent
                else f"- {text_indent(str(item), ' ' * 4).removeprefix(' ' * 4)}"
                for item in items
            ),
            indent=True,
        )

    @classmethod
    def cmd_enter(cls, text: str) -> Self:
        return cls(f'<qqbot-cmd-enter text="{quote(text)}" />')

    @classmethod
    def cmd_input(cls, *, text: str, show: str, reference: bool = False) -> Self:
        return cls(
            f'<qqbot-cmd-input text="{quote(text)}" show="{quote(show)}" reference="{str(reference).lower()}" />'
        )

    @classmethod
    def code_span(cls, code: str) -> Self:
        return cls(f"`{code}`")

    @classmethod
    def emphasis(cls, text: str) -> Self:
        return cls(f"*{text}*")

    @classmethod
    def fenced_code_block(cls, code: str, info_string: str = "") -> Self:
        return cls(f"```{info_string}\n{code}\n```")

    @classmethod
    def h1(cls, text: str) -> Self:
        return cls(f"# {text}")

    @classmethod
    def h2(cls, text: str) -> Self:
        return cls(f"## {text}")

    @classmethod
    def h3(cls, text: str) -> Self:
        return cls(f"### {text}")

    @classmethod
    def h4(cls, text: str) -> Self:
        return cls(f"#### {text}")

    @classmethod
    def h5(cls, text: str) -> Self:
        return cls(f"##### {text}")

    @classmethod
    def h6(cls, text: str) -> Self:
        return cls(f"###### {text}")

    @classmethod
    def image(cls, *, text: str, url: str, width: int, height: int) -> Self:
        return cls(f"![{text} #{width}px #{height}px]({url})")

    @classmethod
    def inline_latex(cls, formula: str) -> Self:
        return cls(f"${formula}$")

    @classmethod
    def link(cls, text: str, destination: str) -> Self:
        return cls(f"[{text}]({destination})")

    @classmethod
    def ordered_list(cls, *items: str | Markdown) -> Self:
        index = count(1)

        return cls(
            *(
                text_indent(str(item), " " * 4)
                if isinstance(item, Markdown) and item.indent
                else f"{next(index)}. {
                    text_indent(str(item), ' ' * 4).removeprefix(' ' * 4)
                }"
                for item in items
            ),
            indent=True,
        )

    @classmethod
    def strikethrough(cls, text: str) -> Self:
        return cls(f"~~{text}~~")

    @classmethod
    def strong_emphasis(cls, text: str) -> Self:
        return cls(f"**{text}**")

    @classmethod
    def table(
        cls,
        *,
        header: Sequence[str | Markdown],
        rows: Sequence[Sequence[str | Markdown]],
        alignments: Sequence[Literal["left", "center", "right"]] | None = None,
    ) -> Self:
        markers = {"left": ":---", "center": ":---:", "right": "---:"}

        return cls(
            f"| {' | '.join(map(str, header))} |",
            f"| {
                ' | '.join(
                    markers[item]
                    for item in (
                        alignments if alignments else ('center',) * len(header)
                    )
                )
            } |",
            *(f"| {' | '.join(map(str, row))} |" for row in rows),
        )

    @classmethod
    def task_list(cls, *items: tuple[bool, str | Markdown]) -> Self:
        return cls.bullet_list(
            *(cls(f"[{'x' if checked else ' '}] {item}") for checked, item in items)
        )

    @classmethod
    def thematic_break(cls) -> Self:
        return cls("***")


class ButtonRenderDataStyle(IntEnum):
    GRAY = 0
    BLUE = 1
    WHITE = 3
    BLUE_BACKGROUND = 4


class ButtonRenderData(CompactDict):
    def __init__(
        self,
        *,
        label: str | None = None,
        visited_label: str | None = None,
        style: ButtonRenderDataStyle | None = None,
    ) -> None:
        super().__init__(label=label, visited_label=visited_label, style=style)


class ButtonActionPermissionType(IntEnum):
    SPECIFY_USER = 0
    ADMIN = 1
    ALL = 2
    SPECIFY_ROLE = 3


class ButtonActionPermission(CompactDict):
    @classmethod
    def all(cls) -> Self:
        return cls(type=ButtonActionPermissionType.ALL)

    @classmethod
    def admin(cls) -> Self:
        return cls(type=ButtonActionPermissionType.ADMIN)

    @classmethod
    def specify_user_ids(cls, *specify_user_ids: str) -> Self:
        return cls(
            type=ButtonActionPermissionType.SPECIFY_USER,
            specify_user_ids=specify_user_ids,
        )

    @classmethod
    def specify_role_ids(cls, *specify_role_ids: str) -> Self:
        return cls(
            type=ButtonActionPermissionType.SPECIFY_ROLE,
            specify_role_ids=specify_role_ids,
        )


class ButtonActionType(IntEnum):
    JUMP = 0
    CALLBACK = 1
    INSTRUCTION = 2


class ButtonAction(CompactDict):
    def __init__(
        self,
        *,
        type: ButtonActionType | None = None,
        permission: ButtonActionPermission | None = None,
        data: str | None = None,
        unsupport_tips: str | None = None,
        reply: bool | None = None,
        enter: bool | None = None,
        anchor: int | None = None,
    ) -> None:
        super().__init__(
            type=type,
            permission=permission,
            data=data,
            unsupport_tips=unsupport_tips,
            reply=reply,
            enter=enter,
            anchor=anchor,
        )


class Button(CompactDict):
    @classmethod
    def jump(
        cls,
        *,
        data: str | None = None,
        label: str | None = None,
        visited_label: str | None = None,
        unsupport_tips: str | None = None,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
    ) -> Self:
        return cls(
            id=id,
            render_data=ButtonRenderData(
                label=label, visited_label=visited_label, style=style
            ),
            action=ButtonAction(
                type=ButtonActionType.JUMP,
                permission=permission,
                data=data,
                unsupport_tips=unsupport_tips,
            ),
        )

    @classmethod
    def callback(
        cls,
        *,
        data: dict | str,
        label: str | None = None,
        visited_label: str | None = None,
        unsupport_tips: str | None = None,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
    ) -> Self:
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

        return cls(
            id=id,
            render_data=ButtonRenderData(
                label=label, visited_label=visited_label, style=style
            ),
            action=ButtonAction(
                type=ButtonActionType.CALLBACK,
                permission=permission or ButtonActionPermission.all(),
                data=data,
                unsupport_tips=unsupport_tips,
            ),
        )

    @classmethod
    def instruction(
        cls,
        *,
        data: str,
        label: str | None = None,
        visited_label: str | None = None,
        unsupport_tips: str | None = None,
        id: str | None = None,
        style: ButtonRenderDataStyle = ButtonRenderDataStyle.BLUE,
        permission: ButtonActionPermission | None = None,
        reply: bool | None = None,
        enter: bool | None = None,
        anchor: Literal[1] | None = None,
    ) -> Self:
        return cls(
            id=id,
            render_data=ButtonRenderData(
                label=label, visited_label=visited_label, style=style
            ),
            action=ButtonAction(
                type=ButtonActionType.INSTRUCTION,
                permission=permission or ButtonActionPermission.all(),
                data=data,
                reply=reply,
                enter=enter,
                anchor=anchor,
                unsupport_tips=unsupport_tips,
            ),
        )


class Buttons(dict):
    def __init__(self, *buttons: Button) -> None:
        super().__init__(buttons=buttons)


class Rows(dict):
    def __init__(self, *rows: Buttons) -> None:
        super().__init__(rows=rows)


class Keyboard(CompactDict):
    def __init__(self, *rows: Buttons) -> None:
        super().__init__(content=Rows(*rows))


class MessageReference(dict):
    def __init__(self, *, message_id: str) -> None:
        super().__init__(message_id=message_id)


class InputNotify(dict):
    def __init__(self, *, input_second: int) -> None:
        super().__init__(input_type=1, input_second=input_second)


class Media(CompactDict):
    def __init__(
        self,
        *,
        file_type: FileType | None = None,
        data: bytes | None = None,
        url: str | None = None,
        file_name: str | None = None,
    ) -> None:
        super().__init__(file_type=file_type, data=data, url=url, file_name=file_name)

    @overload
    @classmethod
    def image(cls, *, data: bytes, file_name: str, url: str | None = None) -> Self: ...

    @overload
    @classmethod
    def image(
        cls, *, url: str, data: None = None, file_name: str | None = None
    ) -> Self: ...

    @classmethod
    def image(
        cls,
        *,
        data: bytes | None = None,
        url: str | None = None,
        file_name: str | None = None,
    ) -> Self:
        return cls(file_type=FileType.IMAGE, data=data, url=url, file_name=file_name)

    @classmethod
    def video(
        cls,
        *,
        data: bytes | None = None,
        url: str | None = None,
        file_name: str | None = None,
    ) -> Self:
        return cls(file_type=FileType.VIDEO, data=data, url=url, file_name=file_name)

    @classmethod
    def voice(
        cls,
        *,
        data: bytes | None = None,
        url: str | None = None,
        file_name: str | None = None,
    ) -> Self:
        return cls(file_type=FileType.VOICE, data=data, url=url, file_name=file_name)

    @classmethod
    def file(
        cls,
        *,
        data: bytes | None = None,
        url: str | None = None,
        file_name: str | None = None,
    ) -> Self:
        return cls(file_type=FileType.FILE, data=data, url=url, file_name=file_name)


class MediaInfo(TypedDict):
    file_info: str


class Message[T: Keyboard | None = None](CompactDict):
    def __init__(
        self,
        *,
        msg_type: MsgType,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        input_notify: InputNotify | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> None:
        super().__init__(
            msg_type=msg_type,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            media=media,
            message_reference=message_reference,
            input_notify=input_notify,
            msg_id=msg_id,
            event_id=event_id,
            msg_seq=msg_seq,
            is_wakeup=is_wakeup,
        )

    @classmethod
    def content(
        cls: type[Message],
        content: str,
        *,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message:
        return cls(
            msg_type=MsgType.PLAINTEXT,
            content=content,
            message_reference=message_reference,
            msg_id=msg_id,
            event_id=event_id,
            msg_seq=msg_seq,
            is_wakeup=is_wakeup,
        )

    @classmethod
    def media(
        cls: type[Message],
        media: Media,
        *,
        content: str | None = None,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message:
        return cls(
            msg_type=MsgType.MEDIA,
            media=media,
            content=content,
            message_reference=message_reference,
            msg_id=msg_id,
            event_id=event_id,
            msg_seq=msg_seq,
            is_wakeup=is_wakeup,
        )

    @overload
    @classmethod
    def markdown(
        cls,
        markdown: Markdown | None = None,
        *,
        keyboard: Keyboard,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message[Keyboard]: ...

    @overload
    @classmethod
    def markdown(
        cls,
        markdown: Markdown | None = None,
        *,
        keyboard: None = None,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message: ...

    @classmethod
    def markdown(
        cls: type[Message],
        markdown: Markdown | None = None,
        *,
        keyboard: Keyboard | None = None,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message[Keyboard] | Message:
        return cls(
            msg_type=MsgType.MARKDOWN,
            markdown=markdown,
            keyboard=keyboard,
            message_reference=message_reference,
            msg_id=msg_id,
            event_id=event_id,
            msg_seq=msg_seq,
            is_wakeup=is_wakeup,
        )

    @classmethod
    def input_notify(
        cls: type[Message],
        input_second: int,
        *,
        message_reference: MessageReference | None = None,
        msg_id: str | None = None,
        event_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> Message:
        return cls(
            msg_type=MsgType.INPUT_NOTIFY,
            input_notify=InputNotify(input_second=input_second),
            message_reference=message_reference,
            msg_id=msg_id,
            event_id=event_id,
            msg_seq=msg_seq,
            is_wakeup=is_wakeup,
        )


def at(id: str | Literal["all"]) -> str:
    return "<qqbot-at-everyone />" if id == "all" else f'<qqbot-at-user id="{id}" />'


def channel(channel_id: str) -> str:
    return f"<#{channel_id}>"


def media(token: str) -> str:
    return f"qqbot-media://image/v1/{token}"


class ExtInfo(TypedDict):
    ref_idx: str


class MessageResponse(TypedDict):
    id: str
    timestamp: str
    ext_info: ExtInfo


class StreamMessageResponse(MessageResponse):
    remain_msg_len: NotRequired[int]


class SendMessageMixin:
    @staticmethod
    def proactive_message_rate_limit[T, **P, R](
        func: Callable[Concatenate[T, P], Awaitable[R]],
    ) -> Callable[Concatenate[T, P], Awaitable[R]]:
        limited_func = sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))(
            func
        )

        @wraps(func)
        async def wrapper(self: T, *args: P.args, **kwargs: P.kwargs) -> R:
            if kwargs.get("msg_id") or kwargs.get("event_id"):
                return await func(self, *args, **kwargs)

            return await limited_func(self, *args, **kwargs)

        return wrapper

    @staticmethod
    def user_openid_rate_limit[T, **P, R](
        func: Callable[Concatenate[T, P], Awaitable[R]],
    ) -> Callable[Concatenate[T, P], Awaitable[R]]:
        return sliding_window_rate_limit(
            key="openid", limit=20, window=timedelta(minutes=1)
        )(func)

    @staticmethod
    def group_openid_rate_limit[T, **P, R](
        func: Callable[Concatenate[T, P], Awaitable[R]],
    ) -> Callable[Concatenate[T, P], Awaitable[R]]:
        return sliding_window_rate_limit(
            key="group_openid", limit=20, window=timedelta(minutes=1)
        )(func)

    @user_openid_rate_limit
    @QuotaPool.acquire
    @proactive_message_rate_limit
    @sliding_window_rate_limit(limit=100, window=timedelta(seconds=1))
    async def send_raw_user_message(
        self: OiBot,
        *,
        openid: str,
        msg_type: MsgType,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        media: MediaInfo | None = None,
        message_reference: MessageReference | None = None,
        input_notify: InputNotify | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        is_wakeup: bool | None = None,
        msg_seq: int | None = None,
    ) -> MessageResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/messages",
            json=CompactDict(
                content=content,
                msg_type=msg_type,
                markdown=markdown,
                keyboard=keyboard,
                media=media,
                message_reference=message_reference,
                input_notify=input_notify,
                event_id=event_id,
                msg_id=msg_id,
                is_wakeup=is_wakeup,
                msg_seq=msg_seq,
            ),
        )

    async def send_user_message(
        self: OiBot, *, openid: str, message: Message | Message[Keyboard]
    ) -> MessageResponse:
        message = deepcopy(message)

        if message["msg_type"] == MsgType.MEDIA:
            media = message["media"]

            if data := media.pop("data", None):
                prepare = await self.prepare_user_upload(
                    openid=openid,
                    file_type=media["file_type"],
                    file_size=str(len(data)),
                    file_name=media["file_name"],
                    md5=md5(data).hexdigest(),
                    sha1=sha1(data).hexdigest(),
                    md5_10m=md5(data[:10_002_432]).hexdigest(),
                )

                upload_config = prepare["upload_config"]

                for idx in range(
                    0, len(prepare["parts"]), upload_config["concurrency"]
                ):
                    await asyncio.gather(
                        *(
                            self.upload_user_part(
                                openid=openid,
                                upload_id=prepare["upload_id"],
                                data=data,
                                block_size=prepare["block_size"],
                                part=part,
                                retry_timeout=upload_config["retry_timeout"],
                                retry_delay=upload_config["retry_delay"],
                            )
                            for part in prepare["parts"][
                                idx : idx + upload_config["concurrency"]
                            ]
                        )
                    )

                message["media"] = MediaInfo(
                    file_info=(
                        await self.upload_user_file(
                            openid=openid, upload_id=prepare["upload_id"], **media
                        )
                    )["file_info"]
                )

            else:
                message["media"] = MediaInfo(
                    file_info=(await self.upload_user_file(openid=openid, **media))[
                        "file_info"
                    ]
                )

        return await self.send_raw_user_message(openid=openid, **message)

    @proactive_message_rate_limit
    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def stream_user_message(
        self: OiBot,
        *,
        openid: str,
        input_state: StreamInputState,
        index: int,
        content_type: Literal["text", "markdown"],
        content_raw: str,
        input_mode: Literal["append", "replace"] = "append",
        event_id: str | None = None,
        msg_id: str | None = None,
        stream_msg_id: str | None = None,
        msg_seq: int | None = None,
        is_wakeup: bool | None = None,
    ) -> StreamMessageResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/stream_messages",
            json=CompactDict(
                input_mode=input_mode,
                input_state=input_state,
                index=index,
                content_type=content_type,
                content_raw=content_raw,
                event_id=event_id,
                msg_id=msg_id,
                stream_msg_id=stream_msg_id,
                msg_seq=msg_seq,
                is_wakeup=is_wakeup,
            ),
        )

    @group_openid_rate_limit
    @QuotaPool.acquire
    @proactive_message_rate_limit
    @sliding_window_rate_limit(limit=100, window=timedelta(seconds=1))
    async def send_raw_group_message(
        self: OiBot,
        *,
        group_openid: str,
        msg_type: MsgType,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        media: MediaInfo | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        is_wakeup: bool | None = None,
        msg_seq: int | None = None,
    ) -> MessageResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/messages",
            json=CompactDict(
                content=content,
                msg_type=msg_type,
                markdown=markdown,
                keyboard=keyboard,
                media=media,
                message_reference=message_reference,
                event_id=event_id,
                msg_id=msg_id,
                is_wakeup=is_wakeup,
                msg_seq=msg_seq,
            ),
        )

    async def send_group_message(
        self: OiBot, *, group_openid: str, message: Message | Message[Keyboard]
    ) -> MessageResponse:
        message = deepcopy(message)

        if message["msg_type"] == MsgType.MEDIA:
            media = message["media"]

            if data := media.pop("data", None):
                prepare = await self.prepare_group_upload(
                    group_openid=group_openid,
                    file_type=media["file_type"],
                    file_size=str(len(data)),
                    file_name=media["file_name"],
                    md5=md5(data).hexdigest(),
                    sha1=sha1(data).hexdigest(),
                    md5_10m=md5(data[:10_002_432]).hexdigest(),
                )

                upload_config = prepare["upload_config"]

                for idx in range(
                    0, len(prepare["parts"]), upload_config["concurrency"]
                ):
                    await asyncio.gather(
                        *(
                            self.upload_group_part(
                                group_openid=group_openid,
                                upload_id=prepare["upload_id"],
                                data=data,
                                block_size=prepare["block_size"],
                                part=part,
                                retry_timeout=upload_config["retry_timeout"],
                                retry_delay=upload_config["retry_delay"],
                            )
                            for part in prepare["parts"][
                                idx : idx + upload_config["concurrency"]
                            ]
                        )
                    )

                message["media"] = MediaInfo(
                    file_info=(
                        await self.upload_group_file(
                            group_openid=group_openid,
                            upload_id=prepare["upload_id"],
                            **media,
                        )
                    )["file_info"]
                )

            else:
                message["media"] = MediaInfo(
                    file_info=(
                        await self.upload_group_file(group_openid=group_openid, **media)
                    )["file_info"]
                )

        return await self.send_raw_group_message(group_openid=group_openid, **message)
