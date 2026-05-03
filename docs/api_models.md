# API Models & Managers

These classes form the data and orchestration layer that sits between raw WA-JS events and the storage/interaction pipeline.

## Models

### `MessageModelAPI`
A structured dataclass representing a message event received from the WA-JS event bridge. Contains sender, content, timestamp, media flags, and reply context.

### `ChatModelAPI`
Represents a WhatsApp chat thread — group or individual. Contains participant metadata, unread counts, and last-message state.

## Managers

### `MessageApiManager`
Processes raw `MessageModelAPI` events. Responsible for:
- Persisting to `SQLAlchemyStorage`
- Dispatching to registered `on_newMsg` handlers

### `ChatApiManager`
Handles the lifecycle of `ChatModelAPI` objects. Provides lookup, caching, and persistence for conversation threads.

## Usage Example

The `MessageApiManager` is instantiated by `WapiSession` internally.

```python
from camouchat_whatsapp import WapiSession, RegistryConfig, on_newMsg
import asyncio

# Attach via WapiSession
wapi = WapiSession(page=page)
await wapi.start()

# Use RegistryConfig for storage and encryption (Recommended)
registry = RegistryConfig(profile=profile, store=True, encrypt=True)

@on_newMsg(wapi, config=registry)
async def my_handler(msg):
    print(f"Handled: {msg.body}")

await my_handler() # Activate registration
```
