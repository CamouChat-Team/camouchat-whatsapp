---
name: camouchat-whatsapp
description: >
  Complete agent skill reference for camouchat-whatsapp.
  Covers the full public API surface: session lifecycle, message pipeline,
  storage, event decorators, encryption, and query layer.
  Read this before writing or modifying any code in this repo.
---

# CamouChat WhatsApp — Agent Reference

## Package layout

```
camouchat_whatsapp/
├── api/
│   ├── WapiSession          # top-level session (1 per Page)
│   ├── WapiWrapper          # raw JS bridge (_evaluate_stealth)
│   ├── managers/
│   │   ├── MessageApiManager   # message push pipeline
│   │   └── ChatApiManager      # chat RAM/DOM ops
│   └── models/
│       ├── MessageModelAPI  # normalized message dataclass
│       └── ChatModelAPI     # normalized chat dataclass
├── core/
│   ├── Login                # QR / phone-code auth
│   └── WebSelectorConfig    # CSS selector locators
├── features/
│   ├── InteractionController  # send_api_text, send_text, open_chat
│   └── MediaController        # save_media, add_media
├── decorator/
│   ├── on_newMsg + RegistryConfig  # outermost event hook
│   ├── on_storage                  # auto-persist decorator
│   └── on_encrypt                  # AES-256-GCM encrypt decorator
├── storage/
│   ├── SQLAlchemyStorage    # async batch writer (SQLite/PG/MySQL)
│   └── queries.py → Query   # flexible retrieval layer
```

---

## 1. Session Lifecycle

```python
from camouchat_whatsapp import WapiSession, Login
from camouchat_browser import ProfileManager, BrowserConfig, CamoufoxBrowser
from camouchat_core import Platform

pm = ProfileManager()
profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="work")

config = BrowserConfig.from_dict({"platform": Platform.WHATSAPP, "headless": False})
browser = CamoufoxBrowser(config=config, profile=profile)
page = await browser.get_page()

login = Login(page=page)
await login.login(method=0)          # method=0=QR, method=1=phone code

wapi = WapiSession(page=page)        # singleton per Page
await wapi.start()                   # injects WA-JS, starts push listener
# wapi.bridge          → WapiWrapper
# wapi.message_manager → MessageApiManager
# wapi.chat_manager    → ChatApiManager

await wapi.stop()                    # teardown bridge + clear handlers
```

---

## 2. Event Decorators

### Execution order (innermost first)
```
WA-JS push → @on_encrypt → @on_storage → @on_newMsg → handler(msg)
```

### `@on_newMsg`
```python
from camouchat_whatsapp import on_newMsg, RegistryConfig

# RegistryConfig fields:
#   profile: ProfileInfo | None
#   store: bool = True     # auto-persist if profile set
#   encrypt: bool = False  # AES-256-GCM encrypt body before persist

registry = RegistryConfig(profile=profile, store=True, encrypt=False)

@on_newMsg(wapi_session=wapi, config=registry)
async def handle(msg):          # msg: MessageModelAPI
    print(msg.body)

await handle()   # MUST be awaited once to activate registration
```

### `@on_storage` (manual override)
```python
from camouchat_whatsapp.decorator import on_storage

@on_newMsg(wapi_session=wapi, config=RegistryConfig(profile=profile, store=False))
@on_storage(profile=profile)   # takes ProfileInfo, not storage object
async def handle(msg):
    pass  # msg already persisted before this runs
```

### `@on_encrypt`
Applied automatically when `RegistryConfig(encrypt=True)`.
- Reads AES-256-GCM key from `profile.encryption["key_file"]`.
- Generates + writes key on first run if missing.
- Caches `MessageEncryptor` per `profile_id`.
- Sets `msg.body = base64(ciphertext)`, `msg.encryption_nonce = base64(nonce)`.

> Full decorator docs: `docs/event_arch.md`

---

## 3. Storage

### Constructor (always use `from_profile`)
```python
from camouchat_whatsapp import SQLAlchemyStorage

storage = SQLAlchemyStorage.from_profile(profile)   # resolves dialect from ProfileInfo
await storage.start()   # init_db + create_table + migrate + start_writer
```

### Key methods
| Method | Description |
|---|---|
| `enqueue_insert(msgs, min_insert_time=-1)` | Queue msgs for async batch write. Pass `min_insert_time=N` to override flush interval at runtime. |
| `flush()` | Force immediate write of pending batch. |
| `close_db()` | Graceful shutdown — drains queue, disposes engine. |
| `get_all_messages_async(limit, offset)` | Raw fetch from DB. |
| `get_messages_by_chat(chat_id, limit, offset)` | Filtered fetch. |
| `check_message_if_exists_async(msg_id)` | Dedup check. |

### `db_credentials` dict keys
| Key | Required | Notes |
|---|---|---|
| `storage_type` | No | `"sqlite"` (default), `"postgresql"`, `"mysql"` |
| `database_name` | Yes | SQLite: used as filename |
| `username` | PG/MySQL only | |
| `password` | PG/MySQL only | |
| `host` | PG/MySQL only | default `"localhost"` |
| `port` | PG/MySQL only | 5432 / 3306 |

