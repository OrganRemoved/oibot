from enum import IntEnum
from typing import NotRequired, TypedDict

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


async def upload_private_file(
    *,
    openid: str,
    file_type: FileType,
    url: str | None = None,
    srv_send_msg: bool = False,
    file_data: bytes | str | None = None,
) -> UploadFileResponse:
    return await OiBot.request(
        method="POST",
        url=f"/v2/users/{openid}/files",
        json={
            "file_type": file_type,
            "url": url,
            "srv_send_msg": srv_send_msg,
            "file_data": file_data,
        },
    )


async def upload_group_file(
    *,
    group_openid: str,
    file_type: FileType,
    url: str | None = None,
    srv_send_msg: bool = False,
    file_data: bytes | str | None = None,
) -> UploadFileResponse:
    return await OiBot.request(
        method="POST",
        url=f"/v2/groups/{group_openid}/files",
        json={
            "file_type": file_type,
            "url": url,
            "srv_send_msg": srv_send_msg,
            "file_data": file_data,
        },
    )
