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
    ↓ page.evaluate()
WA-JS (JavaScript in browser)
    ↓ Internal WhatsApp API
WhatsApp Web
```

## Why WA-JS over DOM selectors?

- Selectors break with every WhatsApp UI update.
- The internal API is significantly more stable.
- Reduces detectable signals from synthetic user events.

## References

- [WA-JS Project](https://github.com/wppconnect-team/wa-js) — Apache 2.0 License
- Full attribution in [NOTICE](https://github.com/CamouChat-Team/camouchat-whatsapp/blob/main/NOTICE)
