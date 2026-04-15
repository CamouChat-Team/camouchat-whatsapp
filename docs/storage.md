# Storage & Filtering

## `SQLAlchemyStorage`
The primary persistence layer for messages and chats. Uses `SQLAlchemy` with `aiosqlite` for fully async, non-blocking database operations.

Supports:
- **SQLite** (default, local-first)
- **MySQL** via `aiomysql`
- **PostgreSQL** via `asyncpg`

```python
from camouchat_whatsapp import SQLAlchemyStorage

storage = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///messages.db")
await storage.init()
await storage.save_message(message_obj)
```

The database URL is automatically configured by `ProfileManager` when creating a profile sandbox.

## `MessageFilter`
A configurable gating layer applied before any message reaches a handler or storage.

Common filter rules:
- `allow_from_me`: Include or exclude messages sent by the bot itself.
- Rate limiting: Cap incoming events per second to prevent processing floods.

```python
from camouchat_whatsapp import MessageFilter

msg_filter = MessageFilter(allow_from_me=False)
passed = msg_filter.check(message=msg)
```

## `on_newMsg` Decorator
Register a callback to be invoked whenever a new message passes all active filters.

```python
from camouchat_whatsapp import on_newMsg

@on_newMsg
async def handle(message):
    print(f"New message from {message.sender}: {message.body}")
```
