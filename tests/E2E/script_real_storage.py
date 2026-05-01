"""
This script demonstrates how to use the SQLAlchemyStorage to store
and retrieve messages from the database via manual method.
"""

import asyncio
import traceback

from camouchat_browser import (
    BrowserConfig,
    CamoufoxBrowser,
    ProfileManager,
)
from camouchat_core import Platform

from camouchat_whatsapp import (
    Login,
    MessageModelAPI,
    SQLAlchemyStorage,
    WapiSession,
    on_newMsg,
)


async def main():
    # ── Setup Storage (Once) ───────────────────────────────────────────────
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="work")
    print("profile path : ", profile.profile_dir)
    # Initialize storage once outside the loop
    storage = SQLAlchemyStorage.from_profile(profile=profile)
    await storage.start()

    save_ids = []
    msgs_batch = []

    # ── Browser & Login ────────────────────────────────────────────────────
    config = BrowserConfig.from_dict({"platform": Platform.WHATSAPP, "headless": False})
    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()
    login = Login(page=page, profile=profile)
    await login.login(method=0)

    # ── Event Hook ─────────────────────────────────────────────────────────
    wapi = WapiSession(page=page)

    @on_newMsg(
        wapi_session=wapi
    )  # can also give profile=profile here, it will auto add new_msg to storage
    async def new_msg(msg: MessageModelAPI):
        print("New Msg Arrived with type--")
        print(msg)

        save_ids.append(msg.id_serialized)
        msgs_batch.append(msg)

    await new_msg()

    try:
        print("\n>>> Listening for messages... Press Ctrl+C to stop and view data from DB.")
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        # 1. Batch insert everything collected during the session
        await storage.enqueue_insert(msgs=msgs_batch)
        await asyncio.sleep(3)  # minimum enqueue insert time.

        # 2. Fetch ONLY the specific messages we just saved using the Query layer
        from camouchat_whatsapp.storage.queries import Query

        query = Query(profile)
        db_msgs = await query.get_messages_by_ids_async(save_ids)

        print("\n\n" + "=" * 50)
        print(f"DATABASE VERIFICATION: {len(db_msgs)} records retrieved by target IDs.")
        print("=" * 50)

        for msg in db_msgs:
            body = msg.body or ""
            body_disp = f"{body[:40]}...[truncated {len(body)} chars]" if len(body) > 100 else body

            print("\n--- Found DB Record ---")
            print(f"ID     : {msg.id_serialized}")
            print(f"DB Id  : {msg.id}")
            print(f"Type   : {msg.msgtype}")
            print(f"Body   : {body_disp}")
            print(f"FromMe : {msg.fromMe}")
            print(f"ChatID : {msg.chat_id}")
            print(f"Time   : {msg.timestamp}")
            print(f"Created: {msg.created_at}")
            print(f"E-Nonce: {msg.encryption_nonce}")
            print("-----------------------")

        await CamoufoxBrowser.close_browser_by_profile(profile_id="work")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except BrokenPipeError:
        pass  # Browser subprocess closed pipes on Ctrl+C — expected.
    except Exception:
        traceback.print_exc()
