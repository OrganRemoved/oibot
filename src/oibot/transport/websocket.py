import asyncio
import logging
from enum import IntEnum, IntFlag
from http import HTTPMethod
from typing import TYPE_CHECKING, Any, TypedDict

from aiohttp import ClientWebSocketResponse, WSMsgType, web

from oibot.api import sliding_window_rate_limit
from oibot.event import Event

if TYPE_CHECKING:
    from oibot.bot import OiBot


class OpCode(IntEnum):
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    RESUME = 6
    RECONNECT = 7
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11


class Intents(IntFlag):
    GUILDS = 1 << 0
    GUILD_MEMBERS = 1 << 1
    GUILD_MESSAGES = 1 << 9
    GUILD_MESSAGE_REACTIONS = 1 << 10
    DIRECT_MESSAGE = 1 << 12
    GROUP_AND_C2C_EVENT = 1 << 25
    INTERACTION = 1 << 26
    MESSAGE_AUDIT = 1 << 27
    FORUMS_EVENT = 1 << 28
    AUDIO_ACTION = 1 << 29
    PUBLIC_GUILD_MESSAGES = 1 << 30


class Gateway(TypedDict):
    url: str


class WebSocketState(TypedDict):
    sequence: int | None
    session_id: str | None
    heartbeat_ack: bool
    reconnect: bool


