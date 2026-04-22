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

### Credential-Based Dialect (0.7.3+)
`SQLAlchemyStorage` now integrates with the new `ProfileManager` structure. The dialect and connection details are resolved from `db_credentials` stored on the profile — no hardcoded URL required:

```python
from camouchat_whatsapp import SQLAlchemyStorage
from camouchat_browser import ProfileManager

pm = ProfileManager()
profile = pm.create_profile(platform=..., profile_id="work")

# Dialect derived automatically from profile.db_credentials
storage = SQLAlchemyStorage.from_profile(profile)
await storage.start()
```

### `db_credentials` Field Reference

Pass this dict directly to `SQLAlchemyStorage(db_credentials=...)` or let `from_profile()` build it automatically.

| Field | Type | Required | Description |
|---|---|---|---|
| `storage_type` | `StorageType` | No | `StorageType.SQLITE` (default), `StorageType.POSTGRESQL`, `StorageType.MYSQL` |
| `database_name` | `str` | Yes | DB name. For SQLite, used as the `.db` filename (falls back to `messages.db`). |
| `username` | `str` | PG / MySQL | DB user. |
| `password` | `str` | PG / MySQL | DB password. |
| `host` | `str` | PG / MySQL | DB host (default: `"localhost"`). |
| `port` | `int` | PG / MySQL | DB port (e.g. `5432` for Postgres, `3306` for MySQL). |

**SQLite example**:
```python
from camouchat_core import StorageType

db_credentials = {
    "storage_type": StorageType.SQLITE,
    "database_name": "camouchat_db",   # used as filename (messages.db fallback if omitted)
    # username, password, host, port are not used by SQLite — safe to omit
}
```

**PostgreSQL example**:
```python
from camouchat_core import StorageType

db_credentials = {
    "storage_type": StorageType.POSTGRESQL,
    "username": "camou",
    "password": "secret",
    "host": "localhost",
    "port": 5432,
    "database_name": "camouchat_db",
}
```

**MySQL example**:
```python
from camouchat_core import StorageType

db_credentials = {
    "storage_type": StorageType.MYSQL,
    "username": "camou",
    "password": "secret",
    "host": "localhost",
    "port": 3306,
    "database_name": "camouchat_db",
}
```

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

## `RegistryConfig` (0.7.3+)
A configuration object passed to `@on_newMsg` that wires a storage backend to the message hook. When a `profile` is provided, all incoming messages are **automatically persisted** — no manual `enqueue_insert` needed.

```python
from camouchat_whatsapp import RegistryConfig, SQLAlchemyStorage

storage = SQLAlchemyStorage.from_profile(profile)
registry = RegistryConfig(profile=profile, storage=storage)
```

## `on_newMsg` Decorator
Register a callback invoked whenever a new message passes all active filters.

```python
from camouchat_whatsapp import on_newMsg, WapiSession, RegistryConfig

wapi = WapiSession(page=page)
registry = RegistryConfig(profile=profile, storage=storage)

@on_newMsg(wapi_session=wapi, registry=registry)
async def handle(msg):
    print(f"New message from {msg.jid_From}: {msg.body}")

await handle()  # registers handler + bridge; auto-saves msgs via registry
```

## `@on_storage` Decorator (0.7.3+)
A nested decorator available inside `@on_newMsg` callbacks for per-handler storage control:

```python
@on_newMsg(wapi_session=wapi, registry=registry)
@on_storage(storage=storage)
async def handle(msg):
    # msg is already persisted before this handler runs
    print(f"Saved & received: {msg.body}")
```

> **Note:** If `profile` is given to `RegistryConfig`, messages are auto-persisted globally. `@on_storage` is for per-handler overrides or a different backend.
