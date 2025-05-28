import asyncio
from functools import _make_key
from typing import Awaitable, Callable, Hashable, TypedDict
from weakref import WeakValueDictionary

from aiohttp import ClientSession


class AccessToken(TypedDict):
    access_token: str
    expires_in: int


def keep_alive(
    func: Callable[..., Awaitable[AccessToken]],
) -> Callable[..., Awaitable[AccessToken]]:
    cache: dict[Hashable, AccessToken] = {}
    inflight: WeakValueDictionary[Hashable, asyncio.Future] = WeakValueDictionary()

    async def decorator(app_id: str, client_secret: str) -> AccessToken:
        key = _make_key((app_id, client_secret), {}, typed=False)

        if access_token := cache.get(key):
            return access_token

        if future := inflight.get(key):
            result = await future

            if exception := future.exception():
                raise exception

            return result

        inflight[key] = future = asyncio.get_running_loop().create_future()
        cache[key] = access_token = await func(app_id, client_secret)
        future.set_result(access_token)

        asyncio.get_running_loop().call_later(
            int(access_token["expires_in"]) - 30, cache.pop, key, None
        )

        return access_token

    return decorator


@keep_alive
async def get_app_access_token(app_id: str, client_secret: str) -> AccessToken:
    async with ClientSession() as session:
        async with session.post(
            "https://bots.qq.com/app/getAppAccessToken",
            json={"appId": app_id, "clientSecret": client_secret},
        ) as response:
            response.raise_for_status()
            return await response.json()