class WebSocketMixin:
    def __init__(self: OiBot) -> None:
        self.websocket_tasks: set[asyncio.Task[None]] = set()

        self.websocket_state = WebSocketState(
            sequence=None, session_id=None, heartbeat_ack=True, reconnect=False
        )

    def websocket_run(
        self: OiBot,
        *,
        intents: Intents = Intents.GROUP_AND_C2C_EVENT,
        shard: tuple[int, int] = (0, 1),
        properties: dict[str, str] = {},
        host: str = "0.0.0.0",
        port: int = 8080,
        **kwargs: Any,
    ) -> None:
        asyncio.run(
            WebSocketMixin.websocket_serve(
                self,
                intents=intents,
                shard=shard,
                properties=properties,
                host=host,
                port=port,
                **kwargs,
            )
        )

    async def websocket_serve(
        self: OiBot,
        *,
        intents: Intents,
        shard: tuple[int, int],
        properties: dict[str, str],
        host: str,
        port: int,
        **kwargs: Any,
    ) -> None:
        async with self:
            runner = web.AppRunner(self.app)

            try:
                await runner.setup()

                if self.app.router.routes():
                    await web.TCPSite(runner, host, port).start()

                await self.websocket_connect(
                    intents=intents, shard=shard, properties=properties, **kwargs
                )

            finally:
                for task in self.websocket_tasks:
                    task.cancel()

                await asyncio.gather(*self.websocket_tasks, return_exceptions=True)

                await runner.cleanup()

    @sliding_window_rate_limit(limit=50, window=1)
    async def get_gateway(self: OiBot) -> Gateway:
        return await self(HTTPMethod.GET, "/gateway")

    async def identify(
        self: OiBot,
        websocket: ClientWebSocketResponse,
        *,
        access_token: str,
        intents: Intents,
        shard: tuple[int, int],
        properties: dict[str, str],
    ) -> None:
        await websocket.send_json(
            {
                "op": OpCode.IDENTIFY,
                "d": {
                    "token": f"QQBot {access_token}",
                    "intents": intents,
                    "shard": shard,
                    "properties": properties,
                },
            }
        )

    async def heartbeat(
        self: OiBot, websocket: ClientWebSocketResponse, interval: float
    ) -> None:
        while True:
            await asyncio.sleep(interval)

            if not self.websocket_state["heartbeat_ack"]:
                self.websocket_state["reconnect"] = True

                await websocket.close()

                return

            self.websocket_state["heartbeat_ack"] = False

            await websocket.send_json(
                {"op": OpCode.HEARTBEAT, "d": self.websocket_state["sequence"]}
            )

    async def resume(
        self: OiBot, websocket: ClientWebSocketResponse, *, access_token: str
    ) -> None:
        await websocket.send_json(
            {
                "op": OpCode.RESUME,
                "d": {
                    "token": f"QQBot {access_token}",
                    "session_id": self.websocket_state["session_id"],
                    "seq": self.websocket_state["sequence"],
                },
            }
        )

    async def websocket_connect(
        self: OiBot,
        *,
        intents: Intents,
        shard: tuple[int, int],
        properties: dict[str, str],
        **kwargs: Any,
    ) -> None:
        while True:
            try:
                async with self.client_session.ws_connect(
                    (await self.get_gateway())["url"], **kwargs
                ) as websocket:
                    if (ctx := await websocket.receive_json())["op"] != OpCode.HELLO:
                        raise RuntimeError(f"invalid hello payload received {ctx=}")

                    logging.debug(ctx)

                    self.websocket_state.update(heartbeat_ack=True, reconnect=False)

                    access_token = await self.get_access_token(
                        self.app_id, self.app_secret
                    )

                    future = self.app[key := (self.app_id, self.app_secret)]

                    if (
                        self.websocket_state["session_id"] is None
                        or self.websocket_state["sequence"] is None
                    ):
                        await self.identify(
                            websocket,
                            access_token=access_token,
                            intents=intents,
                            shard=shard,
                            properties=properties,
                        )

                    else:
                        await self.resume(websocket, access_token=access_token)

                    heartbeat = asyncio.create_task(
                        self.heartbeat(websocket, ctx["d"]["heartbeat_interval"] / 1000)
                    )

                    try:
                        async for message in websocket:
                            if message.type is WSMsgType.ERROR:
                                raise websocket.exception() or RuntimeError(
                                    "websocket connection failed"
                                )

                            if message.type not in {WSMsgType.TEXT, WSMsgType.BINARY}:
                                continue

                            logging.debug(ctx := message.json())

                            if (sequence := ctx.get("s")) is not None:
                                self.websocket_state["sequence"] = sequence

                            match ctx["op"]:
                                case OpCode.DISPATCH:
                                    match ctx.get("t"):
                                        case "READY":
                                            self.websocket_state["session_id"] = ctx[
                                                "d"
                                            ]["session_id"]

                                            logging.info(
                                                f"websocket session ready {self.websocket_state['session_id']=}"
                                            )

                                        case "RESUMED":
                                            logging.info("websocket session resumed")

                                        case _:
                                            event = Event(self, ctx)

                                            self.quota_pool(event)

                                            if not self.session_manager(event):
                                                self.websocket_tasks.add(
                                                    task := asyncio.create_task(
                                                        self.plugin_manager(event)
                                                    )
                                                )

                                                task.add_done_callback(
                                                    self.websocket_tasks.discard
                                                )

                                case OpCode.HEARTBEAT:
                                    self.websocket_state["heartbeat_ack"] = False

                                    await websocket.send_json(
                                        {
                                            "op": OpCode.HEARTBEAT,
                                            "d": self.websocket_state["sequence"],
                                        }
                                    )

                                case OpCode.RECONNECT:
                                    self.websocket_state["reconnect"] = True

                                    await websocket.close()

                                    break

                                case OpCode.INVALID_SESSION:
                                    if not ctx.get("d"):
                                        self.websocket_state.update(
                                            sequence=None, session_id=None
                                        )

                                    self.websocket_state["reconnect"] = True

                                    await websocket.close()

                                    break

                                case OpCode.HEARTBEAT_ACK:
                                    self.websocket_state["heartbeat_ack"] = True

                                case _:
                                    logging.warning(f"invalid type received {ctx=}")

                    finally:
                        heartbeat.cancel()

                        try:
                            await heartbeat

                        except asyncio.CancelledError:
                            pass

                    if websocket.close_code in {
                        4001,
                        4002,
                        4010,
                        4011,
                        4012,
                        4013,
                        4014,
                        4914,
                        4915,
                    }:
                        logging.error(
                            f"websocket connection rejected code={websocket.close_code}"
                        )

                        return

                    if (
                        websocket.close_code == 1000
                        and not self.websocket_state["reconnect"]
                    ):
                        logging.info("websocket connection closed normally")

                        return

                    if websocket.close_code == 4004:
                        if self.app.get(key) is future:
                            self.app.pop(key)

                        logging.warning(
                            "websocket authentication failed; refreshing access token"
                        )

                    if websocket.close_code in {4006, 4007, 4009} or (
                        websocket.close_code is not None
                        and 4900 <= websocket.close_code <= 4913
                    ):
                        self.websocket_state.update(sequence=None, session_id=None)

                    if websocket.close_code == 4008:
                        logging.warning(
                            "websocket connection rate limited; reconnecting in 60 seconds"
                        )

                        await asyncio.sleep(60)

            except asyncio.CancelledError:
                raise

            except Exception:
                logging.exception("websocket connection failed")
