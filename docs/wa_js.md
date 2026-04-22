# WA-JS Integration

`camouchat-whatsapp` uses the internal WhatsApp Web API via [WA-JS](https://github.com/wppconnect-team/wa-js) rather than brittle DOM selectors. This is the core of how CamouChat achieves reliability and stealth simultaneously.

## Classes

### `WapiSession`
Manages the WA-JS script injection lifecycle on a Playwright `Page`. It handles loading the `WaPP` bridge into the page context and waiting for the WhatsApp Web application to be ready.

### `WapiWrapper`
A high-level wrapper providing typed Python methods over the raw JavaScript API. All message sending, chat reading, and media operations go through this layer.

## Architecture

```
Python (WapiWrapper)
    ↓ page.evaluate()  ← hardened via _evaluate_stealth (0.7.3+)
WA-JS (JavaScript in browser)
    ↓ Internal WhatsApp API
WhatsApp Web
```

### `_evaluate_stealth` (0.7.3+)
All JS executions go through `_evaluate_stealth`, which wraps scripts in a try/catch and returns a structured `{success, result, error}` dict. This prevents unhandled JS rejections from crashing the bridge and gives Python-side callers a typed error signal.

## Why WA-JS over DOM selectors?

- Selectors break with every WhatsApp UI update.
- The internal API is significantly more stable.
- Reduces detectable signals from synthetic user events.

## Group API & ChatStore Sync
Group-level APIs (`group_get_all`, `community_get_subgroups`, etc.) read from **ChatStore** (in-memory React store). During the first **10–30 seconds** after login, the store populates incrementally — calls made too early will encounter `null` skeleton entries and raise:

```
TypeError: g is undefined
```

The smoke test script reports this explicitly. `conn_is_main_ready()` only confirms the WebSocket + WPP bridge are active — it does **not** guarantee ChatStore has finished populating groups. The safest approach is to wait a fixed **10–30s** after login before calling group APIs, or implement a retry loop with backoff.

## Smoke Test Script
A comprehensive smoke test script (`tests/smoke/smoke_script.py`) is provided for validating the full bridge surface — messages, chats, contacts, groups, media, privacy, labels, and newsletters. Run it directly:

```bash
uv run tests/smoke/smoke_script.py           # all tests
uv run tests/smoke/smoke_script.py --list    # list available tests
uv run tests/smoke/smoke_script.py test_conn # prefix match
```

## References

- [WA-JS Project](https://github.com/wppconnect-team/wa-js) — Apache 2.0 License
- Full attribution in [NOTICE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/NOTICE)
