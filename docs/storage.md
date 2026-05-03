# Storage


## `SQLAlchemyStorage`
The primary persistence layer for messages and chats. Uses `SQLAlchemy` with `aiosqlite` for fully async, non-blocking database operations.

Supports:
- **SQLite** (default, local-first)
- **MySQL** via `aiomysql`
- **PostgreSQL** via `asyncpg`

```python
from camouchat_whatsapp import SQLAlchemyStorage
from camouchat_browser import ProfileManager

pm = ProfileManager()
profile = pm.create_profile(platform=..., profile_id="work")

storage = SQLAlchemyStorage.from_profile(profile)
await storage.start()  # init_db + create_table + start_writer
await storage.enqueue_insert([message_obj])  # enqueue for async batch write

# 0.7.3+: Manual flush and runtime interval control
await storage.flush()  # immediate batch write
await storage.enqueue_insert(message_obj, min_insert_time=5.0)  # override flush interval to 5s
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


## Decorator Pipeline

The `RegistryConfig`, `@on_newMsg`, `@on_storage`, and `@on_encrypt` decorators form the real-time ingestion pipeline. See **[event_arch.md](event_arch.md)** for full documentation.

## `Query` (Advanced Retrieval)
The `Query` class provides high-level, flexible methods for fetching and searching messages without writing raw SQL.

```python
from camouchat_whatsapp.storage.queries import Query

query = Query(profile=profile)

# Retrieval
all_msgs = await query.get_all_messages()
chat_msgs = await query.get_messages_by_chat(chat_id="...", limit=50)

# Search
search_results = await query.search_messages_by_text("hello")

# Checks & Meta
exists = await query.is_msgs_exist(msg_obj)
total = await query.total_messages()

# Decryption on-the-fly
decrypted_msgs = await query.get_decrypted_messages_async(key=my_aes_key)
```
