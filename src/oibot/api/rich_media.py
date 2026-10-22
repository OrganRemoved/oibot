import asyncio
from datetime import timedelta
from enum import IntEnum
from hashlib import md5
from http import HTTPMethod
from typing import TYPE_CHECKING, NotRequired, TypedDict

from oibot.api import CompactDict, sliding_window_rate_limit

if TYPE_CHECKING:
    from oibot.bot import OiBot


class FileType(IntEnum):
    IMAGE = 1
    VIDEO = 2
    VOICE = 3
    FILE = 4


class RichMediaUploadResponse(TypedDict):
    file_uuid: str
    file_info: str
    ttl: int
    id: NotRequired[str]
    raw_url: NotRequired[str]


class RichMediaUploadPart(TypedDict):
    index: int
    presigned_url: str
    block_size: str


class RichMediaUploadConfig(TypedDict):
    concurrency: int
    retry_timeout: int
    retry_delay: int


class RichMediaUploadPrepareResponse(TypedDict):
    upload_id: str
    block_size: str
    parts: list[RichMediaUploadPart]
    upload_config: RichMediaUploadConfig


class RichMediaMixin:
    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def upload_user_file(
        self: OiBot,
        *,
        openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_name: str | None = None,
        upload_id: str | None = None,
    ) -> RichMediaUploadResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/files",
            json=CompactDict(
                file_type=file_type,
                url=url,
                srv_send_msg=srv_send_msg,
                file_name=file_name,
                upload_id=upload_id,
            ),
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(seconds=1))
    async def prepare_user_upload(
        self: OiBot,
        *,
        openid: str,
        file_name: str,
        file_type: FileType | None = None,
        file_size: str | None = None,
        md5: str | None = None,
        sha1: str | None = None,
        md5_10m: str | None = None,
    ) -> RichMediaUploadPrepareResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/upload_prepare",
            json=CompactDict(
                file_type=file_type,
                file_size=file_size,
                file_name=file_name,
                md5=md5,
                sha1=sha1,
                md5_10m=md5_10m,
            ),
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(seconds=1))
    async def finish_user_upload_part(
        self: OiBot,
        *,
        openid: str,
        upload_id: str | None = None,
        part_index: int | None = None,
        block_size: str | None = None,
        md5: str | None = None,
    ) -> None:
        await self(
            HTTPMethod.POST,
            f"/v2/users/{openid}/upload_part_finish",
            json=CompactDict(
                upload_id=upload_id,
                part_index=part_index,
                block_size=block_size,
                md5=md5,
            ),
        )

    async def upload_user_part(
        self: OiBot,
        *,
        openid: str,
        upload_id: str,
        data: bytes,
        block_size: str,
        part: RichMediaUploadPart,
        retry_timeout: int = 300,
        retry_delay: int = 1,
    ) -> None:
        offset = (part["index"] - 1) * int(block_size)
        chunk = data[offset : offset + int(part["block_size"])]

        async with asyncio.timeout(retry_timeout):
            while True:
                try:
                    async with self.client_session.put(
                        part["presigned_url"], data=chunk
                    ) as response:
                        await response.read()

                    return await self.finish_user_upload_part(
                        openid=openid,
                        upload_id=upload_id,
                        part_index=part["index"],
                        block_size=str(len(chunk)),
                        md5=md5(chunk).hexdigest(),
                    )

                except Exception:
                    await asyncio.sleep(retry_delay)

    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def upload_group_file(
        self: OiBot,
        *,
        group_openid: str,
        file_type: FileType,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_name: str | None = None,
        upload_id: str | None = None,
    ) -> RichMediaUploadResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/files",
            json=CompactDict(
                file_type=file_type,
                url=url,
                srv_send_msg=srv_send_msg,
                file_name=file_name,
                upload_id=upload_id,
            ),
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(seconds=1))
    async def prepare_group_upload(
        self: OiBot,
        *,
        group_openid: str,
        file_name: str,
        file_type: FileType | None = None,
        file_size: str | None = None,
        md5: str | None = None,
        sha1: str | None = None,
        md5_10m: str | None = None,
    ) -> RichMediaUploadPrepareResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/upload_prepare",
            json=CompactDict(
                file_type=file_type,
                file_size=file_size,
                file_name=file_name,
                md5=md5,
                sha1=sha1,
                md5_10m=md5_10m,
            ),
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(seconds=1))
    async def finish_group_upload_part(
        self: OiBot,
        *,
        group_openid: str,
        upload_id: str | None = None,
        part_index: int | None = None,
        block_size: str | None = None,
        md5: str | None = None,
    ) -> None:
        await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/upload_part_finish",
            json=CompactDict(
                upload_id=upload_id,
                part_index=part_index,
                block_size=block_size,
                md5=md5,
            ),
        )

    async def upload_group_part(
        self: OiBot,
        *,
        group_openid: str,
        upload_id: str,
        data: bytes,
        block_size: str,
        part: RichMediaUploadPart,
        retry_timeout: int = 300,
        retry_delay: int = 1,
    ) -> None:
        offset = (part["index"] - 1) * int(block_size)
        chunk = data[offset : offset + int(part["block_size"])]

        async with asyncio.timeout(retry_timeout):
            while True:
                try:
                    async with self.client_session.put(
                        part["presigned_url"], data=chunk
                    ) as response:
                        await response.read()

                    return await self.finish_group_upload_part(
                        group_openid=group_openid,
                        upload_id=upload_id,
                        part_index=part["index"],
                        block_size=str(len(chunk)),
                        md5=md5(chunk).hexdigest(),
                    )

                except Exception:
                    await asyncio.sleep(retry_delay)
