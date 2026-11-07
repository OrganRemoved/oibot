import asyncio
import logging
import os
import sys
from collections import OrderedDict, defaultdict
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Iterator,
)
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    contextmanager,
)
from datetime import datetime, timedelta
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
from operator import length_hint
from types import ModuleType, UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Literal,
    Union,
    get_args,
    get_origin,
    overload,
)

from oibot.event import Event
from oibot.matcher import Matcher

if TYPE_CHECKING:
    from oibot.bot import OiBot


def annotation_event_type(annotation: Any) -> tuple[type[Event], ...]:
    if get_origin(annotation) in {UnionType, Union}:
        return tuple(
            event
            for arg in get_args(annotation)
            for event in annotation_event_type(arg)
        )

    elif isclass(annotation) and issubclass(annotation, Event):
        return (annotation,)

    else:
        return ()


class Dependency:
    __slots__ = ("dependency", "eager")

    def __init__(self, dependency: Callable[..., Any], *, eager: bool = True) -> None:
        self.dependency = dependency
        self.eager = eager

    @overload
    @classmethod
    def from_provider[T](
        cls,
        dependency: type[AbstractAsyncContextManager[T]],
        *,
        eager: Literal[True] = True,
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: type[AbstractAsyncContextManager[T]], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: type[AbstractContextManager[T]], *, eager: Literal[True] = True
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: type[AbstractContextManager[T]], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., AsyncIterator[T]], *, eager: Literal[True] = True
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., AsyncIterator[T]], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., Iterator[T]], *, eager: Literal[True] = True
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., Iterator[T]], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @overload
    @classmethod
    def from_provider[T](
        cls,
        dependency: Callable[..., Coroutine[Any, Any, T]],
        *,
        eager: Literal[True] = True,
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., Coroutine[Any, Any, T]], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., T], *, eager: Literal[True] = True
    ) -> T: ...

    @overload
    @classmethod
    def from_provider[T](
        cls, dependency: Callable[..., T], *, eager: Literal[False]
    ) -> Callable[[], Awaitable[T]]: ...

    @classmethod
    def from_provider(
        cls, dependency: Callable[..., Any], *, eager: bool = True
    ) -> Any:
        return cls(dependency, eager=eager)


class InjectionPlan:
    __slots__ = (
        "dependency_parameters",
        "event_parameters",
        "event_types",
        "parameters",
    )

    def __init__(self, func: Callable[..., Any]) -> None:
        self.parameters = signature(func).parameters

        self.dependency_parameters: tuple[tuple[str, Dependency], ...] = ()
        self.event_parameters: tuple[tuple[str, tuple[type[Event], ...]], ...] = ()
        self.event_types: tuple[type[Event], ...] = ()

        for name, parameter in self.parameters.items():
            if isinstance(parameter.default, Dependency):
                self.dependency_parameters += ((name, parameter.default),)

            elif event_types := annotation_event_type(parameter.annotation):
                self.event_parameters += ((name, event_types),)
                self.event_types += event_types


