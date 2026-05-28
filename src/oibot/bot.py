import logging
from contextvars import ContextVar
from enum import IntEnum
from http import HTTPStatus
from os import environ
from typing import Any, AsyncGenerator, Iterable, Literal, NamedTuple

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.api.access_token import AccessTokenMixin
from oibot.api.recall_message import RecallMessageMixin
from oibot.api.send_message import SendMessageMixin
from oibot.api.upload_file import UploadFileMixin
from oibot.matcher import fire_and_forget


class OP(IntEnum):
    MESSAGE = 0
    VERIFICATION = 13


class BotIdentity(NamedTuple):
    app_id: str
    app_token: str
    app_secret: str


class Singleton(type):
    def __call__(cls, *args, **kwargs) -> "OiBot":
        if not (instance := getattr(cls, "instance", None)):
            cls.instance = instance = super().__call__(*args, **kwargs)

        return instance


class OiBot(
    AccessTokenMixin,
    RecallMessageMixin,
    SendMessageMixin,
    UploadFileMixin,
    metaclass=Singleton,
):
    __slots__ = ("app", "plugin_manager", "bot_identity", "session")

    session: ClientSession

    def __init__(self, plugins: str | Iterable[str] | None = None, **kwargs) -> None:
        from oibot.plugin import PluginManager

        self.plugin_manager = plugin_manager = PluginManager(self)

        if isinstance(plugins, str):
            plugin_manager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                plugin_manager.import_from(plugin)

        self.app = app = web.Application(**kwargs)

        app.router.add_post(path="/", handler=self.handler)

        self.bot_identity: ContextVar[BotIdentity] = ContextVar(
            "bot_identity", default=None
        )  # type: ignore

        async def aiohttp_client_session_ctx(
            app: web.Application,
        ) -> AsyncGenerator[None, None]:
            async with ClientSession(base_url="https://api.sgroup.qq.com") as session:
                self.session = session

                yield

        app.cleanup_ctx.append(aiohttp_client_session_ctx)

    async def __call__(
        self,
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

        async with self.session.request(method, url, **kwargs) as resp:
            return await resp.json()

    @property
    def app_id(self) -> str:
        return self.bot_identity.get().app_id

    @property
    def app_token(self) -> str:
        return self.bot_identity.get().app_token

    @property
    def app_secret(self) -> str:
        return self.bot_identity.get().app_secret

    async def handler(self, request: Request) -> Response:
        ctx = await request.json()

        logging.debug(ctx)

        self.bot_identity.set(
            bot_dentity := BotIdentity(
                app_id=request.query.get("id", environ["OIBOT_APP_ID"]),
                app_token=request.query.get("token", environ["OIBOT_APP_TOKEN"]),
                app_secret=request.query.get("secret", environ["OIBOT_APP_SECRET"]),
            )
        )

        match ctx["op"]:
            case OP.MESSAGE:
                fire_and_forget(self.plugin_manager(ctx))

            case OP.VERIFICATION:
                logging.info("webhook verification request received")

                if not (secret := bot_dentity.app_secret):
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

        return web.Response(body=None, status=HTTPStatus.OK)

    def run(self, *args, **kwargs) -> None:
        web.run_app(self.app, *args, **kwargs)
