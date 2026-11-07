from hashlib import md5, sha1
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal, TypedDict

from oibot.api import CompactDict

if TYPE_CHECKING:
    from oibot.bot import OiBot


class MediaImageUploadPrepareResponse(TypedDict):
    upload_id: str
    presigned_url: str
    expires_in: int


class MediaImageUploadResponse(TypedDict):
    image_id: str
    url: str
    ttl: int
    preview_url: str


class MediaImage(TypedDict):
    image_id: str
    url: str
    file_name: str
    preview_url: str
    created_at: int
    expires_at: int


class MediaImageListResponse(TypedDict):
    images: list[MediaImage]
    next_cursor: str
    total: int


class MaterialMixin:
    async def prepare_media_image_upload(
        self: OiBot,
        *,
        file_name: str,
        file_size: int,
        content_type: Literal["image/png", "image/jpeg", "image/gif", "image/webp"],
        md5: str,
        sha1: str,
    ) -> MediaImageUploadPrepareResponse:
        return await self(
            HTTPMethod.POST,
            "/v2/media-images/prepare",
            json={
                "file_name": file_name,
                "file_size": file_size,
                "content_type": content_type,
                "md5": md5,
                "sha1": sha1,
            },
        )

    async def complete_media_image_upload(
        self: OiBot, *, upload_id: str, md5: str
    ) -> MediaImageUploadResponse:
        return await self(
            HTTPMethod.POST,
            "/v2/media-images/complete",
            json={"upload_id": upload_id, "md5": md5},
        )

    async def upload_media_image(
        self: OiBot,
        *,
        data: bytes,
        file_name: str,
        content_type: Literal["image/png", "image/jpeg", "image/gif", "image/webp"],
    ) -> MediaImageUploadResponse:
        prepare = await self.prepare_media_image_upload(
            file_name=file_name,
            file_size=len(data),
            content_type=content_type,
            md5=md5(data).hexdigest(),
            sha1=sha1(data).hexdigest(),
        )

        async with self.client_session.put(
            prepare["presigned_url"], data=data, headers={"Content-Type": content_type}
        ) as response:
            await response.read()
            etag = response.headers["ETag"].strip('"')

        return await self.complete_media_image_upload(
            upload_id=prepare["upload_id"], md5=etag
        )

    async def get_media_images(
        self: OiBot, *, cursor: str | None = None
    ) -> MediaImageListResponse:
        return await self(
            HTTPMethod.GET, "/v2/media-images", params=CompactDict(cursor=cursor)
        )

    async def delete_media_image(self: OiBot, *, image_id: str) -> None:
        return await self(HTTPMethod.DELETE, f"/v2/media-images/{image_id}/delete")
