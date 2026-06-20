import asyncio
import base64
import inspect
import json
import os
import secrets
import time
from dataclasses import dataclass
from enum import StrEnum
from logging import Logger, LoggerAdapter
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from camouchat_whatsapp.exceptions import WAJSError
from camouchat_whatsapp.logger import w_logger

from .wajs_scripts import WAJS_Scripts

# ── Listener event model ────────────────────────────────────────────────────


class EventName(StrEnum):
    """
    Stable semantic keys for all registered WA-JS listeners.

    These names never change — they are the internal API contract.
    The actual WA-JS event string lives inside ``ListenerEntry.event``
    and can be updated in one place without touching any call sites.
    """

    MESSAGE_EVENT = "message"
    ACK_EVENT = "ack"
    REVOKE_EVENT = "revoke"
    EDIT_EVENT = "edit"


# ── Circular-safe JSON extractor (for full raw payload dumps) ─────────────────
_CIRCULAR_SAFE_EXTRACTOR: str = (
    "JSON.parse(JSON.stringify(msg, (() => {"
    "const s = new WeakSet();"
    "return (k, v) => { if (typeof v === 'object' && v !== null) {"
    "if (s.has(v)) return '[Circular]'; s.add(v); } return v; };"
    "})()))"
)


@dataclass(frozen=True)
class WaJSEvent:
    """
    Immutable bundle of a stable ``EventName`` key, the raw WA-JS event
    string, and the JS extractor expression.

    This is the ONLY place WA-JS event strings are written.
    To rename a WA-JS event after a WhatsApp update, change it here — no
    other file needs to be touched.

    Usage::

        await wapi.bridge.register_listener(WaJSEvents.REVOKE)
    """

    event_name: EventName
    event: str
    extractor: str


class WaJSEvents:
    """
    Registry of all supported WA-JS listener events.

    Each class-level attribute is a ``WaJSEvent`` bundle. Pass any of these
    directly to ``register_listener()`` — no need to supply the raw WA-JS
    event string or extractor manually::

        await wapi.bridge.register_listener(WaJSEvents.ACK)
        await wapi.bridge.register_listener(WaJSEvents.REVOKE)
        await wapi.bridge.register_listener(WaJSEvents.EDIT)

    If WA-JS renames an event (e.g. after a WhatsApp update), update only
    the ``event`` string here — all call sites automatically pick up the change.
    """

    MESSAGE: WaJSEvent = WaJSEvent(
        event_name=EventName.MESSAGE_EVENT,
        event="chat.new_message",
        extractor=_CIRCULAR_SAFE_EXTRACTOR,
    )
    ACK: WaJSEvent = WaJSEvent(
        event_name=EventName.ACK_EVENT,
        event="chat.msg_ack_change",
        extractor="{ ack: msg?.ack, chat: String(msg?.chat || ''), ids_count: msg?.ids?.length }",
    )
    REVOKE: WaJSEvent = WaJSEvent(
        event_name=EventName.REVOKE_EVENT,
        event="chat.msg_revoke",
        extractor=_CIRCULAR_SAFE_EXTRACTOR,
    )
    EDIT: WaJSEvent = WaJSEvent(
        event_name=EventName.EDIT_EVENT,
        event="chat.msg_edited",
        extractor=_CIRCULAR_SAFE_EXTRACTOR,
    )


@dataclass
class ListenerEntry:
    """
    Holds the full registration metadata for one wpp.on listener.

    Attributes:
        name:         Stable semantic key (``EventName`` enum member).
        event:        Raw WA-JS event string, e.g. ``"chat.new_message"``.
                      This is the only place the WA-JS string lives;
                      update here if WhatsApp renames the event.
        js_extractor: JS expression evaluated inside the listener callback.
                      Has access to ``msg`` (first callback argument).
                      Result is stored as the ``data`` field in the queue.
        guard_key:    Per-listener DOM flag key (non-enumerable, prevents
                      double registration on page re-attach).
    """

    name: EventName
    event: str
    js_extractor: str
    guard_key: str = ""


