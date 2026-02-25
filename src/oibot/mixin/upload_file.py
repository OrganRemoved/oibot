from base64 import b64encode
from enum import IntEnum
from typing import NotRequired, Self, TypedDict

from oibot.mixin import MixinProtocol


class FileType(IntEnum):
    IMAGE = 1
    VIDEO = 2
    VOICE = 3
    FILE = 4


class Media(dict):
    def __init__(
        self,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> None:
        super().__init__(
            file_type=file_type,
            url=url,
            srv_send_msg=srv_send_msg,
            file_data=file_data
            and (
                b64encode(file_data).decode("utf-8")
                if isinstance(file_data, bytes)
                else file_data
            ),
        )

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


class UploadFileResponse(TypedDict):
    file_uuid: str
    file_info: str
    ttl: int
    id: NotRequired[str]


class UploadFileMixin:
    async def upload_private_file(
        self: MixinProtocol,
        *,
        openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> UploadFileResponse:
        return await self(
            "POST",
            f"/v2/users/{openid}/files",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            json={
                "file_type": file_type,
                "url": url,
                "srv_send_msg": srv_send_msg,
                "file_data": file_data,
            },
        )

    async def upload_group_file(
        self: MixinProtocol,
        *,
        group_openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: bytes | str | None = None,
    ) -> UploadFileResponse:
        return await self(
            "POST",
            f"/v2/groups/{group_openid}/files",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            json={
                "file_type": file_type,
                "url": url,
                "srv_send_msg": srv_send_msg,
                "file_data": file_data,
            },
        )
