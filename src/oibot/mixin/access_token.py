import asyncio
from functools import _make_key
from typing import Any, Callable, TypedDict

from oibot.mixin import MixinProtocol


class AccessToken(TypedDict):
    access_token: str
    expires_in: str


def keep_alive(func: Callable[..., Any]) -> Callable[..., Any]:
    futures = {}

    async def wrapper(*args, **kwargs) -> Any:
        key = _make_key(args, kwargs, typed=False)

        if future := futures.get(key):
            return await future

        loop = asyncio.get_running_loop()

        futures[key] = future = loop.create_future()

        try:
            result: AccessToken = await func(*args, **kwargs)
            access_token = result["access_token"]
            future.set_result(access_token)

            loop.call_later(int(result["expires_in"]), lambda: futures.pop(key, None))

            return access_token

        except BaseException as e:
            futures.pop(key, None)

            future.set_exception(e)

            raise

    return wrapper


class AccessTokenMixin:
    @keep_alive
    async def get_app_access_token(
        self: MixinProtocol, app_id: str | None = None, app_secret: str | None = None
    ) -> str:
        return await self(
            "POST",
            "https://bots.qq.com/app/getAppAccessToken",
            json={
                "appId": app_id or self.bot.get().app_id,
                "clientSecret": app_secret or self.bot.get().app_secret,
            },
        )