class WapiWrapper:
    """
    The Bridge connecting Playwright (Python) to wa-js (Browser).
    """

    def _save_bytes(self, path: str, data: bytes) -> None:
        """Sync helper for writing bytes to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def _read_text(self, path: str) -> str:
        """Sync helper for reading text from disk."""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def __init__(self, page: Page, log: LoggerAdapter | Logger | None = None):
        self.page = page
        self.log = log or w_logger
        self._wpp_key: str = ""  # per-session rotated WPP handle key
        self._bridge_key: str | None = None
        self._queue_key: str | None = None
        self._bridge_active: bool = False

        # ── ListenerRegistry state ───────────────────────────────────────────
        # Maps EventName → ListenerEntry for each registered wpp.on listener.
        # Callers always reference EventName keys — the raw WA-JS event string
        # is an implementation detail inside ListenerEntry.event.
        # The shared queue is identified by self._queue_key (same field reused).
        self._listener_registry: dict[EventName, ListenerEntry] = {}

        # Per-session token used to authenticate all writes into the stealth
        # queue. Only our JS code knows this value; WA integrity code cannot
        # predict it. Generated lazily alongside _bridge_key.
        self._session_token: str = ""

    async def _evaluate_stealth(self, js_fragment: str) -> Any:
        """
        Executes a JS fragment in the real Main World via a script-tag injection bridge.

        Why NOT `mw:` async IIFE:
            Camoufox's `mw:` runs code in Main World, but does NOT await Promises
            back through CDP — async IIFE results serialize as {} (unresolved Promise).
            Script tags always execute in Main World AND can dispatch their async result
            back via CustomEvent, which the Isolated World Promise catches cleanly.

        Flow:
            1. Isolated World sets up a one-shot CustomEvent listener (per-call secrets ID).
            2. A <script> tag is injected into the DOM — executes async IIFE in Main World.
            3. Main World resolves the WPP call and dispatches {success, data, error}.
            4. Isolated World catches it, resolves the outer Promise back to Python.

        Args:
            js_fragment: Raw JS expression. `const wpp` is injected automatically.

        Returns:
            Deserialized Python object (whatever the fragment evaluates to).

        Raises:
            WAJSError: On JS error, missing WPP handle, or 30s timeout.
        """
        if not self._wpp_key:
            raise WAJSError("WPP handle key not set — was wait_for_ready() called?")

        frame = inspect.currentframe()
        caller = frame.f_back.f_code.co_name if frame and frame.f_back else "unknown"

        req_id = f"_cr{secrets.token_hex(5)}"  # per-call, no predictable prefix
        wpp_key = self._wpp_key

        bridge_script = f"""() => {{
            return new Promise((resolve) => {{
                let resolved = false;

                // Isolated World: one-shot listener for the Main World result
                window.addEventListener('{req_id}', (e) => {{
                    resolved = true;
                    resolve(e.detail);
                }}, {{ once: true }});

                // 30s timeout guard
                setTimeout(() => {{
                    if (!resolved) resolve({{
                        success: false, data: null,
                        error: 'Bridge timeout (30s) — Main World did not respond.'
                    }});
                }}, 30000);

                // Inject <script> tag — always runs in Main World regardless of eval context
                const script = document.createElement('script');
                const nonceEl = document.querySelector('script[nonce]');
                if (nonceEl) script.setAttribute('nonce', nonceEl.nonce);

                script.textContent = `
                    (async () => {{
                        try {{
                            const wpp = Object.getOwnPropertyDescriptor(window, '{wpp_key}')?.value;
                            if (!wpp) {{
                                window.dispatchEvent(new CustomEvent('{req_id}', {{
                                    detail: {{ success: false, data: null, error: 'WPP handle missing ({wpp_key}).' }}
                                }}));
                                return;
                            }}
                            const res = await ({js_fragment});
                            window.dispatchEvent(new CustomEvent('{req_id}', {{
                                detail: {{ success: true, data: res, error: null }}
                            }}));
                        }} catch (err) {{
                            window.dispatchEvent(new CustomEvent('{req_id}', {{
                                detail: {{ success: false, data: null, error: err.toString() }}
                            }}));
                        }}
                    }})();
                `;
                document.documentElement.appendChild(script);
                script.remove();
            }});
        }}"""

        raw = await self.page.evaluate(bridge_script)

        if not isinstance(raw, dict):
            raise WAJSError(f"[{caller}] _evaluate_stealth: unexpected response: {raw!r}")
        if not raw.get("success"):
            err = raw.get("error", "Unknown JS error")
            self.log.error(f"[{caller}] WA-JS error: {err}")
            raise WAJSError(f"[{caller}] {err}")

        return raw.get("data")

    # ─────────────────────────────────────────────
    # 1. SETUP & LIFECYCLE
    # ─────────────────────────────────────────────

    async def wait_for_ready(self, timeout_ms: float = 60000) -> bool:
        """
        Injects wppconnect-wa.js into the Main World, waits for WPP to init,
        then performs the 'Smash & Grab':
          - Generates a per-session randomized key (e.g. `__react_devtools_a3f9c1b2`).
          - Hides WPP under that non-enumerable, non-configurable, non-writable key.
          - Deletes `window.WPP` to evade Meta's integrity.js scanners.
        """
        js_path = str(Path(__file__).parent / "wppconnect-wa.js")
        js_code = await asyncio.to_thread(self._read_text, js_path)

        self.log.info("Injecting WPP engine and waiting for Webpack integration...")

        start = time.time()
        injected = False

        while (time.time() - start) * 1000 < timeout_ms:
            try:
                if not injected:
                    has_global = await self.page.evaluate("mw:typeof window.WPP !== 'undefined'")
                    if not has_global:
                        try:
                            await self.page.evaluate(
                                """([jsCode]) => {
                                    const script = document.createElement('script');
                                    const nonceEl = document.querySelector('script[nonce]');
                                    if (nonceEl) script.setAttribute('nonce', nonceEl.nonce);
                                    script.textContent = jsCode;
                                    document.documentElement.appendChild(script);
                                    script.remove();
                                }""",
                                [js_code],
                            )
                            injected = True
                        except Exception as e:
                            if "Execution context was destroyed" not in str(e):
                                self.log.warning(f"DOM injection failed: {e}")
                    else:
                        injected = True

                if injected:
                    is_ready = await self.page.evaluate(
                        "mw:window.WPP && window.WPP.isReady === true"
                    )
                    if is_ready:
                        wpp_key = f"__react_devtools_{secrets.token_hex(4)}"

                        # override properties-----------
                        await self.page.evaluate(f"""mw:(() => {{
                            Object.defineProperty(window, '{wpp_key}', {{
                                value: window.WPP,
                                enumerable: false,
                                configurable: false,
                                writable: false
                            }});
                            delete window.WPP;
                        }})()""")

                        # Verify WPP is deleted + handle is live.
                        sweep_ok = await self.page.evaluate(f"""mw:(() => {{
                            const wppGone = !Object.keys(window).includes('WPP');
                            const desc = Object.getOwnPropertyDescriptor(window, '{wpp_key}');
                            const handleOk = desc && typeof desc.value === 'object' && desc.value !== null;
                            return wppGone && !!handleOk;
                        }})()""")

                        if not sweep_ok:
                            raise WAJSError(
                                "Smash & Grab verification FAILED — "
                                "WPP still enumerable or handle is null."
                            )

                        self._wpp_key = wpp_key
                        self.log.info(
                            "WPP engine integrated! window.WPP annihilated → stealth handle locked."
                        )
                        self.log.debug(
                            f"wpp_key='{wpp_key[:20]}...' (enumerable=false, configurable=false, writable=false)."
                        )
                        return True

            except Exception as e:
                if "Execution context was destroyed" in str(e):
                    injected = False
                else:
                    self.log.warning(f"Error evaluating WPP status: {e}")

            await asyncio.sleep(0.5)

        self.log.error("wa-js failed to initialize before timeout.")
        raise WAJSError(f"WPP Initialization Timeout (waited {timeout_ms / 1000:.0f}s)")

    async def is_authenticated(self) -> bool:
        """Check if WhatsApp session is currently authenticated."""
        return await self._evaluate_stealth(WAJS_Scripts.is_authenticated())

    # ──────────────────────────────────────────────────────────────
    # 2. PUSH ARCHITECTURE — STEALTH DOM BRIDGE  (ListenerRegistry)
    # ──────────────────────────────────────────────────────────────

    def _get_bridge_key(self) -> str:
        """
        Returns (and lazily generates) a per-session random base key.
        All queue / guard names are derived from this single random token
        so they cannot be hardcoded into WA's blacklist.

        Also lazily initialises ``_session_token`` on first call, so both
        values are always in sync with the same session lifecycle.
        """
        if not self._bridge_key:
            self._bridge_key = f"_c{secrets.token_hex(6)}"
            self._session_token = secrets.token_hex(16)
        return self._bridge_key

    async def _ensure_stealth_queue(self) -> str:
        """
        Idempotent — creates the ONE shared stealth queue on the first call.

        The queue is a **closure-based token-gated object** (not a plain array)
        stored at a non-enumerable, non-configurable, non-writable window key.

        Security model:
            - ``_data`` lives inside a JS closure — unreachable from any
              external JS, including WA's integrity scanners.
            - Every write (``push``) requires the per-session ``_session_token``
              embedded at creation time. WA code cannot predict this token.
            - ``drain`` / ``drainFor`` / ``clear`` are also token-gated.
            - The window property itself is non-writable → cannot be replaced.
            - Non-enumerable → invisible to ``Object.keys`` / ``for..in``.

        Returns:
            The ``queue_key`` (e.g. ``'__cq_c203a2bd9fdb1'``).
        """
        if self._queue_key:
            return self._queue_key  # already created this session

        bridge_key = self._get_bridge_key()
        queue_key = f"__cq{bridge_key}"
        tok = self._session_token  # per-session secret, never leaves Python/our JS

        await self.page.evaluate(f"""mw:(() => {{
            if (Object.getOwnPropertyDescriptor(window, '{queue_key}')) return;

            // Closure: _data is completely unreachable from outside this IIFE.
            const _data = [];
            const _tok  = '{tok}';

            const _q = Object.create(null);

            // push(item, token) — silently drops if token mismatches.
            Object.defineProperty(_q, 'push', {{
                value: function(item, t) {{
                    if (t === _tok && item != null) _data.push(item);
                }},
                writable: false, enumerable: false, configurable: false,
            }});

            // drain(token) — atomically empties and returns all items.
            Object.defineProperty(_q, 'drain', {{
                value: function(t) {{
                    if (t !== _tok) return [];
                    return _data.splice(0);
                }},
                writable: false, enumerable: false, configurable: false,
            }});

            // drainFor(event, token) — splices only matching-event items.
            Object.defineProperty(_q, 'drainFor', {{
                value: function(ev, t) {{
                    if (t !== _tok) return [];
                    const out = [];
                    let i = _data.length;
                    while (i--) {{
                        if (_data[i].event === ev) {{
                            out.push(_data.splice(i, 1)[0].data);
                        }}
                    }}
                    return out.reverse();
                }},
                writable: false, enumerable: false, configurable: false,
            }});

            // clear(token) — wipes all items (used at teardown).
            Object.defineProperty(_q, 'clear', {{
                value: function(t) {{
                    if (t === _tok) _data.splice(0);
                }},
                writable: false, enumerable: false, configurable: false,
            }});

            // Attach the queue to window — non-writable, so it cannot be
            // replaced by WA code even if they discover the key name.
            Object.defineProperty(window, '{queue_key}', {{
                value: _q,
                writable: false,
                enumerable: false,
                configurable: false,
            }});
        }})()""")

        self._queue_key = queue_key
        self.log.debug(f"ListenerRegistry: token-gated stealth queue created → '{queue_key}'")
        return queue_key

    async def register_listener(
        self,
        wa_event: "WaJSEvent | None" = None,
        *,
        event_name: "EventName | None" = None,
        event: str | None = None,
        js_extractor: str | None = None,
    ) -> None:
        """
        Register a ``wpp.on(event, handler)`` listener that pushes structured
        events into the ONE shared stealth queue.

        All registered listeners funnel into a single ``window[queue_key]`` array
        as ``{event, data}`` objects. Each listener is keyed by a stable
        ``EventName`` enum member — the raw WA-JS event string lives only inside
        ``ListenerEntry.event`` and can be updated without touching call sites.

        Design constraints:
            - Queue is created once (non-configurable, non-enumerable).
            - Each event gets its OWN guard flag — prevents double registration
              on page re-attach / hot-reload without a full teardown.
            - ``js_extractor`` is a JS expression evaluated inside the
              listener callback. It has access to the first argument named
              ``msg``. The result is stored as the ``data`` field.
            - ``{queue_key}`` and ``{wpp_key}`` are Python-templated before
              eval — they are NOT user-controllable.

        Args:
            event_name:   Stable semantic key from ``EventName`` enum.
            event:        Raw WA-JS event string, e.g. ``'chat.new_message'``.
                          This is the only place the WA-JS string is written;
                          update here if WhatsApp renames the event.
            js_extractor: JS expression returning the payload to store, e.g.
                          ``"msg?.id?._serialized"`` or ``"msg"``.

        Example::

            await wrapper.register_listener(
                event_name=EventName.ACK_EVENT,
                event="chat.msg_ack_change",
                js_extractor="msg?.id?._serialized",
            )
        """
        # ── Resolve args: accept WaJSEvent bundle OR individual params ─────────
        if wa_event is not None:
            event_name = wa_event.event_name
            event = wa_event.event
            js_extractor = wa_event.extractor
        elif event_name is None or event is None or js_extractor is None:
            raise ValueError(
                "register_listener: supply either a WaJSEvent bundle (first positional arg) "
                "or all three keyword args: event_name, event, js_extractor."
            )

        if not self._wpp_key:
            raise WAJSError(
                "register_listener: WPP handle key not set — call wait_for_ready() first."
            )

        if event_name in self._listener_registry:
            self.log.debug(f"register_listener: '{event_name}' already registered, skipping.")
            return

        queue_key = await self._ensure_stealth_queue()
        wpp_key = self._wpp_key
        tok = self._session_token  # embedded in JS — authenticates push calls

        # Derive a per-event guard key from the bridge base + event slug.
        safe_event_slug = event.replace(".", "_").replace("-", "_")[:32]
        guard_key = f"__cg{self._get_bridge_key()}_{safe_event_slug}"

        # Create per-listener guard flag (non-enumerable).
        await self.page.evaluate(f"""mw:(() => {{
            if (Object.getOwnPropertyDescriptor(window, '{guard_key}')) return;
            Object.defineProperty(window, '{guard_key}', {{
                value: false,
                writable: true,
                enumerable: false,
                configurable: false,
            }});
        }})()""")

        # Register the wpp.on listener in Main World.
        await self.page.evaluate(f"""mw:(async () => {{
            const wpp = Object.getOwnPropertyDescriptor(window, '{wpp_key}')?.value;
            if (!wpp) {{
                console.warn('CamouBridge [register_listener]: WPP handle missing at key {wpp_key}.');
                return;
            }}
            if (window['{guard_key}']) return;  // already registered for this event

            wpp.on('{event}', (msg) => {{
                try {{
                    const data = {js_extractor};
                    if (data !== undefined && data !== null) {{
                        // Token authenticates this write — WA code cannot
                        // predict the per-session token and will be silently
                        // rejected by the queue's token-gated push method.
                        window['{queue_key}'].push({{ event: '{event}', data: data }}, '{tok}');
                    }}
                }} catch (e) {{
                    console.warn('CamouBridge [{event}] extractor error:', e);
                }}
            }});

            window['{guard_key}'] = true;
        }})()""")

        self._listener_registry[event_name] = ListenerEntry(
            name=event_name,
            event=event,
            js_extractor=js_extractor,
            guard_key=guard_key,
        )
        self.log.info(
            f"ListenerRegistry: registered EventName.{event_name!r} "
            f"→ event='{event}' guard='{guard_key}' queue='{queue_key}'"
        )

    async def drain_queue(self) -> list[dict[str, Any]]:
        """
        Atomically drains the shared stealth queue in ONE JS round-trip.

        Calls the token-gated ``drain(token)`` method on the closure-based
        queue object. The token is the per-session secret embedded at queue
        creation time — only our code can call this successfully.

        Returns:
            ``list[dict]`` — each item is ``{"event": str, "data": Any}``.
            Returns ``[]`` if the queue is empty, the registry is empty,
            or an error occurs.

        Example output::

            [
                {"event": "chat.new_message",    "data": "true_91..._ABCD"},
                {"event": "chat.msg_ack_change", "data": "true_91..._EFGH"},
            ]
        """
        if not self._queue_key or not self._listener_registry:
            return []
        try:
            qk = self._queue_key
            tok = self._session_token
            raw: list[dict[str, Any]] = await self.page.evaluate(
                f"mw:(() => {{ const q = window['{qk}']; return q ? q.drain('{tok}') : []; }})()"
            )
            return raw or []
        except Exception as exc:
            self.log.debug(f"drain_queue: suppressed error — {exc}")
            return []

    async def teardown_all_listeners(self) -> list[dict[str, Any]]:
        """
        Full registry teardown — flushes remaining queue data, resets ALL
        per-listener guard flags, and clears the shared stealth queue.

        The queue is drained BEFORE the wipe so no in-flight events are lost.
        The returned list gives callers (e.g. ``stop_bridge``) a chance to
        process or log any data that arrived between the last poll and shutdown.

        Call this before re-attaching listeners after a page reload so that
        :meth:`register_listener` can re-register ``wpp.on`` handlers
        cleanly (guards default back to ``false``).

        Note:
            Because queue and guard properties are ``configurable: false``,
            they cannot be deleted. We reset them to their initial values:
            queue → ``[]``, guards → ``false``.

        Returns:
            ``list[dict]`` — all ``{event, data}`` items remaining in the
            shared queue at teardown time. Empty list if nothing was pending.
        """
        if not self._listener_registry and not self._queue_key:
            return []  # nothing to tear down

        # ── Step 1: flush remaining items before the wipe ────────────────────
        flushed = await self.drain_queue()
        if flushed:
            self.log.info(
                f"teardown_all_listeners: flushed {len(flushed)} pending item(s) "
                "from queue before wipe — pass to caller for processing."
            )

        # ── Step 2: reset all guard flags + wipe queue in one mw: call ───────
        guard_resets = "\n".join(
            f"    if (typeof window['{entry.guard_key}'] !== 'undefined') "
            f"window['{entry.guard_key}'] = false;"
            for entry in self._listener_registry.values()
        )

        qk = self._queue_key or ""
        tok = self._session_token
        clear_queue = f"    if (window['{qk}']) window['{qk}'].clear('{tok}');" if qk else ""

        await self.page.evaluate(f"""mw:(() => {{
{guard_resets}
{clear_queue}
        }})()""")

        events_torn = [str(k) for k in self._listener_registry]
        self._listener_registry.clear()
        self._bridge_active = False
        self._bridge_key = None
        self._queue_key = None

        self.log.debug(f"ListenerRegistry: all listeners torn down. Events cleared: {events_torn}")
        return flushed

    # ── Backward-compatible shims ────────────────────────────────────────────

    async def setup_message_bridge(self) -> None:
        """
        Backward-compatible entry point — sets up the ``chat.new_message``
        listener via the new :meth:`register_listener` API.

        Stealth: the shared queue and per-listener guard are defined with
        ``enumerable=false, configurable=false`` so they are invisible to
        ``Object.keys(window)``, ``for..in`` enumeration, and WA integrity scans.
        """
        if self._bridge_active:
            self.log.warning("setup_message_bridge: bridge already active, skipping re-register.")
            return

        await self.register_listener(
            event_name=EventName.MESSAGE_EVENT,
            event="chat.new_message",
            js_extractor="msg && msg.id && msg.id._serialized ? msg.id._serialized : null",
        )

        self._bridge_active = True
        self.log.info(
            f"Stealth DOM Bridge active via ListenerRegistry. "
            f"wpp_key='{self._wpp_key}' queue='{self._queue_key}' "
            "(hidden, non-enumerable) | Mode: mw: poll"
        )

    async def drain_queue_for(self, event_name: EventName) -> list[Any]:
        """
        JS-side splice-filter drain — extracts ONLY items for the given
        ``EventName`` from the shared stealth queue, leaving all other
        events untouched in the queue.

        Unlike :meth:`drain_queue` (which atomically swaps the entire queue),
        this method performs a targeted filter-and-remove in a single JS
        round-trip:

        .. code-block:: javascript

            const q   = window[key];
            const out = q.filter(i => i.event === targetEvent);
            window[key] = q.filter(i => i.event !== targetEvent);
            return out.map(i => i.data);

        Because the JS engine is single-threaded there is no race between
        reading and re-assigning the queue.

        Args:
            event_name: ``EventName`` enum member identifying the listener.

        Returns:
            Flat ``list`` of ``data`` values (whatever ``js_extractor``
            produced) for the given event. Returns ``[]`` if none pending,
            the bridge is inactive, or the event is not registered.
        """
        if not self._queue_key:
            return []

        entry = self._listener_registry.get(event_name)
        if entry is None:
            self.log.warning(
                f"drain_queue_for: EventName.{event_name!r} not in registry — "
                "was register_listener called?"
            )
            return []

        qk = self._queue_key
        wa_event = entry.event  # raw WA-JS string — only looked up here
        tok = self._session_token

        try:
            data_list: list[Any] = await self.page.evaluate(
                f"mw:(() => {{"
                f"  const q = window['{qk}'];"
                f"  return q ? q.drainFor('{wa_event}', '{tok}') : [];"
                f"}})()"
            )
            return data_list or []
        except Exception as exc:
            self.log.debug(f"drain_queue_for({event_name!r}): suppressed error — {exc}")
            return []

    async def poll_message_queue(self) -> list:
        """
        Backward-compatible shim — returns ONLY the ``data`` fields for
        ``chat.new_message`` events using a JS-side splice-filter that
        leaves all other events untouched in the shared queue.

        Called by ``MessageApiManager._poll_loop`` every 100 ms.
        New callers should use :meth:`drain_queue_for` directly.
        """
        if not self._bridge_active:
            return []
        return await self.drain_queue_for(EventName.MESSAGE_EVENT)

    async def teardown_message_bridge(self) -> list[dict[str, Any]]:
        """
        Backward-compatible shim — delegates to :meth:`teardown_all_listeners`.

        Returns:
            Flushed queue items (see :meth:`teardown_all_listeners`).
        """
        return await self.teardown_all_listeners()

    async def probe_expose_function_support(self) -> bool:
        """
        [DIAGNOSTIC ONLY — do not call in production]
        Checks if page.expose_function bindings are callable from Camoufox's
        Isolated World (page.evaluate without mw: prefix).

        If True  → a true push-based bridge is viable:
            mw: wpp.on → CustomEvent(id) → Isolated World addEventListener
            → window[alias](id) [expose_function] → Python enqueue
            → _drain_loop → _evaluate_stealth(get_message_by_id)
        If False → the mw: poll approach (current architecture) is correct.

        WARNING: This call permanently registers a named expose_function on the
        page for the lifetime of the session. Only call it once, in a debug
        environment, and never in the main message loop.

        Returns:
            True  = expose_function IS callable from Isolated World.
            False = expose_function is NOT callable from Isolated World.
        """
        probe_alias = f"__probe{self._get_bridge_key()}"
        result_holder = {"called": False}

        async def _probe(x: str) -> None:
            result_holder["called"] = True

        await self.page.expose_function(probe_alias, _probe)
        is_function = await self.page.evaluate(
            f"typeof window['{probe_alias}'] === 'function'"  # Isolated World — no mw:
        )
        self.log.info(
            f"probe_expose_function_support: "
            f"window[alias] in Isolated World = {'function ✓' if is_function else 'undefined ✗'}"
        )
        return bool(is_function)

    # ─────────────────────────────────────────────
    # 3. DATA FETCHING
    # ─────────────────────────────────────────────

    async def get_chat_list(
        self,
        count: int | None = None,
        direction: str = "after",
        only_users: bool = False,
        only_groups: bool = False,
        only_communities: bool = False,
        only_unread: bool = False,
        only_archived: bool = False,
        only_newsletter: bool = False,
        with_labels: list | None = None,
        anchor_chat_id: str | None = None,
        ignore_group_metadata: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Fetch a list of chats from ChatStore in sidebar order.

        Args:
            count:                  Max chats. None = all.
            direction:              'after' (default) or 'before' anchor_chat_id.
            only_users:             Only 1-on-1 personal chats.
            only_groups:            Only group chats.
            only_communities:       Only Community parent groups.
            only_unread:            Only chats with unread messages.
            only_archived:          Only archived chats.
            only_newsletter:        Only WhatsApp Channels.
            with_labels:            filters by label name/ID (Business accounts).
            anchor_chat_id:         Chat ID to paginate from.
            ignore_group_metadata:  Skip group member fetching (faster, True by default).

        Returns:
            List of raw ChatModel dicts, same order as WhatsApp sidebar.
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.list_chats(
                count=count,
                direction=direction,
                only_users=only_users,
                only_groups=only_groups,
                only_communities=only_communities,
                only_unread=only_unread,
                only_archived=only_archived,
                only_newsletter=only_newsletter,
                with_labels=with_labels,
                anchor_chat_id=anchor_chat_id,
                ignore_group_metadata=ignore_group_metadata,
            )
        )

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        """Fetch all scalar metadata for a chat from React memory."""
        return await self._evaluate_stealth(WAJS_Scripts.get_chat(chat_id))

    async def get_messages(
        self,
        chat_id: str,
        count: int = 50,
        direction: str = "before",
        only_unread: bool = False,
        media: str | None = None,
        include_calls: bool = False,
        anchor_msg_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch messages for a chat from React RAM.

        Args:
            chat_id:        The @c.us or @g.us ID.
            count:          Number of messages (-1 for all).
            direction:      'before' (default) or 'after' anchor_msg_id.
            only_unread:    Only return messages user hasn't seen.
            media:          filters to 'all' | 'image' | 'document' | 'url' | None.
            include_calls:  Include call_log entries in results.
            anchor_msg_id:  Full message ID to paginate from.

        Returns:
            List of message dicts with id, body, type, from, to, timestamp, etc.
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.get_messages(
                chat_id=chat_id,
                count=count,
                direction=direction,
                only_unread=only_unread,
                media=media,
                include_calls=include_calls,
                anchor_msg_id=anchor_msg_id,
            )
        )

    async def get_message_by_id(self, msg_id: str) -> dict[str, Any]:
        """
        Fetch one specific message by its full serialized ID.

        Args:
            msg_id: Full message key e.g. 'true_916398014720@c.us_ABCDE123'
        """
        return await self._evaluate_stealth(WAJS_Scripts.get_message_by_id(msg_id))

    # ─────────────────────────────────────────────
    # 4. ACTIONS — TIER 3 FALLBACKS
    # ─────────────────────────────────────────────

    async def send_text_message(
        self, chat_id: str, message: str, options: dict[str, Any] | None = None
    ) -> bool:
        """
        Pure api text send — fire-and-forget via mw: direct eval.

        Why bypass _evaluate_stealth:
            sendTextMessage may wait for server ACK or perform async lookups
            (e.g. quoted message resolution) that make the bridge time out.
            mw: sync IIFE + setTimeout(0) fires the call and returns immediately.

        Options default: waitForAck=False so WPP doesn't block on delivery signal.
        """
        try:
            safe_msg = json.dumps(message)
            safe_options = json.dumps(options or {"waitForAck": False})
            wpp_key = self._wpp_key
            await self.page.evaluate(
                f"mw:(() => {{"
                f"  const wpp = Object.getOwnPropertyDescriptor(window, '{wpp_key}')?.value;"
                f"  if (wpp) setTimeout(() => wpp.chat.sendTextMessage('{chat_id}', {safe_msg}, {safe_options}).catch(() => null), 0);"
                f"  else console.warn('[CamouChat] send_text_message: WPP handle missing ({wpp_key})');"
                f"}})()"
            )
            return True
        except Exception as e:
            self.log.warning(f"send_text_message failed: {e}")
            return False

    async def mark_is_read(self, chat_id: str) -> bool:
        """Force-mark a chat as read. Only call when using Tier 3 pure api mode."""
        try:
            res = await self._evaluate_stealth(WAJS_Scripts.mark_is_read(chat_id))
            return bool(res)
        except Exception as e:
            self.log.warning(f"mark_is_read failed: {e}")
            return False

    async def mark_is_composing(self, chat_id: str, duration_ms: int = 3000) -> bool:
        """Sends typing state to the chat."""
        try:
            res = await self._evaluate_stealth(WAJS_Scripts.mark_is_composing(chat_id, duration_ms))
            return bool(res)
        except Exception as e:
            self.log.warning(f"mark_is_composing failed: {e}")
            return False

    # ─────────────────────────────────────────────
    # 5. INDEX DB — DISK HISTORY
    # ─────────────────────────────────────────────

    async def indexdb_get_messages(
        self,
        min_row_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch raw message data sequentially from IndexedDB storage across ALL chats.
        Type: RAM (Disk)
        Note: Messages are retrieved in order from min_row_id onwards.
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.indexdb_get_messages(min_row_id=min_row_id, limit=limit)
        )

    # ─────────────────────────────────────────────
    # 6. MEDIA DECRYPT — CACHE API / CDN FALLBACK
    # ─────────────────────────────────────────────

    async def decrypt_media(
        self,
        direct_path: str,
        media_key_b64: str,
        media_type: str,
        msg_id: str | None = None,
        save_path: str | None = None,
    ) -> bytes | None:
        """
        Extract and decrypt WhatsApp media using the fields embedded in the raw MsgModel dump.
        Primary path reads directly from the browser Cache api — zero network cost.
        Falls back to wa-js's CDN downloader if the blob is not yet cached.

        Type: RAM (Cache api primary) / NETWORK (CDN fallback — logs INFO when triggered)

        Args:
            direct_path:   msg['directPath']    — CDN path e.g. "/v/t62.7117-24/..."
            media_key_b64: msg['mediaKey']      — base64 AES root key (32 bytes)
            media_type:    msg['type']          — 'image'|'video'|'audio'|'ptt'|'document'|'sticker'
            msg_id:        msg['id_serialized'] — Required for CDN fallback only.
            save_path:     Optional filesystem path to write decrypted bytes to.

        Returns:
            Raw decrypted bytes, or None if both paths fail.

        Raw MsgModel fields needed:
            directPath, mediaKey, type  (+id_serialized for fallback)
        """
        # ── Primary: Cache api (zero network) ───────────────────────────────
        b64 = await self._evaluate_stealth(
            WAJS_Scripts.decrypt_media(
                direct_path=direct_path,
                media_key_b64=media_key_b64,
                media_type=media_type,
            )
        )

        if b64 is None:
            # ── Fallback: wa-js CDN download (NETWORK) ───────────────────────
            if not msg_id:
                self.log.warning(
                    "decrypt_media: Cache miss and no msg_id provided — cannot use CDN fallback."
                )
                return None

            self.log.info(
                f"decrypt_media: Cache miss for {direct_path!r} — "
                f"falling back to CDN download via wpp.chat.downloadMedia() [NETWORK]"
            )
            b64 = await self._evaluate_stealth(WAJS_Scripts.download_media(msg_id=msg_id))

        if not b64:
            return None

        raw_bytes = base64.b64decode(b64)

        if save_path:
            await asyncio.to_thread(self._save_bytes, save_path, raw_bytes)
            self.log.info(f"decrypt_media: Saved {len(raw_bytes):,} bytes → {save_path}")

        return raw_bytes

    # MIME type → file extension map for auto-naming saved media
    _MIME_TO_EXT: dict[str, str] = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
        "video/mp4": ".mp4",
        "video/3gpp": ".3gp",
        "video/quicktime": ".mov",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
        "audio/mpeg": ".mp3",
        "audio/aac": ".aac",
        "audio/amr": ".amr",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    }
    _TYPE_EXT_FALLBACK: dict[str, str] = {
        "image": ".jpg",
        "video": ".mp4",
        "audio": ".ogg",
        "ptt": ".ogg",
        "sticker": ".webp",
        "document": ".bin",
    }

    @staticmethod
    def _ext_from_mime(mimetype: str | None, media_type: str = "image") -> str:
        """Derive file extension from mimetype, falling back to media_type."""
        if mimetype:
            base = mimetype.split(";")[0].strip().lower()
            if base in WapiWrapper._MIME_TO_EXT:
                return WapiWrapper._MIME_TO_EXT[base]
        return WapiWrapper._TYPE_EXT_FALLBACK.get(media_type, ".bin")

    @staticmethod
    def media_save_path(message: dict[str, Any], save_dir: str) -> str:
        """
        Auto-generate a filesystem path for a media message.

        Args:
            message:  Raw MsgModel dict from get_messages() / get_message_by_id()
            save_dir: Directory where the file should be saved (created if absent)

        Returns:
            Full absolute path string, e.g. /path/to/dir/image_false_91XX_ABCD.jpg
        """
        msg_id = message.get("id_serialized", "unknown")
        media_type = message.get("type", "media")
        mimetype = message.get("mimetype") or message.get("mime_type")
        ext = WapiWrapper._ext_from_mime(mimetype, media_type)
        safe_id = msg_id.replace("/", "_").replace("@", "_").replace(":", "_")
        return str(Path(save_dir) / f"{media_type}_{safe_id}{ext}")

    async def extract_media(
        self,
        message: dict[str, Any],
        save_path: str,
    ) -> dict[str, Any]:
        """
        Extract and save WhatsApp media using WPP's internal download pipeline.

        **Stealth (Local-First):** This method uses ``wpp.chat.downloadMedia()``,
        which automatically probes WA's internal LRU caches (Cache Storage & IndexedDB)
        before hitting the CDN. If auto-download is ON in the profile, this
        call is essentially a zero-network RAM snatch.

        Args:
            message:   Raw MsgModel dict. ``id_serialized`` is required.
            save_path: Full filesystem path where the decrypted file is written.

        Returns:
            Absolute path string on success, or ``None`` on any failure.
        """
        msg_id = message.get("id_serialized")
        media_type = message.get("type", "media")
        mimetype = message.get("mimetype")

        result_dict: dict[str, Any] = {
            "success": False,
            "type": media_type,
            "mimetype": mimetype,
            "size_bytes": None,
            "path": None,
            "msg_id": msg_id,
            "view_once": bool(message.get("isViewOnce")),
            "used_fallback": False,
            "latency_ms": 0.0,
            "error": None,
        }

        if not msg_id:
            result_dict["error"] = "id_serialized missing — skipping."
            self.log.warning(f"extract_media: {result_dict['error']}")
            return result_dict

        self.log.info(
            f"extract_media: downloading {msg_id!r} via wpp.chat.downloadMedia() "
            "(reads from lru-media-array-buffer-cache if auto-downloaded, else CDN)."
        )

        try:
            js_result = await self._evaluate_stealth(WAJS_Scripts.download_media(msg_id=msg_id))
        except Exception as e:
            result_dict["error"] = f"JS error: {e}"
            self.log.warning(f"extract_media: {result_dict['error']}")
            return result_dict

        if not js_result:
            result_dict["error"] = f"downloadMedia returned nothing for {msg_id!r}."
            self.log.warning(f"extract_media: {result_dict['error']}")
            return result_dict

        # Unpack structured result {b64, isCached, latencyMs}
        b64 = js_result.get("b64") if isinstance(js_result, dict) else js_result
        is_cached = js_result.get("isCached", False) if isinstance(js_result, dict) else False
        js_latency_ms = js_result.get("latencyMs", 0.0) if isinstance(js_result, dict) else 0.0

        if not b64:
            result_dict["error"] = f"null blob for {msg_id!r}."
            self.log.warning(f"extract_media: {result_dict['error']}")
            return result_dict

        try:
            raw_bytes = base64.b64decode(b64)
        except Exception as e:
            result_dict["error"] = f"base64 decode failed: {e}"
            self.log.warning(f"extract_media: {result_dict['error']}")
            return result_dict

        await asyncio.to_thread(self._save_bytes, save_path, raw_bytes)

        # isCached is derived from JS-native performance.now() timing (<150ms = CACHE)
        source = "CACHE" if is_cached else "NETWORK"
        self.log.info(
            f"extract_media: [{media_type}] {len(raw_bytes):,} bytes → {save_path} "
            f"[{source} | JS:{js_latency_ms:.1f}ms]"
        )

        result_dict.update(
            {
                "success": True,
                "path": save_path,
                "size_bytes": len(raw_bytes),
                "used_fallback": not is_cached,
                "latency_ms": js_latency_ms,
            }
        )
        return result_dict

    # ─────────────────────────────────────────────
    # 6. NEWSLETTER (CHANNELS)
    # ─────────────────────────────────────────────

    async def newsletter_list(self) -> list[dict[str, Any]]:
        """
        Fetch all WhatsApp Channels (Newsletters) you follow.
        Returns raw ChatModel dicts (same shape as get_chat_list()).
        """
        return await self._evaluate_stealth(WAJS_Scripts.newsletter_list())

    async def newsletter_search(self, query: str, limit: int = 20) -> dict[str, Any]:
        """
        Search the WhatsApp Channel directory.

        Args:
            query: Search term (e.g. 'technology', 'news').
            limit: Max results to return (default 20).

        Returns:
            Raw dict with 'newsletters' list and optional 'pageInfo' for pagination.
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.newsletter_search(query=query, limit=limit)
        )

    async def newsletter_follow(self, newsletter_id: str) -> bool:
        """
        Follow / subscribe to a WhatsApp Channel.

        Args:
            newsletter_id: The @newsletter JID e.g. '120363xxxxx@newsletter'.
        """
        return await self._evaluate_stealth(WAJS_Scripts.newsletter_follow(newsletter_id))

    async def newsletter_unfollow(self, newsletter_id: str) -> bool:
        """
        Unfollow / unsubscribe from a WhatsApp Channel.

        Args:
            newsletter_id: The @newsletter JID e.g. '120363xxxxx@newsletter'.
        """
        return await self._evaluate_stealth(WAJS_Scripts.newsletter_unfollow(newsletter_id))

    async def newsletter_mute(self, newsletter_id: str) -> Any:
        """Mute notifications for a WhatsApp Channel."""
        return await self._evaluate_stealth(WAJS_Scripts.newsletter_mute(newsletter_id))

    async def newsletter_unmute(self, newsletter_id: str) -> Any:
        """Unmute notifications for a WhatsApp Channel."""
        return await self._evaluate_stealth(WAJS_Scripts.newsletter_unmute(newsletter_id))

    # ═══════════════════════════════════════════════════════════
    # READ-LEVEL — DATA & INTROSPECTION
    # ═══════════════════════════════════════════════════════════

    # ─────────────────────────────────────────────
    # 7. CONN — Session & Device Info (READ)
    # ─────────────────────────────────────────────

    async def conn_get_my_user_id(self) -> Any:
        """
        Type: RAM (AccountStore — zero network cost, call freely).
        Returns: str — your own WhatsApp ID e.g. '919876543210@c.us'
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_my_user_id())

    async def conn_get_my_user_lid(self) -> Any:
        """
        Type: RAM (AccountStore).
        Returns: str — hardware-bound Linked Device ID e.g. '37358229573849@lid'.
                 Unique per physical device, used in multi-device signal routing.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_my_user_lid())

    async def conn_get_my_user_wid(self) -> Any:
        """
        Type: RAM (AccountStore).
        Returns: str — full serialized Wid e.g. '919876543210@c.us'
                 (same as user_id for personal accounts).
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_my_user_wid())

    async def conn_get_my_device_id(self) -> Any:
        """
        Type: RAM (AccountStore).
        Returns: int — linked device slot index (0 = primary phone, 1-4 = companion devices).
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_my_device_id())

    async def conn_is_online(self) -> bool:
        """
        Type: RAM (AppState — WebSocket stream flag).
        Returns: bool — True if the WS connection to Meta servers is active.
                 Observed: True when session is live.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_is_online())

    async def conn_is_multi_device(self) -> bool:
        """
        Type: RAM (AccountStore).
        Returns: bool — True if the account has multi-device mode enabled.
                 Observed: True for modern WhatsApp (all accounts post-2022 use MD).
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_is_multi_device())

    async def conn_is_idle(self) -> bool:
        """
        Type: RAM (AppState).
        Returns: bool — True if the session has been idle (no WS activity).
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_is_idle())

    async def conn_is_main_ready(self) -> bool:
        """
        Type: RAM (AppState).
        Returns: bool — True if WA Web has fully initialised (stores loaded, WS connected).
                 Use this as the readiness gate before making any api calls.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_is_main_ready())

    async def conn_get_platform(self) -> Any:
        """
        Type: RAM (BuildConstants).
        Returns: str — platform identifier.
                 Observed values: 'android', 'web', 'smbi' (SMB iOS), 'smba' (SMB Android).
                 'android' means the paired primary device is Android.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_platform())

    async def conn_get_theme(self) -> Any:
        """
        Type: RAM (ThemeStore).
        Returns: str — UI theme. Observed values: 'light', 'dark', 'default'.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_theme())

    async def conn_get_stream_data(self) -> Any:
        """
        Type: RAM (StreamStore — WebSocket connection state).
        Returns: dict with fields:
            mode  (str) — 'MAIN' | 'INIT' | 'OFFLINE'
            info  (str) — 'NORMAL' | 'PAUSED' | 'TIMEOUT'
        Observed: {'mode': 'MAIN', 'info': 'NORMAL'} on a live healthy session.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_stream_data())

    async def conn_get_build_constants(self) -> Any:
        """
        Type: RAM (BuildConstants — hardcoded in the WA Web bundle).
        Returns: dict with fields:
            VERSION_PRIMARY          (str) — major version e.g. '2'
            VERSION_SECONDARY        (str) — minor version e.g. '3000'
            VERSION_TERTIARY         (str) — build number e.g. '1035913242'
            VERSION_BASE             (str) — full version string '2.3000.1035913242'
            VERSION_STR              (str) — same as VERSION_BASE
            PUSH_PHASE               (str) — rollout phase e.g. 'C3'
            WINDOWS_BUILD            (str|None) — Windows desktop build if applicable
            WINDOWS_OFFLINE          (bool) — Windows offline mode flag
            VERSION_BASE_WITH_WINDOWS_BUILD (str) — combined version string
            DYN_ORIGIN               (str) — 'https://web.whatsapp.com/'
            WEB_PUBLIC_PATH          (str) — '/'
            BUILD_URL                (str) — 'https://web.whatsapp.com/'
            PARSED                   (dict) — {PRIMARY: int, SECONDARY: int, TERTIARY: int}
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_build_constants())

    async def conn_get_ab_props(self) -> Any:
        """
        Type: RAM (ABProps — A/B feature flags loaded at session init, no ongoing network cost).
        Returns: dict of str → Any — active feature flag overrides for this session.
                 Keys are internal WA experiment names (e.g. 'ab_send_delay_ms').
                 Empty dict if no active experiments.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_ab_props())

    async def conn_get_auto_download_settings(self) -> Any:
        """
        Type: RAM (SettingsStore).
        Returns: dict — media auto-download config, typically:
            photos    (bool)
            audio     (bool)
            video     (bool)
            documents (bool)
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_auto_download_settings())

    async def conn_get_history_sync_progress(self) -> Any:
        """
        Type: RAM (HistorySyncStore — populated after linking a new device).
        Returns: dict|None — sync progress object, or None if no sync is in progress.
                 Relevant only during the first few minutes of a new device link.
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_get_history_sync_progress())

    async def conn_needs_update(self) -> bool:
        """
        Type: RAM (AppState).
        Returns: bool|None — True if WA Web is stale and requires a page reload.
                 Observed: None when session is current (no update needed).
        """
        return await self._evaluate_stealth(WAJS_Scripts.conn_needs_update())

    # ─────────────────────────────────────────────
    # 8. CONTACT (READ)
    # ─────────────────────────────────────────────

    async def contact_get(self, contact_id: str) -> dict[str, Any]:
        """
        Type: RAM (ContactStore — synchronous map lookup, zero network cost).
        NOTE: Your own ID will return {} — you are not stored in your own ContactStore.
              Use contact_id of someone in your address book.
        Returns: dict with fields:
            id_serialized   (str)  — '919876543210@c.us'
            name            (str)  — saved name in your address book
            pushname        (str)  — their WhatsApp display name
            shortName       (str)  — shortened display name
            type            (str)  — 'in' (in contacts) | 'out' (not saved)
            isBusiness      (bool) — whether this is a Business account
            isEnterprise    (bool)
            isMe            (bool) — True if this is your own ID
            isMyContact     (bool) — True if saved in phonebook
            isUser          (bool)
            isWAContact     (bool) — True if they have WhatsApp
            isPSA           (bool) — Public Service Announcement account
            verifiedName    (str|None) — business verified name
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_get(contact_id))

    async def contact_list(self, count: int = 20) -> list[dict[str, Any]]:
        """
        Type: RAM (ContactStore — synchronous ES6 Map iteration).
        Returns: list of contact dicts (see contact_get for field reference).
        Args:
            count: Max contacts to return (default 20). Increase carefully —
                   large address books (500+) slow down the JS bridge.
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_list(count=count))

    async def contact_query_exists(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — sends an XMPP presence/check packet to Meta servers.
              Use sparingly (<30/hr to avoid rate-flag).
        Returns: dict with fields:
            wid             (dict) — {server, user, _serialized} — their WhatsApp ID
            biz             (bool) — whether this is a Business account
            bizInfo         (dict|None) — business info if biz=True
            disappearingMode(dict) — {duration: int, settingTimestamp: int}
            status          (str)  — their current About text (may be empty)
            lid             (dict) — {server, user, _serialized} — linked device ID
        Returns None if the number does not have WhatsApp.
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_query_exists(contact_id))

    async def contact_get_profile_picture_url(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — CDN HTTP request to fetch current profile picture URL.
        Returns: str — CDN URL like 'https://pps.whatsapp.net/v/...'
                 None if the contact has no picture or privacy blocks you.
        Observed: None when contact has default/no picture.
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.contact_get_profile_picture_url(contact_id)
        )

    async def contact_get_status(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP request to fetch their About/status text.
        Returns: str — their About text e.g. 'Hey there! I am using WhatsApp.'
                 Empty string if not set or privacy-blocked.
        Observed: ' ' (space) for accounts with empty about text.
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_get_status(contact_id))

    async def contact_get_business_profile(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — HTTP request for WhatsApp Business profile data.
        Returns: dict with business fields (address, email, website, category, description)
                 None if the contact is not a Business account.
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_get_business_profile(contact_id))

    async def contact_get_common_groups(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP query for shared group list.
        Returns: list of group ID strings e.g. ['120363401916939000@g.us', ...]
        """
        return await self._evaluate_stealth(WAJS_Scripts.contact_get_common_groups(contact_id))

    # ─────────────────────────────────────────────
    # 9. GROUP (READ)
    # ─────────────────────────────────────────────

    async def group_get_all(self) -> list[dict[str, Any]]:
        """
        Type: RAM (ChatStore filter — zero network cost).
        Returns: list of group ChatModel dicts. Observed fields per group:
            id_serialized           (str)  — '120363401916939000@g.us'
            __x_name                (str)  — group display name
            __x_formattedTitle      (str)  — same as name
            __x_unreadCount         (int)  — unread message count
            __x_muteExpiration      (int)  — 0 if not muted, else Unix ts
            __x_isAutoMuted         (bool)
            __x_archive             (bool) — whether archived
            __x_isLocked            (bool) — admin-only send restriction
            __x_notSpam             (bool) — False = flagged by Meta
            __x_canSend             (bool) — whether you can send in this group
            __x_ephemeralDuration   (int)  — disappearing msg duration (0=off)
            __x_ephemeralSettingTimestamp (int)
            __x_isAnnounceGrpRestrict    (bool) — announcement-only group
            __x_isReadOnly          (bool)
            __x_trusted             (bool)
            __x_groupType           (str)  — 'DEFAULT' | 'COMMUNITY' | 'ANNOUNCEMENT'
            __x_hasCapi             (bool) — has Community api features
            __x_isParentGroup       (bool) — is a Community parent group
            __x_groupSafetyChecked  (bool)
            __x_msgsLength          (int)  — messages loaded in RAM
            __x_msgsChanged         (int)  — change counter
            __x_t                   (int)  — last activity Unix timestamp
            __x_pendingAction       (int)
            __x_unreadMentionCount  (int)
            __x_disappearingModeTrigger  (str) — 'chat_settings' | 'account'
            __x_disappearingModeInitiator (str)
            revisionNumber          (int)  — internal group metadata revision
            initialIndex            (int)  — sidebar position
            proxyName               (str)  — always 'chat'
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_all())

    async def group_get_participants(self, group_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP fetch from Meta servers. Can take 2–5s+.
              Use only when you need the live member list; avoid polling.
        Returns: list of participant dicts, each with:
            id_serialized (str) — participant WhatsApp ID
            isAdmin       (bool)
            isSuperAdmin  (bool)
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_participants(group_id))

    async def group_get_invite_code(self, group_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP request. Requires admin privileges.
        Returns: str — the invite code portion of the link
                 (full link = 'https://chat.whatsapp.com/<invite_code>')
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_invite_code(group_id))

    async def group_get_info_from_invite_code(self, invite_code: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP fetch. Safe to call before joining.
        Returns: dict with group preview metadata:
            id_serialized  (str)  — group JID
            subject        (str)  — group name
            size           (int)  — current member count
            creation       (int)  — creation Unix timestamp
        """
        return await self._evaluate_stealth(
            WAJS_Scripts.group_get_info_from_invite_code(invite_code)
        )

    async def group_get_membership_requests(self, group_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — XMPP fetch. Only works if you are admin.
        Returns: list of pending join request dicts:
            id_serialized  (str) — requester's WhatsApp ID
            addedBy        (str) — who added them (if via invite link)
            requestTime    (int) — Unix timestamp of request
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_membership_requests(group_id))

    async def group_get_past_participants(self, group_id: str) -> Any:
        """
        Type: RAM (GroupMetadataStore — cached locally).
        Returns: list of past participant dicts:
            id_serialized  (str) — their WhatsApp ID
            leaveTs        (int) — Unix timestamp when they left
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_past_participants(group_id))

    async def group_i_am_admin(self, group_id: str) -> bool:
        """
        Type: RAM (GroupMetadataStore — local participant role lookup).
        Returns: bool — True if your ID is in the admin list of this group.
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_i_am_admin(group_id))

    async def group_i_am_super_admin(self, group_id: str) -> bool:
        """
        Type: RAM (GroupMetadataStore).
        Returns: bool — True if you are the group creator (super-admin).
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_i_am_super_admin(group_id))

    async def group_get_size_limit(self) -> Any:
        """
        Type: RAM (BuildConstants / ABProps).
        Returns: int — max participants for a group.
                 Standard: 1024. Communities announcement groups: 5000.
        """
        return await self._evaluate_stealth(WAJS_Scripts.group_get_size_limit())

    # ─────────────────────────────────────────────
    # 10. BLOCKLIST (READ)
    # ─────────────────────────────────────────────

    async def blocklist_all(self) -> list[dict[str, Any]]:
        """
        Type: RAM (BlocklistStore — local list, no network cost).
        Returns: list of blocked contact dicts (same fields as contact_get).
                 Empty list if no contacts are blocked.
        """
        return await self._evaluate_stealth(WAJS_Scripts.blocklist_all())

    async def blocklist_is_blocked(self, contact_id: str) -> bool:
        """
        Type: RAM (BlocklistStore — O(1) set lookup).
        Returns: bool — True if the contact_id is in your block list.
        """
        return await self._evaluate_stealth(WAJS_Scripts.blocklist_is_blocked(contact_id))

    # ─────────────────────────────────────────────
    # 11. STATUS / STORIES (READ)
    # ─────────────────────────────────────────────

    async def status_get(self, contact_id: str) -> Any:
        """
        Type: NETWORK ⚠️ — fetches their Status from Meta's CDN/servers.
        Returns: list of Status story objects, each with:
            id_serialized  (str)  — message ID of the story
            type           (str)  — 'text' | 'image' | 'video'
            body           (str)  — text content (for text stories)
            t              (int)  — Unix timestamp of post
            mimetype       (str)  — media MIME type if media story
            isViewed       (bool) — whether you've viewed it
        Returns empty list if they have no active stories or privacy blocks you.
        """
        return await self._evaluate_stealth(WAJS_Scripts.status_get(contact_id))

    async def status_get_mine(self) -> Any:
        """
        Type: RAM (StatusStore — your own stories cached locally).
        Returns: list of your own Status story objects (same fields as status_get).
                 Empty list if you have no active stories.
        """
        return await self._evaluate_stealth(WAJS_Scripts.status_get_mine())

    # ─────────────────────────────────────────────
    # 12. PROFILE (READ)
    # ─────────────────────────────────────────────

    async def profile_get_my_name(self) -> Any:
        """
        Type: RAM (AccountStore).
        Returns: str — your WhatsApp display name as set in your profile settings.
        """
        return await self._evaluate_stealth(WAJS_Scripts.profile_get_my_name())

    async def profile_get_my_status(self) -> Any:
        """
        Type: RAM (AccountStore).
        Returns: str — your About text. Empty string if not set.
        """
        return await self._evaluate_stealth(WAJS_Scripts.profile_get_my_status())

    async def profile_get_my_picture(self) -> Any:
        """
        Type: RAM (AccountStore — locally cached URL).
        Returns: str — CDN URL for your own profile picture, or None if no picture.
        """
        return await self._evaluate_stealth(WAJS_Scripts.profile_get_my_picture())

    async def profile_is_business(self) -> bool:
        """
        Type: RAM (AccountStore).
        Returns: bool — True if this is a WhatsApp Business (SMBI/SMBA) account.
                 NOTE: platform='android' does NOT mean it's not Business;
                 check isBusiness separately.
        """
        return await self._evaluate_stealth(WAJS_Scripts.profile_is_business())

    # ─────────────────────────────────────────────
    # 13. PRIVACY (READ)
    # ─────────────────────────────────────────────

    async def privacy_get(self) -> Any:
        """
        Type: RAM (PrivacyStore — locally synced privacy settings).
        Returns: dict with fields:
            readreceipts    (str) — 'all' | 'none' (blue tick visibility)
            profile         (str) — 'all' | 'contacts' | 'contact_blacklist' | 'none'
            status          (str) — who can see your Status stories
            online          (str) — 'all' | 'match_last_seen'
            last            (str) — last seen visibility
            groupadd        (str) — who can add you to groups
        """
        return await self._evaluate_stealth(WAJS_Scripts.privacy_get())

    # ─────────────────────────────────────────────
    # 14. LABELS (READ) — Business accounts only
    # ─────────────────────────────────────────────

    async def labels_get_all(self) -> Any:
        """
        Type: RAM (LabelsStore — Business accounts only).
        Returns: list of label dicts, each with:
            id          (str) — label ID
            name        (str) — display name
            color       (int) — color palette index
            colorHex    (str) — hex color string e.g. '#FF6900'
            predefined  (bool) — True for WhatsApp built-in labels
        Returns empty list on non-Business accounts.
        """
        return await self._evaluate_stealth(WAJS_Scripts.labels_get_all())

    async def labels_get_by_id(self, label_id: str) -> Any:
        """
        Type: RAM (LabelsStore).
        Returns: single label dict (see labels_get_all for fields), or None if not found.
        """
        return await self._evaluate_stealth(WAJS_Scripts.labels_get_by_id(label_id))

    # ─────────────────────────────────────────────
    # 15. COMMUNITY (READ)
    # ─────────────────────────────────────────────

    async def community_get_subgroups(self, community_id: str) -> Any:
        """Child group chats of a Community."""
        return await self._evaluate_stealth(WAJS_Scripts.community_get_subgroups(community_id))

    async def community_get_participants(self, community_id: str) -> Any:
        """All members across a Community."""
        return await self._evaluate_stealth(WAJS_Scripts.community_get_participants(community_id))

    async def community_get_announcement_group(self, community_id: str) -> Any:
        """The admin broadcast/announcement group of a Community."""
        return await self._evaluate_stealth(
            WAJS_Scripts.community_get_announcement_group(community_id)
        )

    # ═══════════════════════════════════════════════════════════
    # ACTION-LEVEL — MUTATIONS & INTERACTIONS (OPTIONAL / TIER 3)
    # ═══════════════════════════════════════════════════════════

    # ─────────────────────────────────────────────
    # CONN (ACTIONS)
    # ─────────────────────────────────────────────

    async def conn_logout(self) -> Any:
        """Terminate the WhatsApp session."""
        return await self._evaluate_stealth(WAJS_Scripts.conn_logout())

    async def conn_mark_available(self) -> Any:
        """Appear as online/available."""
        return await self._evaluate_stealth(WAJS_Scripts.conn_mark_available())

    async def conn_set_keep_alive(self, enabled: bool = True) -> Any:
        """Prevent the session from going idle."""
        return await self._evaluate_stealth(WAJS_Scripts.conn_set_keep_alive(enabled))

    async def conn_refresh_qr(self) -> Any:
        """Force a fresh QR code to be generated (for QR login flows)."""
        return await self._evaluate_stealth(WAJS_Scripts.conn_refresh_qr())

    async def conn_set_theme(self, theme: str) -> Any:
        """Set UI theme. Values: 'default' (light) | 'dark'."""
        return await self._evaluate_stealth(WAJS_Scripts.conn_set_theme(theme))

    # ─────────────────────────────────────────────
    # CONTACT (ACTIONS)
    # ─────────────────────────────────────────────

    async def contact_subscribe_presence(self, contact_id: str) -> Any:
        """Start receiving real-time online/typing presence events for a contact."""
        return await self._evaluate_stealth(WAJS_Scripts.contact_subscribe_presence(contact_id))

    async def contact_unsubscribe_presence(self, contact_id: str) -> Any:
        """Stop receiving presence events for a contact."""
        return await self._evaluate_stealth(WAJS_Scripts.contact_unsubscribe_presence(contact_id))

    async def contact_save(self, contact_id: str, name: str) -> Any:
        """Save or update the display name for a contact."""
        return await self._evaluate_stealth(WAJS_Scripts.contact_save(contact_id, name))

    async def contact_remove(self, contact_id: str) -> Any:
        """Delete a contact from your address book."""
        return await self._evaluate_stealth(WAJS_Scripts.contact_remove(contact_id))

    async def contact_report(self, contact_id: str) -> Any:
        """Report a contact to Meta."""
        return await self._evaluate_stealth(WAJS_Scripts.contact_report(contact_id))

    # ─────────────────────────────────────────────
    # GROUP (ACTIONS)
    # ─────────────────────────────────────────────

    async def group_create(self, name: str, participants: list[str]) -> Any:
        """Create a new group chat."""
        return await self._evaluate_stealth(WAJS_Scripts.group_create(name, participants))

    async def group_add_participants(self, group_id: str, participants: list[str]) -> Any:
        """Add members to a group."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_add_participants(group_id, participants)
        )

    async def group_remove_participants(self, group_id: str, participants: list[str]) -> Any:
        """Remove members from a group."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_remove_participants(group_id, participants)
        )

    async def group_promote_participants(self, group_id: str, participants: list[str]) -> Any:
        """Promote members to admin."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_promote_participants(group_id, participants)
        )

    async def group_demote_participants(self, group_id: str, participants: list[str]) -> Any:
        """Remove admin from members."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_demote_participants(group_id, participants)
        )

    async def group_leave(self, group_id: str) -> Any:
        """Leave a group chat."""
        return await self._evaluate_stealth(WAJS_Scripts.group_leave(group_id))

    async def group_join(self, invite_code: str) -> Any:
        """Join a group via invite link code."""
        return await self._evaluate_stealth(WAJS_Scripts.group_join(invite_code))

    async def group_set_subject(self, group_id: str, name: str) -> Any:
        """Rename a group."""
        return await self._evaluate_stealth(WAJS_Scripts.group_set_subject(group_id, name))

    async def group_set_description(self, group_id: str, text: str) -> Any:
        """Set the group description."""
        return await self._evaluate_stealth(WAJS_Scripts.group_set_description(group_id, text))

    async def group_revoke_invite_code(self, group_id: str) -> Any:
        """Revoke the current invite link and generate a new one."""
        return await self._evaluate_stealth(WAJS_Scripts.group_revoke_invite_code(group_id))

    async def group_approve_membership(self, group_id: str, participants: list[str]) -> Any:
        """Approve pending join requests."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_approve_membership(group_id, participants)
        )

    async def group_reject_membership(self, group_id: str, participants: list[str]) -> Any:
        """Reject pending join requests."""
        return await self._evaluate_stealth(
            WAJS_Scripts.group_reject_membership(group_id, participants)
        )

    # ─────────────────────────────────────────────
    # BLOCKLIST (ACTIONS)
    # ─────────────────────────────────────────────

    async def blocklist_block(self, contact_id: str) -> Any:
        """Block a contact."""
        return await self._evaluate_stealth(WAJS_Scripts.blocklist_block(contact_id))

    async def blocklist_unblock(self, contact_id: str) -> Any:
        """Unblock a contact."""
        return await self._evaluate_stealth(WAJS_Scripts.blocklist_unblock(contact_id))

    # ─────────────────────────────────────────────
    # STATUS (ACTIONS)
    # ─────────────────────────────────────────────

    async def status_send_text(self, text: str, bg_color: str | None = None) -> Any:
        """Post a text Status story."""
        return await self._evaluate_stealth(WAJS_Scripts.status_send_text(text, bg_color))

    async def status_send_read(self, msg_id: str) -> Any:
        """Mark a Status story as viewed."""
        return await self._evaluate_stealth(WAJS_Scripts.status_send_read(msg_id))

    async def status_remove(self, msg_id: str) -> Any:
        """Delete one of your own Status stories."""
        return await self._evaluate_stealth(WAJS_Scripts.status_remove(msg_id))

    # ─────────────────────────────────────────────
    # PROFILE (ACTIONS)
    # ─────────────────────────────────────────────

    async def profile_set_my_name(self, name: str) -> Any:
        """Change your WhatsApp display name."""
        return await self._evaluate_stealth(WAJS_Scripts.profile_set_my_name(name))

    async def profile_set_my_status(self, text: str) -> Any:
        """Change your About text."""
        return await self._evaluate_stealth(WAJS_Scripts.profile_set_my_status(text))

    async def profile_remove_my_picture(self) -> Any:
        """Remove your profile picture."""
        return await self._evaluate_stealth(WAJS_Scripts.profile_remove_my_picture())

    # ─────────────────────────────────────────────
    # PRIVACY (ACTIONS)
    # ─────────────────────────────────────────────

    async def privacy_set_last_seen(self, value: str) -> Any:
        """Who can see your Last Seen. Values: 'all'|'contacts'|'contact_blacklist'|'none'."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_last_seen(value))

    async def privacy_set_online(self, value: str) -> Any:
        """Who can see your Online status. Values: 'all'|'match_last_seen'."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_online(value))

    async def privacy_set_profile_pic(self, value: str) -> Any:
        """Who can see your profile picture."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_profile_pic(value))

    async def privacy_set_read_receipts(self, value: str) -> Any:
        """Enable/disable blue ticks. Values: 'all'|'none'."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_read_receipts(value))

    async def privacy_set_add_group(self, value: str) -> Any:
        """Who can add you to groups."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_add_group(value))

    async def privacy_set_status(self, value: str) -> Any:
        """Who can see your Status stories."""
        return await self._evaluate_stealth(WAJS_Scripts.privacy_set_status(value))

    # ─────────────────────────────────────────────
    # LABELS (ACTIONS) — Business accounts only
    # ─────────────────────────────────────────────

    async def labels_add_new(self, name: str, color: int | None = None) -> Any:
        """Create a new label."""
        return await self._evaluate_stealth(WAJS_Scripts.labels_add_new(name, color))

    async def labels_delete(self, label_id: str) -> Any:
        """Delete a label."""
        return await self._evaluate_stealth(WAJS_Scripts.labels_delete(label_id))

    async def labels_apply(self, chat_id: str, label_ids: list[str]) -> Any:
        """Apply labels to a chat."""
        return await self._evaluate_stealth(WAJS_Scripts.labels_apply(chat_id, label_ids))

    # ─────────────────────────────────────────────
    # CALL (ACTIONS)
    # ─────────────────────────────────────────────

    async def call_offer(self, contact_id: str, is_video: bool = False) -> Any:
        """Initiate a voice or video call."""
        return await self._evaluate_stealth(WAJS_Scripts.call_offer(contact_id, is_video))

    async def call_accept(self, call_id: str) -> Any:
        """Accept an incoming call."""
        return await self._evaluate_stealth(WAJS_Scripts.call_accept(call_id))

    async def call_reject(self, call_id: str) -> Any:
        """Reject an incoming call."""
        return await self._evaluate_stealth(WAJS_Scripts.call_reject(call_id))

    async def call_end(self, call_id: str) -> Any:
        """End an active call."""
        return await self._evaluate_stealth(WAJS_Scripts.call_end(call_id))

    # ─────────────────────────────────────────────
    # COMMUNITY (ACTIONS)
    # ─────────────────────────────────────────────

    async def community_create(self, name: str, group_ids: list[str]) -> Any:
        """Create a new Community with existing groups."""
        return await self._evaluate_stealth(WAJS_Scripts.community_create(name, group_ids))

    async def community_deactivate(self, community_id: str) -> Any:
        """Deactivate / close a Community."""
        return await self._evaluate_stealth(WAJS_Scripts.community_deactivate(community_id))

    async def community_add_subgroups(self, community_id: str, group_ids: list[str]) -> Any:
        """Add groups to an existing Community."""
        return await self._evaluate_stealth(
            WAJS_Scripts.community_add_subgroups(community_id, group_ids)
        )

    async def community_remove_subgroups(self, community_id: str, group_ids: list[str]) -> Any:
        """Remove groups from a Community."""
        return await self._evaluate_stealth(
            WAJS_Scripts.community_remove_subgroups(community_id, group_ids)
        )
