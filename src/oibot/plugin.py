import asyncio
import logging
import os
import sys
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    contextmanager,
)
from functools import partial, wraps
from importlib import import_module, reload
from inspect import (
    Parameter,
    isasyncgenfunction,
    isclass,
    iscoroutinefunction,
    isgeneratorfunction,
    signature,
)
from types import ModuleType, UnionType
from typing import Any, AsyncIterator, Awaitable, Callable, Union, get_args, get_origin

from oibot.event import Event
from oibot.matcher import Matcher


class Dependency:
    __slots__ = ("dependency", "signature")

    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency
        self.signature = signature(dependency)

    @classmethod
    def from_provider(cls, dependency: Callable[..., Any], *args, **kwargs) -> Any:
        return cls(
            partial(dependency, *args, **kwargs) if args or kwargs else dependency
        )


class SessionManager:
    __slots__ = ("sessions",)

    def __init__(self) -> None:
        self.sessions: dict[str, asyncio.Future[Event]] = {}

    @asynccontextmanager
    async def defer(self, *keys: str) -> AsyncIterator[asyncio.Future]:
        future = asyncio.get_event_loop().create_future()

        self.sessions |= {key: future for key in keys}

        try:
            yield future

        finally:
            for key in keys:
                self.sessions.pop(key, None)

    def __call__(self, event: Event) -> bool:
        match event.event_type:
            case "C2C_MESSAGE_CREATE":
                if future := self.sessions.get(event.author.user_openid):
                    future.set_result(event)

                    return True

            case "GROUP_AT_MESSAGE_CREATE" | "GROUP_MESSAGE_CREATE":
                if future := self.sessions.get(event.author.member_openid):
                    future.set_result(event)

                    return True

            case "INTERACTION_CREATE":
                if future := self.sessions.get(event.data.resolved.button_id):
                    future.set_result(event)

                    return True

        return False


class Plugin:
    class Executor:
        __slots__ = ("func",)

        def __init__(self, func: Callable[..., Any]) -> None:
            self.func = func

        async def __call__(self, event: Event) -> Any:
            return await self.func(event)

    __slots__ = ("module", "init", "executors")

    def __init__(self, module: ModuleType) -> None:
        self.module = module

        self.init = getattr(module, "init", None)

        self.executors = [
            handler
            for handler in vars(module).values()
            if (
                isinstance(handler, self.Executor)
                and handler.func.__module__ == module.__name__
            )
        ]

    async def __call__(self, event: Event) -> None:
        async with asyncio.TaskGroup() as tg:
            for executor in self.executors:
                tg.create_task(executor(event))


class PluginManager:
    __slots__ = ("plugins",)

    def __init__(self) -> None:
        self.plugins: dict[str, Plugin] = {}

    async def __call__(self, event: Event) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                for plugin in self.plugins.values():
                    tg.create_task(plugin(event))

        except* Exception as e:
            logging.exception(e)

    def import_from(self, plugins: str) -> None:
        def load_module(module_path: str) -> None:
            module_name = (
                os.path.relpath(module_path, os.path.dirname(plugins))
                .removesuffix(".py")
                .replace(os.sep, ".")
            )

            try:
                if module_name in sys.modules:
                    logging.info(f"reloading plugin [{module_name}]")

                    module = reload(sys.modules[module_name])

                else:
                    module = import_module(module_name)

                self.plugins[module_name] = plugin = Plugin(module)

                logging.info(f"loaded plugin [{module_name}]")

                if not (plugin.init or plugin.executors):
                    logging.warning(
                        f"unloaded plugin [{module_name}] due to missing handlers"
                    )

                    self.plugins.pop(module_name, None)

            except Exception as e:
                logging.exception(f"failed to load plugin [{module_name}]: {e}")

                self.plugins.pop(module_name, None)

        if os.path.isdir(plugins):
            for root, _, files in os.walk(plugins):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        load_module(os.path.join(root, file))

        elif (
            os.path.isfile(plugins)
            and plugins.endswith(".py")
            and not os.path.basename(plugins).startswith("_")
        ):
            load_module(plugins)