class QuotaPool:
    __slots__ = ("maxlen", "pool")

    def __init__(self, *, maxlen: int = 128) -> None:
        self.maxlen = maxlen

        self.pool = defaultdict(OrderedDict)

    def __call__(self, event: Event) -> None:
        match getattr(event, "event_type", None):
            case "C2C_MESSAGE_CREATE":
                (pool := self.pool[event.author.user_openid])[event.id] = {
                    "msg_id": event.id,
                    "expire": event.timestamp + timedelta(minutes=30),
                    "msg_seq": iter(range(4)),
                }

            case "GROUP_AT_MESSAGE_CREATE" | "GROUP_MESSAGE_CREATE":
                (pool := self.pool[event.group_openid])[event.id] = {
                    "msg_id": event.id,
                    "expire": event.timestamp + timedelta(minutes=4),
                    "msg_seq": iter(range(5)),
                }

            case "FRIEND_ADD" | "C2C_MSG_RECEIVE":
                (pool := self.pool[event.openid])[event["id"]] = {
                    "event_id": event["id"],
                    "expire": event.timestamp + timedelta(minutes=4),
                    "msg_seq": iter(range(5)),
                }

            case "GROUP_ADD_ROBOT" | "GROUP_MSG_RECEIVE":
                (pool := self.pool[event.group_openid])[event["id"]] = {
                    "event_id": event["id"],
                    "expire": event.timestamp + timedelta(minutes=4),
                    "msg_seq": iter(range(5)),
                }

            case "INTERACTION_CREATE":
                if user_openid := getattr(event, "user_openid", None):
                    (pool := self.pool[user_openid])[event["id"]] = {
                        "event_id": event["id"],
                        "expire": event.timestamp + timedelta(minutes=30),
                        "msg_seq": iter(range(4)),
                    }

                elif group_openid := getattr(event, "group_openid", None):
                    (pool := self.pool[group_openid])[event["id"]] = {
                        "event_id": event["id"],
                        "expire": event.timestamp + timedelta(minutes=4),
                        "msg_seq": iter(range(5)),
                    }

                else:
                    return

            case _:
                return

        while len(pool) > self.maxlen:
            pool.popitem(last=False)

    @staticmethod
    def acquire[**P, R](
        func: Callable[Concatenate[Any, P], Awaitable[R]],
    ) -> Callable[Concatenate[Any, P], Awaitable[R]]:
        @wraps(func)
        async def wrapper(self: OiBot, *args: P.args, **kwargs: P.kwargs) -> R:
            if not (kwargs.get("is_wakeup")):
                while pool := self.quota_pool.pool[
                    kwargs.get("openid") or kwargs.get("group_openid")
                ]:
                    if id := (kwargs.get("msg_id") or kwargs.get("event_id")):
                        if not (quota := pool.pop(id, None)):
                            break
                    else:
                        id, quota = pool.popitem(last=False)

                    if (expire := quota["expire"]) <= datetime.now(expire.tzinfo):
                        continue

                    if (msg_seq := next(quota["msg_seq"], None)) is None:
                        continue

                    if length_hint(quota["msg_seq"]):
                        pool[id] = quota
                        pool.move_to_end(id, last=False)

                    kwargs.update(
                        msg_id=quota.get("msg_id"),
                        event_id=quota.get("event_id"),
                        msg_seq=msg_seq,
                    )

                    break

            return await func(self, *args, **kwargs)

        return wrapper


class SessionManager:
    __slots__ = ("sessions",)

    def __init__(self) -> None:
        self.sessions: dict[str, asyncio.Future] = {}

    @asynccontextmanager
    async def defer(self, *keys: str) -> AsyncGenerator[asyncio.Future]:
        future = asyncio.get_event_loop().create_future()

        self.sessions.update((key, future) for key in keys)

        try:
            yield future

        finally:
            for key in keys:
                self.sessions.pop(key, None)

    def __call__(self, event: Event) -> bool:
        match getattr(event, "event_type", None):
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
    class Executor[T]:
        __slots__ = ("func",)

        def __init__(self, func: Callable[[Event], Awaitable[T | None]]) -> None:
            self.func = func

        async def __call__(self, event: Event) -> T | None:
            return await self.func(event)

    __slots__ = ("executors", "init", "module")

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


class PluginManager:
    __slots__ = ("plugins",)

    def __init__(self) -> None:
        self.plugins: dict[str, Plugin] = {}

    async def __call__(self, event: Event) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                for plugin in self.plugins.values():
                    for executor in plugin.executors:
                        tg.create_task(executor(event))

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


