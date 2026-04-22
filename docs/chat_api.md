# Chat API Manager

`ChatApiManager` is the domain layer for all chat-level operations. It wraps the WA-JS bridge (`WapiWrapper`) and exposes both RAM-based reads and humanized DOM navigation.

```python
from camouchat_whatsapp import WapiSession

wapi = WapiSession(page)   # bridge + chat_manager + message_manager wired automatically
await wapi.start()          # injects WA-JS, waits for ready, starts message listener

chat_mgr = wapi.chat_manager
```

---

## RAM Methods

Zero network cost — reads directly from React's in-memory ChatStore.

### `get_chat_by_id(chat_id)`

Fetch full metadata for a single chat.

```python
chat = await chat_mgr.get_chat_by_id("919876543210@c.us")
print(chat.formattedTitle, chat.unreadCount)
```

Returns: `ChatModelAPI`

---

### `get_chat_list(**kwargs)` / `fetch_chats(**kwargs)`

Fetch the sidebar chat list from ChatStore in sidebar order.

| Param | Type | Default | Description |
|---|---|---|---|
| `count` | `int \| None` | `None` | Max chats. `None` = all. |
| `direction` | `str` | `"after"` | `"after"` or `"before"` `anchor_chat_id`. |
| `only_users` | `bool` | `False` | Only 1-on-1 personal chats. |
| `only_groups` | `bool` | `False` | Only group chats. |
| `only_communities` | `bool` | `False` | Only Community parent groups. |
| `only_unread` | `bool` | `False` | Only chats with unread messages. |
| `only_archived` | `bool` | `False` | Only archived chats. |
| `only_newsletter` | `bool` | `False` | Only WhatsApp Channels. |
| `with_labels` | `list \| None` | `None` | Filter by label name/ID (Business accounts). |
| `anchor_chat_id` | `str \| None` | `None` | Paginate from this chat ID. |
| `ignore_group_metadata` | `bool` | `True` | Skip group member fetch (faster). |

```python
# All unread group chats
chats = await chat_mgr.get_chat_list(only_groups=True, only_unread=True)

# First 20 personal chats
chats = await chat_mgr.get_chat_list(count=20, only_users=True)

# Paginate — chats after a known ID
chats = await chat_mgr.get_chat_list(count=20, anchor_chat_id="91XXXX@c.us", direction="after")
```

Returns: `Sequence[ChatModelAPI]`

---

## DOM Methods

Physical browser interaction — uses humanized mouse clicks with `isTrusted=true`.

### `open_chat(chat)`

Navigate the browser to a specific chat using a 3-retry humanized click loop.

**Strategy:**
1. JS `scrollIntoView` — ensures the row exists in the virtualized DOM.
2. Humanized mouse arc to estimated center.
3. JS re-query after arc (React may re-render during travel).
4. Micro-correction + physical `page.mouse.click()` → `isTrusted=true`.
5. WPP verify: checks active chat JID (read-only).
6. Falls back to `wpp.chat.openChatBottom()` after 3 failures (logged as anomaly).

```python
chat = await chat_mgr.get_chat_by_id("919876543210@c.us")
opened = await chat_mgr.open_chat(chat)
# Returns True if chat is now active, False if all retries failed
```

> ⚠️ Newsletter/Channel JIDs (`@newsletter`) are **skipped** — DOM interaction is
> unstable for those. Use WPP API methods directly for channels.

---

## Network Methods

> Use sparingly — these hit WhatsApp's servers and are more detectable.

### `mark_is_read(chat_id)`

Force-mark a chat as read. Sends a network read-receipt to WhatsApp servers.

```python
await chat_mgr.mark_is_read("919876543210@c.us")
```

> Intended for Tier 3 pure-API mode only. Prefer letting the user's natural UI interaction trigger read receipts.