def on(
    matchers: Matcher | Callable[..., bool | Awaitable[bool]] | None = None,
) -> Callable[..., Any]:
    def annotation_event_type(annotation: Any) -> tuple[type[Event], ...]:
        if get_origin(annotation) in (Union, UnionType):
            return tuple(
                event
                for arg in get_args(annotation)
                for event in annotation_event_type(arg)
            )

        elif isclass(annotation) and issubclass(annotation, Event):
            return (annotation,)

        else:
            return ()

    async def resolve_dependency(
        event: Event,
        dependency: Dependency,
        dependency_cache: dict[Callable[..., Any], asyncio.Future],
        stack: AsyncExitStack,
    ) -> Any:
        func = dependency.dependency

        kwargs: dict[str, Any] = {}
        tasks: dict[str, asyncio.Task] = {}

        if future := dependency_cache.get(dependency.dependency):
            return await future

        dependency_cache[dependency.dependency] = future = (
            asyncio.get_running_loop().create_future()
        )

        try:
            async with asyncio.TaskGroup() as tg:
                for param_name, param in dependency.signature.parameters.items():
                    if isinstance(param.default, Dependency):
                        tasks[param_name] = tg.create_task(
                            resolve_dependency(
                                event, param.default, dependency_cache, stack
                            )
                        )

                    elif isinstance(event, annotation_event_type(param.annotation)):
                        kwargs[param_name] = event

                    elif param.default is not Parameter.empty:
                        kwargs[param_name] = param.default

                    elif param.kind in (
                        Parameter.VAR_POSITIONAL,
                        Parameter.VAR_KEYWORD,
                    ):
                        pass

                    else:
                        raise ValueError(
                            f"cannot resolve dependency for parameter '{param_name}' "
                            f"in function '{func.__name__}'. "
                            f"parameter must have either a default value, be an Event, or be a Dependency"
                        )

            kwargs |= {k: v.result() for k, v in tasks.items()}

            f = func

            while isinstance(f, partial):
                f = f.func

            if isclass(f) and issubclass(f, AbstractAsyncContextManager):
                result = await stack.enter_async_context(func(**kwargs))

            elif isclass(f) and issubclass(f, AbstractContextManager):
                result = stack.enter_context(func(**kwargs))

            elif isasyncgenfunction(f):
                result = await stack.enter_async_context(
                    asynccontextmanager(func)(**kwargs)
                )

            elif isgeneratorfunction(f):
                result = stack.enter_context(contextmanager(func)(**kwargs))

            elif iscoroutinefunction(f):
                result = await func(**kwargs)

            else:
                result = func(**kwargs)

            future.set_result(result)

            return result

        except BaseException as e:
            future.set_exception(e)

            raise

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sign = signature(func)

        event_type = tuple(
            event
            for param in sign.parameters.values()
            for event in annotation_event_type(param.annotation)
        )

        matcher = (
            matchers
            if isinstance(matchers, Matcher)
            else Matcher(matchers or (lambda _: True))
        )

        if any(
            isinstance(param.default, Dependency) for param in sign.parameters.values()
        ):

            @wraps(func)
            async def wrapper(event: Event) -> Any:
                if isinstance(event, event_type) and (
                    matched := await matcher.match(event)
                ):
                    dependency_cache: dict[Callable[..., Any], asyncio.Future] = {}

                    kwargs: dict[str, Any] = {}
                    tasks: dict[str, asyncio.Task] = {}

                    async with AsyncExitStack() as stack:
                        async with asyncio.TaskGroup() as tg:
                            for param_name, param in sign.parameters.items():
                                if isinstance(param.default, Dependency):
                                    tasks[param_name] = tg.create_task(
                                        resolve_dependency(
                                            event,
                                            param.default,
                                            dependency_cache,
                                            stack,
                                        )
                                    )

                                elif isinstance(
                                    event, annotation_event_type(param.annotation)
                                ):
                                    kwargs[param_name] = event

                                elif param.default is not Parameter.empty:
                                    kwargs[param_name] = param.default

                                elif param_name in matched:
                                    kwargs[param_name] = matched.pop(param_name)

                                elif param.kind is Parameter.VAR_POSITIONAL:
                                    pass

                                elif param.kind is Parameter.VAR_KEYWORD:
                                    kwargs |= matched

                                else:
                                    raise ValueError(
                                        f"cannot resolve dependency for parameter '{param_name}' "
                                        f"in function '{func.__name__}'. "
                                        f"parameter must have either a default value, be an Event, or be a Dependency."
                                    )

                        kwargs |= {k: v.result() for k, v in tasks.items()}

                        return await func(**kwargs)

        else:
            if not (
                (param := next(iter(sign.parameters.values()), None))
                and annotation_event_type(param.annotation)
            ):
                raise TypeError(
                    f"function '{func.__name__}' must accept an Event object as its first parameter."
                )

            if any(p.kind == Parameter.VAR_KEYWORD for p in sign.parameters.values()):

                @wraps(func)
                async def wrapper(event: Event) -> Any:
                    if isinstance(event, event_type) and (
                        matched := await matcher.match(event)
                    ):
                        return await func(event, **matched)

            else:

                @wraps(func)
                async def wrapper(event: Event) -> Any:
                    if isinstance(event, event_type) and (
                        matched := await matcher.match(event)
                    ):
                        return await func(
                            event,
                            **{
                                k: v for k, v in matched.items() if k in sign.parameters
                            },
                        )

        return Plugin.Executor(wrapper)

    return decorator
