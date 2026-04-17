"""
This scripts checks for camoufox being able to render the humanized click via Js execution or not ?
"""

import asyncio

from camouchat_browser import (
    BrowserConfig,
    BrowserForge,
    CamoufoxBrowser,
    ProfileManager,
)
from camouchat_core import Platform
from camouchat_whatsapp import (
    Login,
    WebSelectorConfig,
)


async def main():
    # ── 1. Profile ─────────────────────────────────────────────────────────────
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="Work")

    # ── 2. Browser ─────────────────────────────────────────────────────────────
    browser_forge = BrowserForge()
    config = BrowserConfig.from_dict(
        {
            "platform": Platform.WHATSAPP,
            "locale": "en-US",
            "enable_cache": False,
            "headless": False,
            "fingerprint_obj": browser_forge,
            "geoip": False,
        }
    )
    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()

    # ── 3. Login (reuses session) ───────────────────────────────────────────────
    ui = WebSelectorConfig(page=page)
    login = Login(page=page, UIConfig=ui)
    await login.login(method=0)  # Auto Handles saved Persistence.

    # ── 4. Click Test ───────────────────────────────────────────────────────────
    await asyncio.sleep(2)  # Let WA fully render

    # ── Phase 1: JS element.click() — synthetic event, NO mouse movement ────────
    print("\n[Phase 1] JS synthetic click via page.evaluate...")
    result = await page.evaluate("""() => {
        // Stable selector: data-icon attribute only, no hardcoded class names
        const el = document.querySelector('[data-icon="wa-wordmark-refreshed"]');
        if (!el) {
            console.warn('[CamouChat] WA logo not found in DOM');
            return { found: false, clicked: false, reason: 'element not found' };
        }
        const rect = el.getBoundingClientRect();
        console.log('[CamouChat] WA logo found:', el.tagName, '| rect:', JSON.stringify(rect));
        el.click();
        return {
            found: true,
            clicked: true,
            tag: el.tagName,
            rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
        };
    }""")
    print(f"[Phase 1] Result: {result}")
    print("         → If mouse did NOT move: JS click() is synthetic (no humanization).")

    await asyncio.sleep(2)

    # ── Phase 2: Playwright page.click() via bounding rect → humanized mouse ────
    print("\n[Phase 2] Playwright humanized click via bounding rect...")
    rect_data = await page.evaluate("""() => {
        const el = document.querySelector('[data-icon="wa-wordmark-refreshed"]');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height };
    }""")

    if rect_data:
        center_x = rect_data["x"] + rect_data["width"] / 2
        center_y = rect_data["y"] + rect_data["height"] / 2
        print(f"[Phase 2] Element bounding rect: {rect_data}")
        print(f"[Phase 2] Clicking center at ({center_x:.1f}, {center_y:.1f}) via page.mouse...")
        # Playwright humanize moves mouse in natural curve to this position
        await page.mouse.move(center_x, center_y)
        await asyncio.sleep(0.1)
        await page.mouse.click(center_x, center_y)
        print("[Phase 2] Done. → Watch if mouse moved to the WA logo.")
    else:
        print("[Phase 2] Element not found — cannot compute bounding rect.")

    await asyncio.sleep(5)  # Hold browser open to observe


if __name__ == "__main__":
    asyncio.run(main())