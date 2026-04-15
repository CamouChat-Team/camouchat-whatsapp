# Controllers

Controllers provide the actionable layer for interacting with WhatsApp. They are built around the `camouchat-core` protocols for type-safe, decoupled integration.

## `Login`
Manages the authentication flow for WhatsApp Web.

- Detects login state (QR code, loading, authenticated).
- Exposes QR code as bytes for rendering or piping into a bot UI.
- Polls until the session is fully authenticated before allowing further operations.

```python
from camouchat_whatsapp import Login

login = Login(page=page, config=web_ui_config)
await login.wait_for_login()
```

## `WebSelectorConfig`
A configuration object that defines CSS selectors and timeouts for the WhatsApp Web UI. Allows customizing behavior for different locale versions or future UI changes without touching business logic.

## `InteractionController`
Provides humanized high-level actions:

- **`send_message(chat_id, text)`**: Sends a plain text message.
- **`reply_message(chat_id, message_id, text)`**: Sends a quoted reply.
- **`send_mention(chat_id, text, participants)`**: Sends a message with `@mentions`.
- **`send_link_preview(chat_id, url, text)`**: Sends a message with a rich link preview.

All methods introduce natural timing delays to mimic human behavior.

## `MediaController`
Handles media workflows:

- **`download_media(message)`**: Downloads media from a message using WA-JS's internal CDN bridge (stealthy, no direct CDN calls).
- **`save_media(media_bytes, media_type, profile)`**: Persists downloaded media to the profile's media directory.
- **`MediaType`** / **`FileTyped`**: Enums for classifying media category and buffer format.

```python
from camouchat_whatsapp import MediaController, MediaType

ctrl = MediaController(page=page, profile=profile)
media = await ctrl.download_media(message=msg)
await ctrl.save_media(media, MediaType.IMAGE, profile=profile)
```
