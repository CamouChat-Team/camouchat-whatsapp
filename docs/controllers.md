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

- **`send_api_text(chat_id, text, quoted_msg_id=None, mentionList=None)`**: Sends a plain-text message via the internal WA-JS API (zero DOM interaction, stealth-native).
  - `mentionList=["919876543210@c.us"]`: Tag contacts in the message. Stochastic key-typing telemetry runs automatically (~60% of calls).

  > ⚠️ **mentionList must be exact.** Every JID in `mentionList` must also appear as `@number` in the message `text`. WhatsApp's backend cross-validates the mention payload against the message body — a mismatch (e.g. mentioning a JID not present in the text, or vice versa) creates a suspicious signal that can flag the session. Always keep `mentionList` and `@mentions` in the text in sync.

- **`send_text(message, text, quote=False, send=True)`**: Types text into the WhatsApp Web input field using humanized keyboard simulation. Optionally triggers a quote bubble and sends.
- **`open_chat(chat)`**: Navigates the browser to a specific chat. Automatically detects and skips newsletter/channel JIDs (`"@newsletter"`) with fallback reliability.

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