### `Query` — advanced retrieval
```python
from camouchat_whatsapp.storage.queries import Query   # NOT from top-level __init__

q = Query(profile=profile)
await q.get_all_messages()
await q.get_messages_by_chat(chat_id, limit=50)
await q.search_messages_by_text("hello")
await q.is_msgs_exist(msg_or_list)
await q.total_messages()
await q.get_all_message_type(MessageType.CHAT)
await q.get_all_messages_from_me(fromme=False)
await q.get_messages_between_dates(start, end)
await q.get_distinct_chat_ids()
await q.get_messages_by_ids_async([id1, id2])
await q.delete_messages_by_ids([id1])
await q.get_decrypted_messages_async(key=raw_key_bytes)  # on-the-fly AES decrypt
await q.custom_query("SELECT ...", param)
```

> Full storage docs: `docs/storage.md`

---

## 4. InteractionController

```python
from camouchat_whatsapp import InteractionController

ctrl = InteractionController(page=page, wapi=wapi)

# API send (zero DOM — stealth)
await ctrl.send_api_text(
    chat_id="919876543210@c.us",
    text="Hello @mention",
    quoted_msg_id=msg.id_serialized,    # optional
    mentionList=["919876543210@c.us"],  # optional — must match @mention in text
)

# Humanized DOM send (types via keyboard)
await ctrl.send_text(message=msg, text="reply", quote=True, send=True)

# Navigate to chat (auto-skips @newsletter JIDs)
await ctrl.open_chat(chat=chat_obj)
```

> ⚠️ `mentionList` JIDs must appear as `@number` in `text` — WhatsApp cross-validates.

---

## 5. MessageApiManager (RAM/IndexDB pulls)

```python
mgr = wapi.message_manager

# RAM (zero network)
msgs = await mgr.get_messages("91XXXX@c.us", count=50, direction="before")
msg  = await mgr.get_message_by_id("true_91XXXX@c.us_ABCDEF")
unread = await mgr.get_unread("91XXXX@c.us")

# IndexedDB (disk, survives refresh)
msgs = await mgr.indexdb_get_messages(min_row_id=0, limit=100)

# Media download
result = await mgr.extract_media(message=msg, save_path="/tmp/file.jpg")
# result = {success, type, mimetype, size_bytes, path, used_fallback, error}
```

---

## 6. ChatApiManager

```python
mgr = wapi.chat_manager

chats     = await mgr.get_chat_list()
chat      = await mgr.get_chat_by_id("91XXXX@c.us")
opened    = await mgr.open_chat(chat=chat)
```

> Full chat docs: `docs/chat_api.md`

---

## 7. MediaController

```python
from camouchat_whatsapp import MediaController, MediaType, FileTyped

ctrl = MediaController(page=page, UIConfig=ui, wapi=wapi, profile=profile)

# Download incoming media
path = await ctrl.save_media(message=msg)          # download → profile media dir

# Upload media to chat
file = FileTyped(uri=path, name="f.jpg", mime_type=msg.mimetype)
await ctrl.add_media(mtype=MediaType.IMAGE, file=file, force=True)
```
- `MediaType`: Enum with `IMAGE`, `VIDEO`, `DOCUMENT`
- `FileTyped`: Dataclass containing `uri`, `name`, `mime_type`

---

## 8. Login

```python
from camouchat_whatsapp import Login

login = Login(page=page)
await login.login(method=0)                             # QR
await login.login(method=1, number=919876543210, country="India")  # phone code
already = await login.is_login_successful(timeout=5_000)
```
Failures raise `camouchat_whatsapp.exceptions.LoginError`.

---

## 9. Key rules for code changes

1. **`WapiSession` is a singleton per `Page`** — do not instantiate twice.
2. **`SQLAlchemyStorage` is a singleton per DB URL** — use `from_profile()`, not the constructor directly.
3. **`InteractionController` is a singleton per `Page`** — same pattern.
4. **`await handle()` is required** after `@on_newMsg` — it's a registration coroutine, not the handler itself.
5. **`@on_storage` takes `ProfileInfo`**, not a `SQLAlchemyStorage` instance.
6. **`Query` is NOT exported from top-level** — always import from `camouchat_whatsapp.storage.queries`.
7. **Rate Limiting Patterns** — Rate limiting is currently a manual concern, but an inbuilt limiter will be added in a future version with Monitor&Metrics insertion.
8. **Use `uv run pre-commit run --all-files`** before committing — ruff + ruff-format enforced.

---

## 10. Docs map

| File | Contents |
|---|---|
| `docs/event_arch.md` | `@on_newMsg`, `@on_storage`, `@on_encrypt` pipeline |
| `docs/storage.md` | `SQLAlchemyStorage`, `Query`, dialect config |
| `docs/controllers.md` | `InteractionController`, `MediaController` |
| `docs/msg_api.md` | `MessageApiManager` all methods |
| `docs/chat_api.md` | `ChatApiManager` all methods |
| `docs/core.md` | `Login`, `WebSelectorConfig` |
| `docs/api_models.md` | `MessageModelAPI`, `ChatModelAPI` |
| `docs/wa_js.md` | Bridge architecture, stealth engine |
