# Storage & Filtering

## `SQLAlchemyStorage`
The primary persistence layer for messages and chats. Uses `SQLAlchemy` with `aiosqlite` for fully async, non-blocking database operations.

Supports:
- **SQLite** (default, local-first)
- **MySQL** via `aiomysql`
- **PostgreSQL** via `asyncpg`

```python
import asyncio
from camouchat_whatsapp import SQLAlchemyStorage

queue = asyncio.Queue()
storage = SQLAlchemyStorage(queue=queue, database_url="sqlite+aiosqlite:///messages.db")
await storage.start()  # init_db + create_table + start_writer
await storage.enqueue_insert([message_obj])  # enqueue for async batch write
```

The database URL is automatically configured by `ProfileManager` when creating a profile sandbox.

## `MessageFilter`
A configurable gating layer applied before any message reaches a handler or storage.

Common filter rules:
- `allow_from_me`: Include or exclude messages sent by the bot itself.
- Rate limiting: Cap incoming events per second to prevent processing floods.

```python
from camouchat_whatsapp import MessageFilter

# Rate-limit: max 10 messages per 60-second window
msg_filter = MessageFilter(Max_Messages_Per_Window=10, Window_Seconds=60)
passed = msg_filter.apply(msgs=[msg])  # returns [] if rate-limited, [msg] if delivered
```

## `on_newMsg` Decorator
Register a callback to be invoked whenever a new message passes all active filters.

```python
from camouchat_whatsapp import on_newMsg, WapiSession

wapi = WapiSession(page=page)

@on_newMsg(wapi_session=wapi)
async def handle(msg):
    print(f"New message from {msg.jid_From}: {msg.body}")

await handle()  # registers the handler and starts bridge
```
