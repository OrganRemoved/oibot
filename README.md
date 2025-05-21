# OiBot

A lightweight bot framework built on [aiohttp](https://github.com/aio-libs/aiohttp) and the official protocol.

## Quick Start

### Installation

#### Install from GitHub (for development or bleeding-edge features):

```sh
pip install --no-cache --upgrade git+https://github.com/OrganRemoved/oibot.git
```

or

```sh
pip install --no-cache --upgrade https://github.com/OrganRemoved/oibot/archive/refs/heads/main.zip
```

#### Install from PyPI (recommended for stable versions):

```sh
pip install --no-cache --upgrade oibot
```

### Example

The recommended project structure is as follows:

```sh
awesome_oibot
|   __init__.py
|   bot.py
|
\---plugins
        __init__.py
        echo.py
```

#### bot.py

```python
import logging
from os import environ

from oibot.bot import OiBot

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(module)s:%(funcName)s:%(lineno)d]: %(message)s",
)

if __name__ == "__main__":
    (
        OiBot
        # `plugins`: path(s) to plugin directories, passed to `oibot.plugin.PluginManager.import_from(...)`.
        .build(plugins="plugins")
        # arguments: pass directly to `aiohttp.web.run(...)`
        .run(host=environ["OIBOT_HOST"], port=int(environ["OIBOT_PORT"]))
    )
```

#### echo.py

```python
from contextvars import ContextVar
from os import environ
from types import GenericAlias
from typing import Any, AsyncGenerator, ClassVar
from weakref import WeakKeyDictionary

from redis.asyncio.client import Pipeline, Redis

from oibot.event.c2c_message_create import C2CMessageCreate
from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
from oibot.matcher import Matcher
from oibot.plugin import Dependency, on


class ContextVarDescriptor:
    __class_getitem__ = classmethod(GenericAlias)

    def __init__(self, *, default: Any = None) -> None:
        self.default = default

    def __set_name__(self, owner: Any, name: str) -> None:
        self.context_var = ContextVar(name, default=self.default)

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self

        return self.context_var.get()

    def __set__(self, instance: Any, value: Any) -> None:
        self.context_var.set(value)


class Command(Matcher):
    __slots__ = ("command", "separator")

    cache: ClassVar[
        WeakKeyDictionary[C2CMessageCreate | GroupAtMessageCreateEvent, list[str]]
    ] = WeakKeyDictionary()

    argv: ClassVar[ContextVarDescriptor[list[str]]] = ContextVarDescriptor(default=[])
    content: ClassVar[ContextVarDescriptor[str]] = ContextVarDescriptor(default=None)

    def __init__(self, command: str, *, separator: str = " ") -> None:
        super().__init__()

        self.command = command
        self.separator = separator

    def __call__(self, event: C2CMessageCreate | GroupAtMessageCreateEvent) -> bool:
        if self.separator != " ":
            argv = [arg for arg in event.content.strip().split(self.separator) if arg]

        elif not (argv := self.__class__.cache.get(event)):
            self.__class__.cache[event] = argv = [
                arg for arg in event.content.split(self.separator) if arg
            ]

        if matched := self.command in argv:
            self.__class__.argv = [arg for arg in argv if arg != self.command]

            self.__class__.content = self.separator.join(
                arg
                for arg in event.content.split(self.separator)
                if arg != self.command
            )

        elif matched := (command_with_prefix := f"/{self.command}") in argv:
            self.__class__.argv = [arg for arg in argv if arg != command_with_prefix]

            self.__class__.content = self.separator.join(
                arg
                for arg in event.content.split(self.separator)
                if arg != command_with_prefix
            )

        return matched


# Dependency Injection examples:


# Define an async generator for Redis, handling connection creation and cleanup.
async def get_redis(*args, **kwargs) -> AsyncGenerator[Redis, None]:
    if "url" in kwargs:
        redis = Redis.from_url(decode_responses=True, *args, **kwargs)

    elif "connection_pool" in kwargs:
        redis = Redis.from_pool(*args, **kwargs)

    else:
        redis = Redis(
            host=kwargs.pop("host", environ.get("REDIS_HOST", "localhost")),
            port=kwargs.pop("port", int(environ.get("REDIS_PORT", 6379))),
            db=kwargs.pop("db", environ.get("REDIS_DB", 0)),
            password=kwargs.pop("password", environ.get("REDIS_PASSWORD", None)),
            decode_responses=kwargs.pop("decode_responses", True),
            **kwargs,
        )

    async with redis as r:
        yield r


# Chaining Dependency Injection: Define an async generator that depends on another (Redis connection).
async def get_pipeline(
    redis: Redis = Dependency.provide(dependency=get_redis), *args, **kwargs
) -> AsyncGenerator[Pipeline, None]:
    async with redis.pipeline(*args, **kwargs) as pipeline:
        yield pipeline

        await pipeline.execute()


# Event Handler example:


# Combining multiple rules using `&(and)`, `|(or)`, and `~(not)`.
@on(matcher=Command("repeat"))
# For maximum performance, consider using a callable (e.g., a lambda function) directly in the `matcher`.
# Example: `lambda event: event.group_openid in (...)`
async def echo(
    # Specify the event type(s) this handler should process using type hints.  Use `|` or `typing.Union` for multiple types.
    event: GroupAtMessageCreateEvent,
    *,
    redis: Redis = Dependency.provide(dependency=get_redis),
    pipeline: Pipeline = Dependency.provide(dependency=get_pipeline),
) -> None:
    if await redis.get(f"blacklist:group:{event.group_openid}"):
        pipeline.delete(f"config:group:{event.group_openid}")
        pipeline.delete(f"config:user:{event.author.member_openid}")

    if Command.content == "me" or Command.argv == ["me"]:
        event, send_message_response = await event.defer("go !")

        for i in range(10):
            if event.content.strip() == "repeat break":
                await event.reply("repeater stopped")
                return

            event, _ = await event.defer(f"repeat {i}: {event.content.strip()}")

        await event.reply("repeater stopped")
```
