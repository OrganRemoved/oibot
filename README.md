# OiBot

OiBot is a lightweight, fully asynchronous QQ bot framework built on
[aiohttp](https://github.com/aio-libs/aiohttp). It wraps event delivery, plugin
dispatch, message construction, dependency injection, and the QQ Bot HTTP APIs
in a small, typed interface.

## Table of contents

- [Highlights](#highlights)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
  - [Start the bot](#start-the-bot)
  - [Write the smallest useful plugin](#write-the-smallest-useful-plugin)
- [WebSocket transport](#websocket-transport)
- [Framework design](#framework-design)
  - [Modules are plugins](#modules-are-plugins)
  - [Type annotations are event subscriptions](#type-annotations-are-event-subscriptions)
  - [Matchers can return context](#matchers-can-return-context)
  - [Command: parse and inject arguments](#command-parse-and-inject-arguments)
  - [Require: ordered guards with feedback](#require-ordered-guards-with-feedback)
  - [Lifecycle hooks share the aiohttp application](#lifecycle-hooks-share-the-aiohttp-application)
- [Dependency injection](#dependency-injection)
  - [Lazy dependencies: acquire only when needed](#lazy-dependencies-acquire-only-when-needed)
- [Messages and conversations](#messages-and-conversations)
  - [Turn event handling into a conversation](#turn-event-handling-into-a-conversation)
- [Calling APIs directly](#calling-apis-directly)
- [API reference](#api-reference)
  - [`OiBot`](#oibot)
  - [Plugin, matcher, and dependency APIs](#plugin-matcher-and-dependency-apis)
  - [Message builders](#message-builders)
  - [Sending and streaming messages](#sending-and-streaming-messages)
  - [Rich media uploads](#rich-media-uploads)
  - [Message recall and interactions](#message-recall-and-interactions)
  - [Group management](#group-management)
  - [Group join approval strategies](#group-join-approval-strategies)
  - [Bot information and guilds](#bot-information-and-guilds)
  - [Menus](#menus)
  - [Panels](#panels)
  - [Access tokens and raw requests](#access-tokens-and-raw-requests)
  - [Events](#events)
- [Troubleshooting](#troubleshooting)

## Highlights

- Webhook and WebSocket delivery share one `aiohttp` application and one
  asynchronous QQ Bot API client.
- Webhooks handle callback validation and Ed25519 signature verification;
  WebSockets handle heartbeats, reconnects, token refresh, and session resume.
- One plugin path or several plugin trees can be discovered recursively, with
  module lifecycle hooks and concurrent handler dispatch.
- Handler annotations route concrete events and unions without string event
  names; unknown event types remain observable through the base `Event`.
- Synchronous and asynchronous matchers compose with `&`, `|`, and `~`, return
  handler context, short-circuit synchronous rules, and run compatible
  asynchronous branches concurrently.
- Application-defined matchers such as [`Command`](#command-parse-and-inject-arguments)
  and [`Require`](#require-ordered-guards-with-feedback) turn command parsing,
  ordered access checks, and rejection feedback into reusable rules.
- Dependency graphs support functions, coroutines, generators, context
  managers, eager or lazy resolution, caching within each handler invocation,
  and deterministic reverse-order cleanup. A
  [lookup handler](#lazy-dependencies-acquire-only-when-needed) can validate
  input before creating its HTTP session.
- Typed C2C, at-mention, full-group-message, interaction, friend, membership,
  permission, and join-request events expose parsed authors, mentions,
  attachments, nested message elements, timestamps, and action helpers.
- `reply(...)` and `chat(...)` manage quote identifiers, sequence numbers, and
  isolated text or keyboard conversations while preserving the original event
  context.
- Builders cover plain text, Markdown, keyboards, references, rich media, input
  notifications, and C2C streaming. Byte media is uploaded in server-directed
  concurrent parts; URL media uses the same high-level send API.
- Access-token requests are coalesced and cached until shortly before expiry,
  and local sliding-window limiters provide application-, user-, and
  group-scoped backpressure.
- The HTTP API surface covers messages, rich-media upload, recalls,
  interactions, group state and moderation, join approval strategies, bot and
  guild information, global menus, and targeted panels.

## Requirements

- Python 3.14 or later, as declared in `pyproject.toml`.
- A QQ Bot application ID and application secret.

## Installation

Install the latest stable release from PyPI:

```sh
python -m pip install --upgrade oibot
```

For a project managed by uv:

```sh
uv add oibot --frozen
```

Install the latest development version from GitHub:

```sh
python -m pip install --upgrade 'oibot @ git+https://github.com/OrganRemoved/oibot.git'
```

Alternatively, install the branch archive:

```sh
python -m pip install --upgrade https://github.com/OrganRemoved/oibot/archive/refs/heads/main.zip
```

## Quick start

Create an importable plugin package next to the bot entry point:

```text
awesome_oibot/
├── bot.py
└── plugins/
    ├── __init__.py
    └── echo.py
```

### Start the bot

```python
import logging
from os import environ

from oibot.bot import OiBot


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(module)s:%(funcName)s:%(lineno)d] %(message)s",
)


if __name__ == "__main__":
    OiBot(
        plugins="plugins",
        app_id=environ["OIBOT_APP_ID"],
        app_secret=environ["OIBOT_APP_SECRET"],
    ).webhook(
        path="/callback",
        host=environ.get("OIBOT_HOST", "0.0.0.0"),
        port=int(environ.get("OIBOT_PORT", "8080")),
    )
```

Configure the platform callback URL to point to the public HTTPS URL ending in
`/callback`, then run `python bot.py` from `awesome_oibot`. OiBot handles the
callback-validation request with the configured application secret and rejects
event deliveries whose Ed25519 request signature is missing or invalid.

### Write the smallest useful plugin

The following follows the minimal pattern used by the accompanying bot
plugins: one ordinary rule, one typed event parameter, and one async handler.
There is no plugin base class, manifest, registration call, or
framework-specific wrapper to maintain.

```python
from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
from oibot.event.group_message_create import GroupMessageCreateEvent
from oibot.plugin import on


@on(lambda event: event.content.strip() in {"Oi", "oi"})
async def oi(event: GroupAtMessageCreateEvent | GroupMessageCreateEvent) -> None:
    await event.reply("Ciallo～(∠・ω< )⌒☆")
```

This small plugin already demonstrates the central framework design:

- The handler annotation is the event subscription. The union receives both
  at-mention and full-group-message events without duplicate handlers.
- A matcher can be any synchronous or asynchronous callable. A lambda keeps a
  simple hot path simple; richer rules can use `Matcher` composition.
- `event.reply(...)` preserves the event context and lets the framework manage
  reply identifiers, sequence numbers, rate limits, and transport details.
- The decorated function is discovered automatically when OiBot imports the
  plugin directory.

## WebSocket transport

For WebSocket event delivery, import `Intents` from its concrete module and
combine the required flags with `|`:

```python
from os import environ

from oibot.bot import OiBot
from oibot.transport.websocket import Intents


if __name__ == "__main__":
    OiBot(
        plugins="plugins",
        app_id=environ["OIBOT_APP_ID"],
        app_secret=environ["OIBOT_APP_SECRET"],
    ).websocket(intents=Intents.GROUP_AND_C2C_EVENT | Intents.INTERACTION)
```

`GROUP_AND_C2C_EVENT` is the default. Add `INTERACTION` for callback buttons.
Other flags include `GUILDS`, `GUILD_MEMBERS`, `GUILD_MESSAGES`,
`GUILD_MESSAGE_REACTIONS`, `DIRECT_MESSAGE`, `MESSAGE_AUDIT`, `FORUMS_EVENT`,
`AUDIO_ACTION`, and `PUBLIC_GUILD_MESSAGES`.

Both `webhook(...)` and `websocket(...)` are blocking entry points that own the
bot HTTP-client lifecycle. Inside a running handler, use `event.bot` for API
calls.

## Framework design

The event path is deliberately short and explicit:

```text
Webhook / WebSocket
        ↓
typed Event + reply/session context
        ↓
PluginManager
        ↓
type annotation → matcher → dependency graph
        ↓
async handler
```

This keeps transport concerns outside business plugins while preserving the
original event and bot instance all the way to the handler.

### Modules are plugins

`OiBot(plugins=...)` accepts one path or an iterable of paths. Directories are
scanned recursively and Python files beginning with `_` are ignored. An
imported module becomes a plugin when it exposes at least one `@on(...)`
handler or an `init(app)` lifecycle hook.

There is no plugin object graph to construct. A plugin remains an ordinary
Python module, so its functions, types, and tests stay easy to reuse. Handlers
from all loaded plugins are dispatched concurrently with `asyncio.TaskGroup`;
execution order is intentionally not part of the contract.

### Type annotations are event subscriptions

`@on(...)` inspects the handler signature. An event parameter annotated with a
concrete `Event` subclass selects that event, and a union selects several event
types. Annotating with the base `Event` creates a catch-all handler.

Import event classes from their concrete modules, for example
`oibot.event.friend_add`. The `oibot.event` package itself defines the base
`Event` and `EventType`.

This design provides three benefits at once:

- dispatch metadata lives next to the parameter that consumes the event;
- editors and type checkers know the exact event interface inside the handler;
- the framework can inject the matching event without string-based event names.

A handler must have at least one event-typed parameter. Without one, it has no
event subscription and will not run.

### Matchers can return context

A matcher may return a boolean-like value or a dictionary. A non-empty
dictionary both marks the rule as matched and supplies named values to the
handler; `{}`, `None`, and other falsy results mean no match:

```python
from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
from oibot.event.group_message_create import GroupMessageCreateEvent
from oibot.plugin import on


MessageEvent = GroupAtMessageCreateEvent | GroupMessageCreateEvent


def echo_rule(event: MessageEvent) -> dict[str, str] | None:
    content = event.content.strip()

    if content.startswith("echo "):
        return {"text": content.removeprefix("echo ").strip()}


@on(echo_rule)
async def echo(event: MessageEvent, *, text: str) -> None:
    await event.reply(text)
```

Only dictionary keys matching named handler parameters are injected. A handler
with `**kwargs` receives the complete matcher context.

For reusable rules, `Matcher` supports `&`, `|`, and `~`, with
`Matcher.all(...)` and `Matcher.any(...)` as named equivalents. Synchronous
rules are evaluated before asynchronous work; compatible asynchronous rules
are scheduled concurrently. Successful `&` branches merge their dictionaries,
which makes parsing, authorization, and feature-state rules independently
composable.

### Command: parse and inject arguments

`Command` and `Require` below are small application-defined `Matcher`
subclasses, not built-in OiBot exports. Put them in `helper/matcher.py`, with an
empty `helper/__init__.py`.

```python
from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
from oibot.event.group_message_create import GroupMessageCreateEvent
from oibot.matcher import Matcher


MessageEvent = GroupAtMessageCreateEvent | GroupMessageCreateEvent


class Command(Matcher[[MessageEvent]]):
    def __init__(self, command: str) -> None:
        super().__init__()
        self.commands = {command, f"/{command}"}

    def __call__(self, event: MessageEvent) -> dict[str, list[str]] | None:
        argv = event.content.split()
        if argv and argv[0] in self.commands:
            return {"argv": argv}
```

For `/echo hello`, `Command("echo")` returns
`{"argv": ["/echo", "hello"]}`. OiBot injects `argv` into the handler by parameter
name. Command aliases compose naturally with `|`.

### Require: ordered guards with feedback

`Require` checks its primary rule, then its requirements in order. This minimal
version supports a text reply when its primary rule fails. Append it to the
same helper module:

```python
class Require(Matcher[[MessageEvent]]):
    def __init__(self, matcher, *requirements, on_unmet: str | None = None):
        super().__init__()
        self.matcher = matcher
        self.requirements = requirements
        self.on_unmet = on_unmet

    async def __call__(self, event: MessageEvent):
        matched = await self.matcher.match(event)
        if not matched:
            if self.on_unmet:
                await event.reply(self.on_unmet)
            return {}

        for requirement in self.requirements:
            if not await requirement.match(event):
                return {}

        return matched
```

For example, allow administrators to use either `/echo` or `/say`:

```python
from helper.matcher import Command, MessageEvent, Require
from oibot.matcher import Matcher
from oibot.plugin import on


is_admin = Matcher(lambda event: event.author.member_role in {"admin", "owner"})


@on(
    Require(
        Command("echo") | Command("say"),
        Require(is_admin, on_unmet="This command requires an administrator."),
    )
)
async def echo(event: MessageEvent, *, argv: list[str]) -> None:
    await event.reply(" ".join(argv[1:]) or "Usage: /echo <text>")
```

Unrelated messages stop before the permission check. A denied command gets
the inner `Require`'s reply; an allowed command passes the original `argv` to
the handler. `match(...)` handles both synchronous and asynchronous checks, so
the same structure works with a permission lookup that needs I/O.

### Lifecycle hooks share the aiohttp application

A plugin may define `init(app)`. Use an asynchronous generator when a resource
needs deterministic setup and cleanup:

```python
from collections.abc import AsyncIterator

from aiohttp import ClientSession, web


async def init(app: web.Application) -> AsyncIterator[None]:
    async with ClientSession(base_url="https://example.com") as client:
        app["upstream_client"] = client
        yield
```

Synchronous and asynchronous generator functions and ordinary lifecycle
callables are supported. Generator cleanup runs when the transport shuts down.
The same `aiohttp.web.Application` is available as `bot.app`, allowing the
entry point and plugins to share routes, schedulers, connection pools, and
other process-wide resources without framework-specific containers.

## Dependency injection

Dependencies are parameter defaults declared with
`Dependency.from_provider(...)`. The provider may be a synchronous function,
coroutine function, generator, async generator, context-manager class, or
async-context-manager class.

The smallest resource dependency needs no wrapper function:

```python
from aiohttp import ClientSession

from oibot.event.group_at_message_create import GroupAtMessageCreateEvent
from oibot.event.group_message_create import GroupMessageCreateEvent
from oibot.plugin import Dependency, on


@on(lambda event: event.content.strip() == "status")
async def status(
    event: GroupAtMessageCreateEvent | GroupMessageCreateEvent,
    *,
    session: ClientSession = Dependency.from_provider(ClientSession),
) -> None:
    async with session.get("https://example.com/health") as response:
        await event.reply(await response.text())
```

The framework enters `ClientSession` as an async context manager and closes it
after the handler finishes. The same lifecycle applies to custom generators
and context managers.

Providers may depend on other providers and may request the current event with
a type annotation. OiBot builds the dependency graph once when the decorator is
evaluated, then resolves it for each matching event:

- independent eager dependencies are resolved concurrently;
- the same provider callable used several times in one handler invocation is
  resolved once and cached;
- nested dependencies share the same cache and `AsyncExitStack`;
- generator and context-manager cleanup runs in reverse acquisition order; and
- `eager=False` injects a zero-argument async resolver, so an expensive browser,
  HTTP client, or other resource is created only when the handler actually
  awaits that resolver.

This keeps resource ownership local to a handler while retaining explicit
types and deterministic cleanup. Application-lifetime resources can instead
live in `bot.app`, so request-lifetime and process-lifetime dependencies remain
separate by design.

### Lazy dependencies: acquire only when needed

A lookup command can return usage text before it ever needs an HTTP client:

```python
from collections.abc import Awaitable, Callable

from aiohttp import ClientSession
from helper.matcher import Command, MessageEvent
from oibot.plugin import Dependency, on


@on(Command("lookup"))
async def lookup(
    event: MessageEvent,
    *,
    argv: list[str],
    get_session: Callable[[], Awaitable[ClientSession]] = Dependency.from_provider(
        ClientSession, eager=False
    ),
) -> None:
    if len(argv) < 2:
        await event.reply("Usage: /lookup <keyword>")
        return

    session = await get_session()
    async with session.get(
        "https://api.example.com/search", params={"q": " ".join(argv[1:])}
    ) as response:
        response.raise_for_status()
        await event.reply(await response.text())
```

`/lookup` returns the usage hint without creating a session. `/lookup example`
creates one at `await get_session()`. OiBot reuses it within that handler
invocation and closes it when the handler exits, including on exceptions.

With eager injection, the session would be created before the argument check.
`eager=False` lets the handler decide when acquisition is needed while keeping
automatic cleanup. The URL above is a placeholder for your own API.

## Messages and conversations

Common message events expose `reply(...)`. A string is converted to a plain
text message, while the builders in `oibot.api.message` cover Markdown,
keyboards, rich media, references, and input notifications.

```python
from oibot.api.message import Button, Buttons, Keyboard, Markdown, Media, Message


await event.reply(
    Message.markdown(
        Markdown(Markdown.h2("OiBot"), "Choose an action:"),
        keyboard=Keyboard(
            Buttons(
                Button.callback(
                    id="confirm",
                    label="Confirm",
                    visited_label="Confirmed",
                    data={"confirmed": True},
                ),
                Button.jump(
                    id="project",
                    label="Project",
                    data="https://github.com/OrganRemoved/oibot",
                ),
            )
        ),
    )
)


await event.reply(
    Message.media(Media.image(url="https://example.com/image.png"), content="An image")
)
```

`Media.image(...)`, `Media.video(...)`, `Media.voice(...)`, and
`Media.file(...)` accept a URL or bytes through `data=...`. The high-level
`send_user_message(...)` and `send_group_message(...)` methods prepare and
upload byte content automatically, including multipart uploads when required.

### Turn event handling into a conversation

`chat(...)` sends a message and suspends only the current handler until the
same user replies. If the outgoing Markdown contains a keyboard, it waits for a
callback from that keyboard instead:

```python
from oibot.api.message import Button, Buttons, Keyboard, Markdown, Message


try:
    interaction = await event.chat(
        Message.markdown(
            Markdown("Continue?"),
            keyboard=Keyboard(
                Buttons(
                    Button.callback(
                        id="continue", label="Continue", data={"continue": True}
                    )
                )
            ),
        ),
        timeout=30,
    )
except TimeoutError:
    await event.reply("Timed out.")
else:
    if interaction.button_data["continue"]:
        await interaction.reply("Continuing.")
```

OiBot namespaces callback IDs on a copy of the outgoing message, so concurrent
conversations do not collide. The session manager routes the matching event
directly to the suspended handler instead of broadcasting it to every plugin.
For a plain-text or media prompt, `chat(...)` waits for the same user's next
message.

The transport also records recent incoming message or event identifiers in a
bounded quota pool. When a reply does not specify `msg_id`, `event_id`, or
`msg_seq`, the sending layer acquires valid reply context automatically. This
keeps protocol bookkeeping out of plugin code while still allowing callers to
override every field explicitly.

## Calling APIs directly

During event handling, the complete API client is available as `event.bot`:

```python
from oibot.api.message import Message


await event.bot.send_group_message(
    group_openid=event.group_openid, message=Message.content("A proactive message")
)

await event.bot.delete_group_message(
    group_openid=event.group_openid, message_id="MESSAGE_ID"
)
```

For a one-off API call outside a running transport, use `OiBot` as an async
context manager so its HTTP client is opened and closed correctly:

```python
import asyncio
from os import environ

from oibot.bot import OiBot


async def main() -> None:
    async with OiBot(
        app_id=environ["OIBOT_APP_ID"], app_secret=environ["OIBOT_APP_SECRET"]
    ) as bot:
        information = await bot.get_bot_information()
        print(information)


asyncio.run(main())
```

Access tokens are cached and refreshed before expiry. The API methods also use
local sliding-window limiters keyed by application and, where appropriate, by
user or group. This provides backpressure without forcing every plugin to
implement its own limiter.

## API reference

This section documents the application-level interface implemented by the
current source tree. `OiBot` composes the API mixins, so every method below is
called directly on a bot instance. API methods are asynchronous unless stated
otherwise. Parameters following `*` are keyword-only.

The package root deliberately does not re-export the public types. Import each
name from its concrete module:

```python
from oibot.api.interaction import Code
from oibot.api.message import (
    Button,
    ButtonActionPermission,
    ButtonRenderDataStyle,
    Buttons,
    Keyboard,
    Markdown,
    Media,
    Message,
    MessageReference,
    MsgType,
    StreamInputState,
    at,
    channel,
)
from oibot.api.rich_media import FileType
from oibot.bot import OiBot
from oibot.matcher import Matcher
from oibot.plugin import Dependency, on
from oibot.transport.websocket import Intents
```

Request and response models are ordinary dictionaries at runtime, with
`TypedDict` definitions providing editor and type-checker support. Optional
arguments whose value is `None` are omitted from request payloads where the API
uses `CompactDict`.

### `OiBot`

```python
OiBot(
    plugins: str | Iterable[str] | None = None,
    *,
    app_id: str | None = None,
    app_secret: str | None = None,
    **application_options,
)
```

`plugins` accepts a Python file, a directory, or an iterable containing either.
Additional constructor options are forwarded to `aiohttp.web.Application`.

| Member | Behavior |
| --- | --- |
| `app` | Shared `aiohttp.web.Application`. It also stores `app["bot"]` and the credential context variables and is passed to plugin lifecycle hooks. |
| `app_id` / `app_secret` | Credentials for the current context. API calls use them to obtain an access token. |
| `async with bot` | Opens and closes the authenticated `aiohttp.ClientSession`. Use this form for one-off API calls outside a transport. |
| `webhook(path="/", host="0.0.0.0", port=8080, **route_options)` | Blocking Webhook entry point. Registers the POST route, validates callbacks and signatures, starts the HTTP server, and owns shutdown. |
| `websocket(intents=Intents.GROUP_AND_C2C_EVENT, shard=(0, 1), properties={}, host="0.0.0.0", port=8080, **connect_options)` | Blocking WebSocket entry point. `Intents` flags combine with `\|`; extra options go to `aiohttp`'s WebSocket connection. An HTTP site is also started when plugins added application routes. |
| `await bot(method, url, **request_options)` | Low-level authenticated request interface used by all API mixins. It returns decoded JSON or `None` for an empty body. |

The blocking transport methods run the application lifecycle hooks as well as
the client session. A bare `async with OiBot(...)` opens only the API client; it
does not start event delivery or the `aiohttp` application runner.

### Plugin, matcher, and dependency APIs

| API | Behavior |
| --- | --- |
| `@on(matcher=None)` | Declares an async handler. One or more parameters must be annotated with `Event` subclasses; a union subscribes to every member type. |
| `Matcher(rule)` | Wraps a synchronous or asynchronous rule. A truthy result matches; a non-empty dictionary also becomes injectable handler context. `{}` means no match. |
| `left & right` / `Matcher.all(...)` | Requires every rule to match and merges dictionary results. Synchronous rules run first; asynchronous branches may run concurrently. |
| `left \| right` / `Matcher.any(...)` | Returns the first successful rule context. |
| `~matcher` | Inverts whether the wrapped matcher succeeds. |
| `await matcher.match(...)` | Normalizes a successful result to a dictionary and a failed result to `{}`. |
| `Dependency.from_provider(provider, eager=True)` | Declares a parameter dependency. Set `eager=False` to inject an async zero-argument resolver instead of the resolved value. |
| `init(app)` | Optional module lifecycle hook. Ordinary sync/async callables and sync/async generators are supported; generator cleanup runs during application shutdown. |

Dependency providers may themselves declare event parameters and dependencies.
Within one matched handler graph, each provider callable is resolved once.
Independent eager providers run concurrently, while generators and context
managers are released in reverse acquisition order through one
`AsyncExitStack`.

### Message builders

The builders in [`oibot.api.message`](src/oibot/api/message.py) are dictionary
subclasses, so they can be passed directly to the API while retaining typed
constructors.

#### `Message` and `Media`

| Builder | Result |
| --- | --- |
| `Message.content(text, ...)` | Plain-text message. |
| `Message.markdown(markdown=None, *, keyboard=None, ...)` | Markdown message, optionally with an inline keyboard. |
| `Message.media(media, *, content=None, ...)` | Image, video, voice, or file message with optional accompanying text. |
| `Message.input_notify(input_second, ...)` | C2C input-status notification. Group sends do not accept this message type. |
| `Media.image(...)` / `video(...)` / `voice(...)` / `file(...)` | Rich-media descriptor. Supply bytes with `data=...` or a remote `url=...`; `file_name` is optional. |
| `MessageReference(message_id=...)` | Adds a reference to another message. |

Every `Message` constructor also accepts the applicable `msg_id`, `event_id`,
`msg_seq`, `message_reference`, and `is_wakeup` fields. Normally
`event.reply(...)` or the quota pool supplies reply context automatically; set
these fields when explicit protocol control is required.

#### `Markdown`

`Markdown(*elements, separator="\n", indent=False,
force_verify_image_resource=None)` joins fragments and stores the final
`content`. `str(markdown)` returns that content.

| Helpers | Purpose |
| --- | --- |
| `h1` through `h6` | Headings |
| `emphasis`, `strong_emphasis`, `strikethrough` | Inline emphasis |
| `code_span`, `fenced_code_block`, `inline_latex` | Code and formula formatting |
| `link`, `autolink`, `image` | Links and Markdown image resources |
| `block_quote`, `bullet_list`, `ordered_list`, `task_list` | Block and list layouts, including nested `Markdown` fragments |
| `table(header=..., rows=..., alignments=...)` | Table with optional `left`, `center`, or `right` alignment per column |
| `thematic_break` | Horizontal separator |
| `cmd_enter`, `cmd_input` | QQ Bot command-entry and command-input tags |

#### Keyboards and mentions

```python
keyboard = Keyboard(
    Buttons(
        Button.callback(
            id="refresh",
            label="Refresh",
            data={"action": "refresh"},
            permission=ButtonActionPermission.all(),
        ),
        Button.instruction(id="search", label="Search", data="/search ", enter=False),
    ),
    Buttons(Button.jump(id="docs", label="Documentation", data="https://example.com")),
)
```

| Builder | Behavior |
| --- | --- |
| `Keyboard(*rows)` | Builds an inline keyboard; each positional row is a `Buttons(...)` instance. |
| `Button.jump(...)` | Opens the URL or target supplied in `data`. |
| `Button.callback(...)` | Emits an interaction. Dictionary `data` is compact JSON-encoded automatically; the default permission is everyone. |
| `Button.instruction(...)` | Inserts or sends command text, controlled by `reply`, `enter`, and `anchor`. |
| `ButtonActionPermission.all()` / `admin()` | Allows everyone or group administrators. |
| `ButtonActionPermission.specify_user_ids(...)` / `specify_role_ids(...)` | Limits an action to selected users or roles. |
| `ButtonRenderDataStyle` | `GRAY`, `BLUE`, `WHITE`, and `BLUE_BACKGROUND` render styles. |
| `at(id)` | Returns an at-user tag; `at("all")` returns the at-everyone tag. |
| `channel(channel_id)` | Returns a channel mention. |

`ButtonRenderData`, `ButtonAction`, `Buttons`, `Rows`, `Keyboard`,
`MessageReference`, and `InputNotify` remain available for callers that need to
construct lower-level payloads directly.

### Sending and streaming messages

The high-level `send_*` methods accept a `Message` builder and are the preferred
entry points. The lower-level `*_message` methods expose the wire fields
directly. Use `MsgType.PLAINTEXT`, `MARKDOWN`, `INPUT_NOTIFY`, or `MEDIA`
instead of their numeric wire values.

| Method | Behavior and return value |
| --- | --- |
| `send_user_message(*, openid, message)` | Sends a C2C `Message`. URL media is registered automatically; byte media is prepared, uploaded in server-directed concurrent parts, finalized, and then sent. Returns `MessageResponse`. |
| `send_group_message(*, group_openid, message)` | Group counterpart to `send_user_message`. Returns `MessageResponse`. |
| `send_raw_user_message(*, openid, msg_type, content=None, markdown=None, keyboard=None, media=None, message_reference=None, input_notify=None, event_id=None, msg_id=None, is_wakeup=None, msg_seq=None)` | Low-level C2C send. `media` is a finalized `MediaInfo` rather than a `Media` builder. |
| `send_raw_group_message(*, group_openid, msg_type, content=None, markdown=None, keyboard=None, media=None, message_reference=None, event_id=None, msg_id=None, is_wakeup=None, msg_seq=None)` | Low-level group send. |
| `stream_user_message(*, openid, input_state, index, content_type, content_raw, input_mode="append", event_id=None, msg_id=None, stream_msg_id=None, msg_seq=None, is_wakeup=None)` | Sends or updates a C2C stream. `content_type` is `"text"` or `"markdown"` and `input_mode` is `"append"` or `"replace"`. |

`StreamInputState.GENERATING` marks an in-progress stream and
`StreamInputState.FINISHED` completes it. `MessageResponse` contains `id`,
`timestamp`, and `ext_info.ref_idx`; `StreamMessageResponse` may additionally
contain `remain_msg_len`.

The high-level media path deep-copies the message before replacing its media
descriptor, so a builder can be reused safely. Recent supported incoming
events populate a bounded quota pool. When `send_raw_user_message(...)` or
`send_raw_group_message(...)` receives no `msg_id` or `event_id`, it can acquire
a valid identifier and sequence number from that pool. Local limiters apply
application-, user-, and group-scoped backpressure; platform-side limits and
errors still remain authoritative.

### Rich media uploads

[`oibot.api.rich_media`](src/oibot/api/rich_media.py) exposes the upload
protocol used by `send_user_message(...)` and `send_group_message(...)`.
`FileType` has `IMAGE`, `VIDEO`, `VOICE`, and `FILE` members.

| Method | Behavior |
| --- | --- |
| `upload_user_file(*, openid, file_type, url=None, srv_send_msg=False, file_name=None, upload_id=None)` | Registers URL media or a completed upload for a user and returns `RichMediaUploadResponse`. |
| `upload_group_file(*, group_openid, file_type, url=None, srv_send_msg=False, file_name=None, upload_id=None)` | Registers URL media or a completed upload for a group and returns `RichMediaUploadResponse`. |
| `prepare_user_upload(*, openid, file_type=None, file_size=None, file_name=None, md5=None, sha1=None, md5_10m=None)` | Starts a multipart user upload. |
| `prepare_group_upload(*, group_openid, file_type=None, file_size=None, file_name=None, md5=None, sha1=None, md5_10m=None)` | Starts a multipart group upload. |
| `upload_user_part(*, openid, upload_id, data, block_size, part, retry_timeout=300, retry_delay=1)` | Uploads one prepared user part and reports its digest. |
| `upload_group_part(*, group_openid, upload_id, data, block_size, part, retry_timeout=300, retry_delay=1)` | Uploads one prepared group part and reports its digest. |
| `finish_user_upload_part(*, openid, upload_id=None, part_index=None, block_size=None, md5=None)` | Marks one user-upload part complete. |
| `finish_group_upload_part(*, group_openid, upload_id=None, part_index=None, block_size=None, md5=None)` | Marks one group-upload part complete. |

`RichMediaUploadPrepareResponse` supplies `upload_id`, `block_size`, the
presigned `parts`, and an `upload_config` containing concurrency and retry
settings. `RichMediaUploadResponse` supplies `file_uuid`, `file_info`, `ttl`,
and optional `id` and `raw_url`. Application code normally needs these
low-level methods only when implementing a custom upload pipeline.

### Message recall and interactions

| Method | Behavior |
| --- | --- |
| `delete_user_message(*, openid, message_id)` | Recalls a C2C message. |
| `delete_group_message(*, group_openid, message_id)` | Recalls a group message. |
| `delete_channel_message(*, channel_id, message_id, hide_tip=False)` | Recalls a channel message, optionally hiding the recall notice. |
| `delete_dm_message(*, guild_id, message_id, hide_tip=False)` | Recalls a direct message in a guild context. |
| `acknowledge_interaction(*, interaction_id, code)` | Acknowledges an interaction result and returns `None`. |

Use the `Code` enum for interaction acknowledgement:
`SUCCESS`, `FAILURE`, `RATE_LIMIT_EXCEEDED`, `DUPLICATE_OPERATION`,
`PERMISSION_DENIED`, or `REQUIRES_ADMIN_PRIVILEGES`. An
`InteractionCreateEvent` also exposes `await event.acknowledge(code)`, which
returns `None`.

### Group management

| Method | Behavior and return value |
| --- | --- |
| `get_group_info(*, group_openid)` | Returns `GroupInformation` with the open ID, name, memo, class, tags, and member count. |
| `get_group_bot_state(*, group_openid)` | Returns `BotState` with the bot member ID, join time, proactive-message permission, receive setting, and member role. |
| `get_group_members(*, group_openid, cursor=None)` | Returns up to 30 `GroupMember` records and the next pagination cursor. |
| `get_group_member(*, group_openid, member_openid)` | Returns one `GroupMember` with its role, join time, bot flag, and optional union open ID. |
| `remove_group_members(*, group_openid, member_openids, add_to_member_blacklist=False)` | Removes up to 20 members and optionally adds them to the group blacklist. |
| `get_group_join_requests(*, group_openid, cursor=None, limit=None)` | Returns a cursor-based `JoinRequestListResponse`. |
| `review_group_join_request(*, group_openid, member_openid, op, join_request_id=None, reject_reason=None, add_to_member_blacklist=False)` | Approves or declines one request. `op` is `"approve"` or `"decline"`. |
| `get_group_member_blacklist(*, group_openid, cursor=None, limit=None)` | Lists blacklisted users and returns the next cursor; `limit` defaults to 20 and cannot exceed 100. |
| `update_group_member_blacklist(*, group_openid, op, member_openids)` | Adds or removes up to 20 users with `op="add"` or `"del"` and returns any failed open IDs. |
| `get_group_restrict_chat_setting(*, group_openid)` | Returns the global mute rule and current member mute states. |
| `set_group_restrict_chat_setting(*, group_openid, members=None)` | Applies member mute operations. Each `SetMemberMuteState` uses `op="add"`, `"update"`, or `"del"` plus `member_openid` and optional `mute_expire_at`. |

A group member includes its open ID, username, role, bot flag, join time, and an
optional union open ID. The QQ Bot platform currently exposes the five member
listing, lookup, removal, and blacklist methods above only to invited
applications.

A join request includes its request and member IDs, username, source and apply
time, risk information, optional inviter, bot flag, and optional verification
message or question-and-answer list. The corresponding
`GroupJoinRequestEvent` provides `approve()` and `decline(...)` shortcuts.

### Group join approval strategies

| Method | Behavior and return value |
| --- | --- |
| `get_group_join_approval_strategies(*, cursor=None, limit=None)` | Lists strategies and returns the next cursor. |
| `create_group_join_approval_strategy(*, group_openids=None, group_ids=None, is_enable=None, expire_at=None, remark=None)` | Creates a strategy and returns its ID, state, and expiry. |
| `update_group_join_approval_strategy(*, strategy_id, is_enable=None, expire_at=None, group_action=None, remark=None)` | Updates state, expiry, remark, or group assignments. |
| `delete_group_join_approval_strategy(*, strategy_id)` | Deletes a strategy. |
| `execute_group_join_approval_strategy(*, strategy_id)` | Executes a strategy immediately. |
| `update_group_join_approval_strategy_whitelist_users(*, strategy_id, op, whitelist_users)` | Adds or removes whitelist users and returns the new whitelist count. |

`group_action` is a `GroupJoinApprovalStrategyGroupAction` dictionary with
`op="add"` or `"del"` and optional `group_openids` or numeric `group_ids`.
Strategy state uses `"on"` or `"off"`.

### Bot information and guilds

| Method | Behavior and return value |
| --- | --- |
| `get_bot_information()` | Returns `BotInformation`: ID, username, avatar, bot flag, and optional union IDs, share URL, and welcome message. |
| `get_bot_guilds(*, before=None, after=None, limit=None)` | Returns guild records with ownership, membership, capacity, description, and join-time data. Use `before` or `after` for pagination. |
| `generate_url_link(*, callback_data=None)` | Returns `URLLinkResponse` with the generated share link in `response["data"]["url"]`. Optional `callback_data` supports up to 32 characters. |

```python
response = await bot.generate_url_link(callback_data="invite")
share_url = response["data"]["url"]
```

### Menus

| Method | Behavior and return value |
| --- | --- |
| `get_global_menu()` | Returns the current menu `version` and optional `menu`. |
| `update_global_menu(*, menu=None)` | Updates the global menu and returns its new `version`. |

A `Menu` contains an `items` list. Each item has a `name` and a `type` of
`"switch"`, `"send_message"`, `"link"`, or `"menu"`, plus the matching
`switch`, `send_message`, `link`, or `sub_menu_items` field. Top-level items may
also choose `align="left"` or `"right"`.

```python
from oibot.api.menu import Menu


menu: Menu = {
    "items": [
        {"name": "Help", "type": "send_message", "send_message": "/help"},
        {"name": "Project", "type": "link", "link": "https://example.com"},
    ]
}
await bot.update_global_menu(menu=menu)
```

### Panels

| Method | Behavior and return value |
| --- | --- |
| `get_panels(*, scope, cursor=None, limit=None)` | Lists panels in `"c2c"`, `"group"`, `"channel"`, or `"dm"` scope. |
| `create_panel(*, scope, panel, target_type=None, user_openids=None, group_openids=None)` | Creates a global or specifically targeted panel and returns `panel_id`. |
| `get_panel(*, panel_id)` | Returns panel details and any user or group targets. |
| `update_panel(*, panel_id, panel)` | Replaces panel content and returns the new `version`. |
| `delete_panel(*, panel_id)` | Deletes a panel. |
| `update_panel_target(*, panel_id, op, user_openids=None, group_openids=None)` | Adds or deletes specific targets with `op="add"` or `"del"`. |

A `Panel` contains `items` and optional `remark` and `version`. Each
`PanelItem` has a `name`, `type="command"` or `"link"`, and optional `desc`,
`only_admin`, and `link` fields. List responses contain `records`,
`next_cursor`, and `is_end`; each record includes scope, target type, timestamps,
and version.

### Access tokens and raw requests

| Method | Behavior |
| --- | --- |
| `get_app_access_token(app_id, app_secret)` | Calls the unauthenticated token endpoint and returns `{"access_token": str, "expires_in": str}`. |
| `get_access_token(app_id, app_secret)` | Returns the cached token or coalesces concurrent refreshes. The cache entry is removed 60 seconds before server-reported expiry. |
| `await bot(method, url, **request_options)` | Executes a request through the shared client. The middleware adds `Authorization: QQBot ...` except on the token endpoint. |

The client is configured with `raise_for_status=True`, so HTTP failures surface
as `aiohttp` exceptions. OiBot does not silently retry ordinary API calls.
Multipart part upload has timeout-bounded retries; WebSocket connection and
session recovery are managed separately by the transport.

### Events

`Event(bot, ctx)` dispatches an incoming payload to a registered structured
subclass. Every event exposes:

| Member | Behavior |
| --- | --- |
| `event.bot` | The owning `OiBot` and its complete API surface. |
| `event.ctx` | Original delivery envelope, including `d`, `id`, `op`, `s`, and `t`. |
| `event["id"]` and other envelope keys | Dictionary-style access to top-level delivery fields. |
| `event.some_payload_field` | Falls back to `ctx["d"]["some_payload_field"]` when no typed property exists. |
| `Event.dispatch(ctx)` | Returns the registered class for `ctx["t"]`, or base `Event` when the type is unknown. |

Import `Event` and `EventType` from `oibot.event`. Structured classes live in
their concrete modules:

| Event | Typed data and convenience operations |
| --- | --- |
| [`C2CMessageCreateEvent`](src/oibot/event/c2c_message_create.py) | `id`, `content`, `timestamp`, `author`, `attachments`, `message_scene`, `message_type`, and optional `ark_data`; supports `reply(str \| Message)` and `chat(...)`. |
| [`GroupAtMessageCreateEvent`](src/oibot/event/group_at_message_create.py) | At-mention message with `group_openid`, author, mentions, attachments, scene, type, optional Ark data, and recursively parsed `msg_elements`; supports `reply(...)` and `chat(...)`. |
| [`GroupMessageCreateEvent`](src/oibot/event/group_message_create.py) | Full group-message counterpart to `GroupAtMessageCreateEvent`, including nested message elements and the same conversation helpers. |
| [`InteractionCreateEvent`](src/oibot/event/interaction_create.py) | Typed interaction `type`, `scene`, `chat_type`, `timestamp`, and resolved data. `button_data` decodes callback JSON, `button_id` exposes its ID, and `acknowledge(code)` acknowledges the result. |
| `C2CInteractionCreateEvent` | Adds `user_openid` plus C2C `reply(...)` and `chat(...)`. |
| `GroupInteractionCreateEvent` | Adds `group_openid` and `group_member_openid` plus group `reply(...)` and `chat(...)`. |
| `GuildInteractionCreateEvent` | Adds `guild_id` and `channel_id` for guild-scene interactions. |
| [`GroupJoinRequestEvent`](src/oibot/event/group_join_request.py) | Request, group and member IDs, source, apply time, optional risk, inviter, verification, and automatic-strategy data; supports `approve()` and `decline(...)`. |
| [`FriendAddEvent`](src/oibot/event/friend_add.py) / [`FriendDelEvent`](src/oibot/event/friend_del.py) | Friend open ID, typed author and timestamp; add events can `reply(Message)`. |
| [`C2CMsgReceiveEvent`](src/oibot/event/c2c_msg_receive.py) / [`C2CMsgRejectEvent`](src/oibot/event/c2c_msg_reject.py) | C2C proactive-message permission state with open ID and timestamp; receive events can `reply(Message)`. |
| [`GroupAddRobotEvent`](src/oibot/event/group_add_robot.py) / [`GroupDelRobotEvent`](src/oibot/event/group_del_robot.py) | Group robot lifecycle, group and operator IDs, and timestamp; add events can `reply(Message)`. |
| [`GroupMemberAddEvent`](src/oibot/event/group_member_add.py) / [`GroupMemberRemoveEvent`](src/oibot/event/group_member_remove.py) | Group and member IDs plus timestamp; both can `reply(Message)`. |
| [`GroupMsgReceiveEvent`](src/oibot/event/group_msg_receive.py) / [`GroupMsgRejectEvent`](src/oibot/event/group_msg_reject.py) | Group proactive-message permission state, operator ID, and timestamp; both expose `reply(Message)`. |

Message-event authors, attachments, mentions, message scenes, Ark payloads, and
nested message elements are immutable dataclasses returned by cached
properties. `ArkData.ark_type` supports `"tuwen"`, `"feed"`, `"miniapp"`, `"map"`,
`"contact_card"`, `"video_share"`, `"music_together"`, and `"picture"` for C2C,
at-mention, and full-group-message events, including nested group message
elements. Interaction payloads use the same pattern. Lifecycle-event
`reply(...)` methods accept a built `Message`, while message and interaction
events additionally accept a plain string.

`EventType` names the wider QQ Bot event vocabulary. Event types without a
registered structured class deliberately remain base `Event` instances, so a
catch-all handler can observe protocol additions without breaking dispatch.

## Troubleshooting

- **A plugin is not loaded:** start the process from the directory containing
  the plugin package, keep `plugins/__init__.py`, do not prefix the module name
  with `_`, and make sure the module contains `@on(...)` or `init(app)`.
- **A handler never runs:** annotate its event parameter, import the concrete
  event class, and enable the matching event or WebSocket intent in the QQ Bot
  configuration.
- **A callback button never arrives over WebSocket:** include
  `Intents.INTERACTION`.
- **An API method has no client session:** call it from a running transport or
  inside `async with OiBot(...)`.
- **A dependency is not resolved:** declare it as a parameter default with
  `Dependency.from_provider(...)` and keep the event annotation on the handler
  or provider.

Keep application credentials in environment variables or a secret manager; do
not commit them to source control. In production, expose Webhook endpoints over
HTTPS, normally through a reverse proxy. Never place the application secret in
the callback URL or its query parameters.
