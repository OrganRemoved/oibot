from enum import IntEnum
from http import HTTPMethod
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from oibot.bot import OiBot


class FileType(IntEnum):
    IMAGE = 1
    VIDEO = 2
    VOICE = 3
    FILE = 4


class UploadFileResponse(TypedDict):
    file_uuid: str
    file_info: str
    ttl: int
    id: NotRequired[str]


class UploadFileMixin:
    async def upload_user_file(
        self: "OiBot",
        *,
        openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> UploadFileResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/files",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            json={
                "file_type": file_type,
                "url": url,
                "srv_send_msg": srv_send_msg,
                "file_data": file_data,
            },
        )

    async def upload_group_file(
        self: "OiBot",
        *,
        group_openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> UploadFileResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/files",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            json={
                "file_type": file_type,
                "url": url,
                "srv_send_msg": srv_send_msg,
                "file_data": file_data,
            },
        )
