# Controllers

Controllers provide the actionable layer for interacting with WhatsApp. They are built around the `camouchat-core` protocols for type-safe, decoupled integration.

## `Login`
Manages the authentication flow for WhatsApp Web.

- Detects login state (QR code, loading, authenticated).
- Exposes QR code as bytes for rendering or piping into a bot UI.
- Polls until the session is fully authenticated before allowing further operations.

```python
from camouchat_whatsapp import Login, WebSelectorConfig

ui = WebSelectorConfig(page=page)
login = Login(page=page, UIConfig=ui)
await login.login(method=0)  # method=0: auto-handles saved session or QR
```

## `WebSelectorConfig`
A configuration object that defines CSS selectors and timeouts for the WhatsApp Web UI. Allows customizing behavior for different locale versions or future UI changes without touching business logic.

## `InteractionController`
Provides both API-level and humanized browser-level message actions:

- **`send_api_text(chat_id, text, quoted_msg_id=None)`**: Sends a plain-text message via the internal WA-JS API (zero DOM interaction, stealth-native).
- **`send_text(message, text, quote=False, send=True)`**: Types text into the WhatsApp Web input field using humanized keyboard simulation. Optionally triggers a quote bubble and sends.
- **`open_chat(chat)`**: Navigates the browser to a specific chat.

## `MediaController`
Handles media workflows via the WA-JS CDN bridge:

- **`save_media(message)`**: Downloads media from a `MessageModelAPI` object using the local-first WPP CDN bridge and saves it to the profile's media directory. Returns the saved file path or `None`.
- **`add_media(mtype, file, force=False)`**: Uploads a `FileTyped` object to the currently open WhatsApp chat via the file picker automation. `force=True` skips the chat-open check.

```python
from camouchat_whatsapp import MediaController, MediaType, FileTyped

ctrl = MediaController(page=page, UIConfig=ui, wapi=wapi, profile=profile)

# Download and save incoming media
saved_path = await ctrl.save_media(message=msg)

# Re-upload to chat
file_obj = FileTyped(uri=saved_path, name="file.jpg", mime_type=msg.mimetype)
await ctrl.add_media(mtype=MediaType.IMAGE, file=file_obj, force=True)
```
