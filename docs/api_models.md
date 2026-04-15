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
- Filtering by `MessageFilter` rules
- Persisting to `SQLAlchemyStorage`
- Dispatching to registered `on_newMsg` handlers

### `ChatApiManager`
Handles the lifecycle of `ChatModelAPI` objects. Provides lookup, caching, and persistence for conversation threads.

## Usage Example

The `MessageApiManager` is instantiated by `WapiSession` internally. If you need it standalone:

```python
from camouchat_whatsapp import WapiSession, SQLAlchemyStorage, MessageFilter
import asyncio

queue = asyncio.Queue()
storage = SQLAlchemyStorage(queue=queue, database_url="sqlite+aiosqlite:///messages.db")
msg_filter = MessageFilter(Max_Messages_Per_Window=20, Window_Seconds=60)

# Attach via WapiSession (preferred)
wapi = WapiSession(page=page, storage_obj=storage, filter_obj=msg_filter)
```