def on[T](
    matcher: Matcher[...] | Callable[..., bool | Awaitable[bool]] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Plugin.Executor[T]]:
    def decorator(func: Callable[..., Awaitable[T]]) -> Plugin.Executor[T]:
        plan = InjectionPlan(func)
        event_type = plan.event_types

        if plan.dependency_parameters:
            dependency_plans: dict[
                Callable[..., Any],
                tuple[
                    InjectionPlan,
                    Callable[[AsyncExitStack, dict[str, Any]], Awaitable[Any]],
                ],
            ] = {}

            def plan_dependency(dependency: Dependency) -> None:
                if dependency.dependency in dependency_plans:
                    return

                dependency_plan = InjectionPlan(dependency.dependency)

                func = dependency.dependency
                f = func

                while isinstance(f, partial):
                    f = f.func

                if isclass(f) and issubclass(f, AbstractAsyncContextManager):

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return await stack.enter_async_context(func(**kwargs))

                elif isclass(f) and issubclass(f, AbstractContextManager):

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return stack.enter_context(func(**kwargs))

                elif isasyncgenfunction(f):

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return await stack.enter_async_context(
                            asynccontextmanager(func)(**kwargs)
                        )

                elif isgeneratorfunction(f):

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return stack.enter_context(contextmanager(func)(**kwargs))

                elif iscoroutinefunction(f):

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return await func(**kwargs)

                else:

                    async def invoke(
                        stack: AsyncExitStack, kwargs: dict[str, Any]
                    ) -> Any:
                        return func(**kwargs)

                dependency_plans[func] = dependency_plan, invoke

                for _, nested in dependency_plan.dependency_parameters:
                    plan_dependency(nested)

            for _, dependency in plan.dependency_parameters:
                plan_dependency(dependency)

            dependency_event_types = tuple(
                event_type
                for dependency_plan, _ in dependency_plans.values()
                for name, event_type in dependency_plan.event_parameters
                if dependency_plan.parameters[name].default is Parameter.empty
            )

            async def resolve_parameters(
                event: Event,
                parameters: tuple[tuple[str, Dependency], ...],
                dependency_cache: dict[Callable[..., Any], asyncio.Future[Any]],
                stack: AsyncExitStack,
            ) -> dict[str, Any]:
                kwargs = {
                    name: partial(
                        resolve_dependency, event, dependency, dependency_cache, stack
                    )
                    for name, dependency in parameters
                    if not dependency.eager
                }

                if len(parameters) == 1:
                    ((name, dependency),) = parameters

                    if dependency.eager:
                        kwargs[name] = await resolve_dependency(
                            event, dependency, dependency_cache, stack
                        )

                    return kwargs

                async with asyncio.TaskGroup() as tg:
                    tasks = {
                        name: tg.create_task(
                            resolve_dependency(
                                event, dependency, dependency_cache, stack
                            )
                        )
                        for name, dependency in parameters
                        if dependency.eager
                    }

                kwargs.update((name, task.result()) for name, task in tasks.items())

                return kwargs

            async def resolve_dependency(
                event: Event,
                dependency: Dependency,
                dependency_cache: dict[Callable[..., Any], asyncio.Future[Any]],
                stack: AsyncExitStack,
            ) -> Any:
                if future := dependency_cache.get(dependency.dependency):
                    return await asyncio.shield(future)

                dependency_cache[dependency.dependency] = future = (
                    asyncio.get_running_loop().create_future()
                )

                try:
                    dependency_plan, invoke = dependency_plans[dependency.dependency]

                    kwargs = {
                        name: event
                        for name, types in dependency_plan.event_parameters
                        if isinstance(event, types)
                    }

                    if dependency_plan.dependency_parameters:
                        kwargs.update(
                            await resolve_parameters(
                                event,
                                dependency_plan.dependency_parameters,
                                dependency_cache,
                                stack,
                            )
                        )

                    future.set_result(await invoke(stack, kwargs))

                except asyncio.CancelledError:
                    future.cancel()

                except BaseException as e:
                    future.set_exception(e)

                return await future

            if not matcher:

                @wraps(func)
                async def wrapper(event: Event) -> T | None:
                    if isinstance(event, event_type) and all(
                        isinstance(event, event_type)
                        for event_type in dependency_event_types
                    ):
                        kwargs = {
                            name: event
                            for name, types in plan.event_parameters
                            if isinstance(event, types)
                        }

                        dependency_cache: dict[
                            Callable[..., Any], asyncio.Future[Any]
                        ] = {}

                        async with AsyncExitStack() as stack:
                            kwargs.update(
                                await resolve_parameters(
                                    event,
                                    plan.dependency_parameters,
                                    dependency_cache,
                                    stack,
                                )
                            )

                            return await func(**kwargs)

            else:
                async_matcher = (
                    matcher if isinstance(matcher, Matcher) else Matcher(matcher)
                )

                if any(
                    param.kind is Parameter.VAR_KEYWORD
                    for param in plan.parameters.values()
                ):

                    @wraps(func)
                    async def wrapper(event: Event) -> T | None:
                        if (
                            isinstance(event, event_type)
                            and all(
                                isinstance(event, event_type)
                                for event_type in dependency_event_types
                            )
                            and (matched := await async_matcher.match(event))
                        ):
                            kwargs = matched | {
                                name: event
                                for name, types in plan.event_parameters
                                if isinstance(event, types)
                            }

                            dependency_cache: dict[
                                Callable[..., Any], asyncio.Future[Any]
                            ] = {}

                            async with AsyncExitStack() as stack:
                                kwargs.update(
                                    await resolve_parameters(
                                        event,
                                        plan.dependency_parameters,
                                        dependency_cache,
                                        stack,
                                    )
                                )

                                return await func(**kwargs)

                else:

                    @wraps(func)
                    async def wrapper(event: Event) -> T | None:
                        if (
                            isinstance(event, event_type)
                            and all(
                                isinstance(event, event_type)
                                for event_type in dependency_event_types
                            )
                            and (matched := await async_matcher.match(event))
                        ):
                            kwargs = {
                                name: value
                                for name, value in matched.items()
                                if name in plan.parameters
                            } | {
                                name: event
                                for name, types in plan.event_parameters
                                if isinstance(event, types)
                            }

                            dependency_cache: dict[
                                Callable[..., Any], asyncio.Future[Any]
                            ] = {}

                            async with AsyncExitStack() as stack:
                                kwargs.update(
                                    await resolve_parameters(
                                        event,
                                        plan.dependency_parameters,
                                        dependency_cache,
                                        stack,
                                    )
                                )

                                return await func(**kwargs)

        else:
            if not matcher:

                @wraps(func)
                async def wrapper(event: Event) -> T | None:
                    if isinstance(event, event_type):
                        return await func(
                            **{
                                name: event
                                for name, types in plan.event_parameters
                                if isinstance(event, types)
                            }
                        )

            elif any(
                param.kind is Parameter.VAR_KEYWORD
                for param in plan.parameters.values()
            ):
                async_matcher = (
                    matcher if isinstance(matcher, Matcher) else Matcher(matcher)
                )

                @wraps(func)
                async def wrapper(event: Event) -> T | None:
                    if isinstance(event, event_type) and (
                        matched := await async_matcher.match(event)
                    ):
                        return await func(
                            **(
                                matched
                                | {
                                    name: event
                                    for name, types in plan.event_parameters
                                    if isinstance(event, types)
                                }
                            )
                        )

            elif len(plan.parameters) == len(plan.event_parameters):
                async_matcher = (
                    matcher if isinstance(matcher, Matcher) else Matcher(matcher)
                )

                @wraps(func)
                async def wrapper(event: Event) -> T | None:
                    if isinstance(event, event_type) and await async_matcher.match(
                        event
                    ):
                        return await func(
                            **{
                                name: event
                                for name, types in plan.event_parameters
                                if isinstance(event, types)
                            }
                        )

            else:
                async_matcher = (
                    matcher if isinstance(matcher, Matcher) else Matcher(matcher)
                )

                @wraps(func)
                async def wrapper(event: Event) -> T | None:
                    if isinstance(event, event_type) and (
                        matched := await async_matcher.match(event)
                    ):
                        return await func(
                            **(
                                {
                                    key: value
                                    for key, value in matched.items()
                                    if key in plan.parameters
                                }
                                | {
                                    name: event
                                    for name, types in plan.event_parameters
                                    if isinstance(event, types)
                                }
                            )
                        )

        return Plugin.Executor(wrapper)

    return decorator
