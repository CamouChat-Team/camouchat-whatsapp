# Event Architecture

CamouChat-WhatsApp uses a **decorator-based pipeline** for real-time message handling. Each decorator wraps the next in a clean, composable stack. The execution order is fixed:

```
WA-JS bridge fires
    → @on_newMsg (receives raw event, normalizes to MessageModelAPI)
        → @on_storage (persists before handler runs)
            → @on_encrypt (encrypts body + nonce before persist)
                → your handler function
```

---

## `@on_newMsg`

The outermost decorator. Hooks into WA-JS's `chat.new_message` push event.

**Source:** `camouchat_whatsapp.decorator.msg_event_hook`

### Signature

```python
def on_newMsg(
    wapi_session: WapiSession,
    config: RegistryConfig | None = None,
) -> Callable
```

### `RegistryConfig`

Controls which pipeline layers are activated:

```python
from camouchat_whatsapp import RegistryConfig

@dataclass
class RegistryConfig:
    profile: ProfileInfo | None = None  # required for storage or encrypt
    store: bool = True                  # enables @on_storage if profile is set
    encrypt: bool = False               # enables @on_encrypt (requires profile)
```

### Usage

```python
from camouchat_whatsapp import on_newMsg, WapiSession, RegistryConfig

wapi = WapiSession(page=page)
registry = RegistryConfig(profile=profile, store=True, encrypt=False)

@on_newMsg(wapi_session=wapi, config=registry)
async def handle(msg):
    print(f"Received: {msg.body}")

await handle()  # registers handler — must be awaited once to activate
```

### How it works internally

1. `@on_newMsg` wraps your function and applies `@on_storage` / `@on_encrypt` based on `config`.
2. The returned `_register()` coroutine, when awaited, calls `wapi_session.start()` (if not already started) and registers the final handler with `MessageApiManager`.
3. The bridge fires per-message via a poll loop (100ms) reading from `window.__camou_queue__` in Main World — zero `expose_function` race conditions.

> ⚠️ **Must be awaited once.** `@on_newMsg` returns a coroutine factory, not a live handler. Call `await handle()` to activate registration.

---

## `@on_storage`

Persists each incoming message to `SQLAlchemyStorage` **before** your handler runs.

**Source:** `camouchat_whatsapp.decorator.storage_hook`

### Signature

```python
def on_storage(profile: ProfileInfo) -> Callable
```

Internally calls `SQLAlchemyStorage.from_profile(profile)` and lazily starts the writer on first message.

### Usage (standalone — per-handler override)

```python
from camouchat_whatsapp.decorator import on_storage

@on_newMsg(wapi_session=wapi, config=RegistryConfig(profile=profile, store=False))
@on_storage(profile=profile)
async def handle(msg):
    # msg is already in DB before this line runs
    print(f"Saved: {msg.body}")
```

> **Tip:** When `RegistryConfig(store=True)` is set, `@on_storage` is applied **automatically** — no need to stack it manually. Use the manual form only when you want a different profile/backend for a specific handler.

### Storage accessor

`on_storage` exposes the internal `SQLAlchemyStorage` reference via `.get_storage()`:

```python
decorator = on_storage(profile)
storage_ref = decorator.get_storage()
```

---

## `@on_encrypt`

Encrypts `msg.body` (AES-256-GCM) and sets `msg.encryption_nonce` **in-place** before the handler (and storage) sees it.

**Source:** `camouchat_whatsapp.decorator.encrypt_hook`

### Signature

```python
def on_encrypt(profile: ProfileInfo) -> Callable
```

### Pipeline position

`@on_encrypt` is applied **after** `@on_storage` in the decorator stack, so the persisted body is always the ciphertext — never plaintext:

```
message arrives → @on_storage (stores ciphertext) → @on_encrypt → handler
```

### Key management

- Reads key from `profile.encryption["key_file"]` if it exists and `enabled=True`.
- Generates a new random AES-256-GCM key on first run and writes it to `key_file`.
- Caches `MessageEncryptor` per `profile_id` — key IO happens only once per session.

### Usage

```python
from camouchat_whatsapp import RegistryConfig, on_newMsg

registry = RegistryConfig(profile=profile, store=True, encrypt=True)

@on_newMsg(wapi_session=wapi, config=registry)
async def handle(msg):
    # msg.body is base64-encoded ciphertext
    # msg.encryption_nonce is base64-encoded nonce
    print(f"Encrypted body: {msg.body[:20]}...")
```

> ⚠️ **Profile must have `encryption.key_file` set.** If the path is missing or corrupted, a warning is logged and a random ephemeral key is used (not persisted — lost on restart).

### Decryption

Use `Query.get_decrypted_messages_async(key)` to decrypt on retrieval:

```python
from camouchat_whatsapp.storage.queries import Query

query = Query(profile=profile)
plaintext_msgs = await query.get_decrypted_messages_async(key=raw_key_bytes)
```

---

## Full Pipeline Example

```python
from camouchat_whatsapp import on_newMsg, WapiSession, RegistryConfig

wapi = WapiSession(page=page)

# Enables storage + encryption
registry = RegistryConfig(profile=profile, store=True, encrypt=True)

@on_newMsg(wapi_session=wapi, config=registry)
async def handle(msg):
    print(f"[ENCRYPTED] {msg.body[:20]}...")

await handle()  # activate
```

**Execution order for each incoming message:**

```
WA-JS push → normalize to MessageModelAPI
    → @on_encrypt: body → AES-256-GCM ciphertext, nonce set
        → @on_storage: enqueue_insert(msg) to SQLAlchemyStorage
            → handle(msg) called
```
