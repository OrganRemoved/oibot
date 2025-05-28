import asyncio
import logging
from contextvars import ContextVar
from os import environ
from typing import Any, ClassVar, Iterable, Literal, Self

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.api.access_token import get_app_access_token
from oibot.event import Context
from oibot.plugin import PluginManager


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
