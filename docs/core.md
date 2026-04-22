# Core — Login & UI Config

## `Login`

Handles WhatsApp Web authentication. Singleton per `Page` — creating `Login(page=page)` twice returns the same instance.

```python
from camouchat_whatsapp import Login, WebSelectorConfig

ui = WebSelectorConfig(page=page)
login = Login(page=page, ui_config=ui)
success = await login.login(method=0)  # method=0: QR, method=1: phone code
```

### `login(**kwargs)` → `bool`

| kwarg | Type | Default | Description |
|---|---|---|---|
| `method` | `int` | `1` | `0` = QR scan, `1` = phone linking code. |
| `wait_time` | `int` | `180_000` | QR scan timeout in ms (method=0 only). |
| `url` | `str` | `"https://web.whatsapp.com"` | WhatsApp Web URL. |
| `number` | `int` | `None` | Phone number (method=1 only, no `+` or spaces). |
| `country` | `str` | `None` | Country name e.g. `"India"` (method=1 only). |

**QR login** — opens WA Web and waits for user to scan:
```python
success = await login.login(method=0, wait_time=120_000)
```

**Phone code login** — generates a linking code to enter on your phone:
```python
success = await login.login(method=1, number=919876543210, country="India")
# Linking code printed to log: "WhatsApp Login Code: XXXX-XXXX"
```

> The code is logged at `INFO` level. Retrieve it from your logger or `print` intercept.

### `is_login_successful(timeout=10_000)` → `bool`

Poll for chat list visibility — use to verify an existing persistent context is already authenticated without re-running `login()`.

```python
try:
    already_logged_in = await login.is_login_successful(timeout=5_000)
except TimeoutError:
    # Not logged in — run login()
    await login.login(method=0)
```

### Error handling

All failures raise `LoginError`:

```python
from camouchat_whatsapp.exceptions import LoginError

try:
    await login.login(method=1, number=919876543210, country="India")
except LoginError as e:
    print(f"Login failed: {e}")
```

Common causes:
- `"QR login timeout."` — user didn't scan within `wait_time`.
- `"Country 'X' not selectable."` — country name doesn't match WA's list exactly.
- `"Timeout while loading WhatsApp Web"` — network/navigation issue.

---

## `WebSelectorConfig`

Provides typed CSS selector locators for WhatsApp Web UI elements. Created automatically by `Login` if not passed explicitly.

```python
from camouchat_whatsapp import WebSelectorConfig

ui = WebSelectorConfig(page=page)
```

Rarely needed directly — `Login` and `InteractionController` consume it internally. Override only when building custom interaction logic against non-standard WA Web locales or UI versions.

Key locators exposed (all return Playwright `Locator`):

| Method | Element |
|---|---|
| `chat_list()` | Main sidebar chat list — used as the "authenticated" signal |
| `qr_canvas()` | QR code canvas element |
| `link_phone_number_button()` | "Link with phone number" button |
| `country_selector_button()` | Country dropdown in phone login |
| `country_list_items()` | Country list entries |
| `phone_number_input()` | Phone number text field |
| `link_code_container()` | Container holding the `data-link-code` attribute |
