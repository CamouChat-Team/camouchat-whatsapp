# Message API Manager

`MessageApiManager` is the domain layer for all WhatsApp message operations. It sits between `WapiWrapper` (raw stealth bridge) and the user-facing `@on_newMsg` decorator.

```python
from camouchat_whatsapp import WapiSession

wapi = WapiSession(page)   # bridge + chat_manager + message_manager wired automatically
await wapi.start()          # injects WA-JS, waits for ready, starts message listener

msg_mgr = wapi.message_manager
```

---

## Event-Driven (Push Architecture)

Zero poll — WPP fires `chat.new_message` → message ID pushed to an internal queue → RAM fetch → normalized `MessageModelAPI` → your handler.

### `register_handler(callback)`

**Auto-handled — you do not call this directly.**

`wapi.start()` wires the bridge and `@on_newMsg` registers your callback internally. You will see handler registration confirmed in the logs:

```
INFO  MessageApiManager: registered handler 'my_handler' (total=1)
INFO  MessageApiManager: DOM bridge active, ready to receive messages.
```

Use `@on_newMsg` to register handlers — see [storage.md](storage.md) for the full decorator pattern.

### `start_listener` / `_setup_bridge()`

**Auto-handled — called by `wapi.start()`.**

You do not call this directly. `wapi.start()` calls `_setup_bridge()` internally after the WA-JS bridge is ready.

### `stop_bridge()`

**Auto-handled — called by `wapi.stop()`.**

`wapi.stop()` tears down the message bridge, cancels the poll/drain tasks, and clears all handlers. Calling `msg_mgr.stop_bridge()` directly while `wapi` is still alive leaves the WPP connection open with no message pipeline — there's nothing useful left to do with it. Always use:

```python
await wapi.stop()   # stops bridge + message listener + marks session as not ready
```


---

## RAM Methods

Zero network cost — reads directly from React's in-memory MsgStore.

### `get_messages(chat_id, **kwargs)`

Pull messages from React MsgStore.

| Param | Type | Default | Description |
|---|---|---|---|
| `chat_id` | `str` | required | `@c.us` or `@g.us` JID. |
| `count` | `int` | `50` | Messages to fetch. `-1` = all loaded in RAM. |
| `direction` | `str` | `"before"` | `"before"` (newest first) or `"after"`. |
| `only_unread` | `bool` | `False` | Only unread messages. |
| `media` | `str \| None` | `None` | Filter: `"all"`, `"image"`, `"document"`, `"url"`. |
| `include_calls` | `bool` | `False` | Include call log entries. |
| `anchor_msg_id` | `str \| None` | `None` | Paginate from this `id_serialized`. |

```python
# Last 20 messages in a chat
msgs = await msg_mgr.get_messages("919876543210@c.us", count=20)

# Only images, paginated
msgs = await msg_mgr.get_messages("91XXXX@g.us", media="image", count=50)

# All RAM-loaded unread
msgs = await msg_mgr.get_messages("91XXXX@c.us", count=-1, only_unread=True)
```

Returns: `Sequence[MessageModelAPI]`

---

### `get_message_by_id(msg_id)`

Fetch a single message by its full serialized ID.

```python
msg = await msg_mgr.get_message_by_id("true_916398014720@c.us_ABCDEF123")
```

Returns: `MessageModelAPI | None`

---

### `get_unread(chat_id)`

Shorthand for all unread messages in a chat.

```python
unread = await msg_mgr.get_unread("919876543210@c.us")
```

---

## IndexedDB Methods

Reads from browser's local IndexedDB (disk) — slower than RAM but survives page refreshes.

### `indexdb_get_messages(min_row_id, limit=50)`

Sequential scan across **all chats** from a row cursor — useful for bulk export.

```python
# Fetch 100 messages starting from row 0
msgs = await msg_mgr.indexdb_get_messages(min_row_id=0, limit=100)

# Paginate
msgs = await msg_mgr.indexdb_get_messages(min_row_id=100, limit=100)
```

Returns: `list[MessageModelAPI]`

---

## Network Methods

> Use sparingly / only for experimental purpose — these hit WhatsApp's servers.

### `extract_media(message, save_path)`

Download and save media from a `MessageModelAPI` object.

### Making `extract_media` RAM-safe (recommended setup)

`extract_media` calls `wpp.downloadMedia()` internally. Whether this hits the **browser cache (RAM/disk)** or makes an **XMPP/CDN network call** depends entirely on whether the browser has already cached that media.

**To keep it RAM-based and avoid XMPP hits:**

1. **Open the browser in headed mode** (not headless). WhatsApp Web auto-downloads media only when the browser window is visible and active.
2. **Enable auto-download for all media types** in WhatsApp Web settings:
   - Go to `Settings → Storage and data → Media auto-download`
   - Enable: **Photos, Audio, Video, Documents** (recommend enabling all).
3. Once downloaded, the browser LRU cache holds them — `extract_media` serves from cache with near-zero latency.

**How to detect if you're hitting the network:**

Check the log line emitted by `extract_media`:
```
extract_media: [image] 84,231 bytes → /tmp/photo.jpg
```
The underlying `download_media` JS returns `{ b64, isCached, latencyMs }`. If `used_fallback: True` in the result dict **and** you observe `latencyMs >= 300` in your own logs, the call went to the CDN. At that point **stop relying on `extract_media`** and ensure auto-download is configured correctly.

```python
result = await msg_mgr.extract_media(message=msg, save_path="/tmp/photo.jpg")
if result["success"]:
    print(f"Saved {result['size_bytes']} bytes → {result['path']}")
    if result["used_fallback"]:
        print("⚠  CDN fallback used — check auto-download settings or latency")
    else:
        print("✓  Served from browser cache (RAM)")
```

**Returns dict:**
| Key | Description |
|---|---|
| `success` | `bool` — download succeeded |
| `type` | Media type string e.g. `"image"`, `"video"`, `"document"` |
| `mimetype` | MIME type string e.g. `"image/jpeg"` |
| `size_bytes` | File size in bytes (`None` if failed) |
| `path` | Local file path (`None` if failed) |
| `msg_id` | `id_serialized` of the source message |
| `view_once` | Whether original was a view-once message |
| `used_fallback` | `True` = CDN fetch, `False` = served from browser cache |
| `error` | Error string if `success=False`, else `None` |

> View-once messages are excluded by the Signal protocol on linked devices — `directPath` will be absent and `extract_media` returns `success=False`.

### `send_text_message(chat_id, message, options=None)`

> ⛔ **Do not use this directly.** This low-level method is internally patched by `InteractionController`. Calling it directly bypasses mention handling, stealth timing, and quote support.
>
> **Use `InteractionController.send_api_text()` instead** — it wraps this with the full stealth-grade send pipeline including `mentionList` support and proper session context.

```python
# ✗ Avoid:
await msg_mgr.send_text_message("91XXXX@c.us", "Hello")

# ✓ Correct:
from camouchat_whatsapp import InteractionController
await ctrl.send_api_text(chat_id="91XXXX@c.us", text="Hello @mention", mentionList=["91XXXX@c.us"])
```
