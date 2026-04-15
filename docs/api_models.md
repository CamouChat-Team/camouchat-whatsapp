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

```python
from camouchat_whatsapp import MessageApiManager, SQLAlchemyStorage, MessageFilter

storage = SQLAlchemyStorage(database_url="sqlite+aiosqlite:///messages.db")
msg_filter = MessageFilter(allow_from_me=False)

manager = MessageApiManager(storage=storage, msg_filter=msg_filter)
```
