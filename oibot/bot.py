import asyncio
import logging
from contextvars import ContextVar
from functools import _make_key, wraps
from os import environ
from typing import (
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Hashable,
    Iterable,
    Literal,
    Self,
    TypedDict,
)
from weakref import WeakValueDictionary

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.event import Context
from oibot.plugin import PluginManager


class AccessToken(TypedDict):
    access_token: str
    expires_in: int


def singleflight(typed: bool = False) -> Callable[..., Callable[..., Awaitable[Any]]]:
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        futures: WeakValueDictionary[Hashable, asyncio.Future] = WeakValueDictionary()

        @wraps(func)
        async def warpper(*args, **kwargs) -> Any:
            key = _make_key(args, kwargs, typed=typed)

            if future := futures.get(key):
                result = await future

                if exception := future.exception():
                    raise exception

                return result

            futures[key] = future = asyncio.Future()

            try:
                result = await func(*args, **kwargs)
                future.set_result(result)
                return result

            except Exception as e:
                future.set_exception(e)
                raise e

        return warpper

    return decorator


def keep_alive(
    func: Callable[[str, str], Awaitable[AccessToken]],
) -> Callable[[str, str], Awaitable[AccessToken]]:
    cache: dict[tuple[str, str], AccessToken] = {}

    async def decorator(app_id: str, client_secret: str) -> AccessToken:
        key = (app_id, client_secret)

        if not (access_token := cache.get(key)):
            cache[key] = access_token = await func(app_id, client_secret)

            asyncio.get_running_loop().call_later(
                int(access_token["expires_in"]) - 30, cache.pop, key, None
            )

        return access_token

    return decorator


@singleflight(typed=False)
@keep_alive
async def get_app_access_token(app_id: str, client_secret: str) -> AccessToken:
    async with ClientSession() as session:
        async with session.post(
            "https://bots.qq.com/app/getAppAccessToken",
            json={"appId": app_id, "clientSecret": client_secret},
        ) as response:
            response.raise_for_status()
            return await response.json()


async def handler(
    request: Request, *, background_tasks: set[asyncio.Task] = set()
) -> Response:
    ctx: Context = await request.json()

    logging.debug(ctx)

    OiBot.app_id.set(request.query.get("id", environ.get("OIBOT_APP_ID")))
    OiBot.app_token.set(request.query.get("token", environ.get("OIBOT_APP_TOKEN")))
    OiBot.app_secret.set(request.query.get("secret", environ.get("OIBOT_APP_SECRET")))

    match ctx["op"]:
        case 0:
            task = asyncio.create_task(PluginManager.run(ctx=ctx))
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        case 13:
            logging.info("webhook verification request received")

            if not (secret := OiBot.app_secret.get()):
                raise ValueError("parameter `app_secret` must be specified")

            secret = secret.encode("utf-8")

            while len(secret) < 32:
                secret *= 2

            d = ctx["d"]

            return web.json_response(
                {
                    "plain_token": d["plain_token"],
                    "signature": (
                        Ed25519PrivateKey.from_private_bytes(secret[:32])
                        .sign(f"{d['event_ts']}{d['plain_token']}".encode("utf-8"))
                        .hex()
                    ),
                }
            )

        case _:
            logging.warning(f"invalid type received {ctx=}")

    return web.Response(body=None, status=200)


class OiBot:
    __slots__ = ()

    app: ClassVar[web.Application]

    app_id: ClassVar[ContextVar[str | None]] = ContextVar(
        "app_id", default=environ.get("OIBOT_APP_ID")
    )
    app_token: ClassVar[ContextVar[str | None]] = ContextVar(
        "app_token", default=environ.get("OIBOT_APP_TOKEN")
    )
    app_secret: ClassVar[ContextVar[str | None]] = ContextVar(
        "app_secret", default=environ.get("OIBOT_APP_SECRET")
    )

    @classmethod
    async def request(
        cls,
        *,
        method: Literal[
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
            "TRACE",
            "CONNECT",
        ],
        url: str,
        **kwargs,
    ) -> Any:
        logging.debug(f"{method=} {url=} {kwargs=}")

        async with ClientSession(
            base_url=f"https://{'sandbox.' if environ.get('OIBOT_SANDBOX') else ''}api.sgroup.qq.com",
            headers={
                "Authorization": f"QQBot {
                    (
                        await get_app_access_token(
                            app_id=cls.app_id.get(),
                            client_secret=cls.app_secret.get(),
                        )
                    )['access_token']
                }"
            },
        ) as session:
            async with session.request(method, url, **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json()

    @classmethod
    def build(cls, plugins: str | Iterable[str] | None = None, **kwargs) -> Self:
        cls.app = app = web.Application(**kwargs)

        app.router.add_post(path="/", handler=handler)

        if isinstance(plugins, str):
            PluginManager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                PluginManager.import_from(plugin)

        return cls()

    @classmethod
    def run(cls, *args, **kwargs) -> None:
        web.run_app(app=cls.app, *args, **kwargs)
