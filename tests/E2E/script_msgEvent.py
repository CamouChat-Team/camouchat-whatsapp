"""
Here we will be testing the new Msg Event Hook based Architecture Prototyping.
"""

import asyncio

from camouchat_browser import (
    BrowserConfig,
    CamoufoxBrowser,
    ProfileManager,
)
from camouchat_core import FileTyped, MediaType, Platform

from camouchat_whatsapp import Login, MediaController


async def main():
    # ── 1. Profile ─────────────────────────────────────────────────────────────
    pm = ProfileManager()
    profile = pm.create_profile(platform=Platform.WHATSAPP, profile_id="Work")

    # ── 2. Browser ─────────────────────────────────────────────────────────────
    # browser_forge = BrowserForge() # Used to Generate Random Fingerprints for the browser ,
    # Also handles automatic generation of fingerprints if not provided.
    config = BrowserConfig.from_dict(
        {
            "platform": Platform.WHATSAPP,
            # "locale": "en-US",
            # "enable_cache": False,
            "headless": False,
            # "fingerprint_obj": browser_forge, changed to fingerprint, also default auto sets.
            # "geoip": False,
        }
        # Other Commented Values are default Testing based, if used for real script ,
        #  considering updating them Proxy based requirements. etc.
    )
    browser = CamoufoxBrowser(config=config, profile=profile)
    page = await browser.get_page()

    # ── 3. Login (reuses session) ───────────────────────────────────────────────
    # ui = WebSelectorConfig(page=page)
    login = (Login(page=page),)  # UIConfig=ui) # default setup can take.
    await login.login(method=0)  # Auto Handles saved Persistence.

    # ── 4. Message event hook ───────────────────────────────────────────────────
    from camouchat_whatsapp import (
        InteractionController,
        MessageModelAPI,
        WapiSession,
        on_newMsg,
    )

    wapi = WapiSession(page=page)
    interaction = InteractionController(page=page, wapi=wapi)  # , ui_config=ui,
    media = MediaController(page=page, wapi=wapi, profile=profile)  # ,  UIConfig=ui,

    # Pass the Wapi Session object here
    # Also if profile passed it it will auto save msgs to Storage.
    @on_newMsg(wapi_session=wapi, profile=profile)
    async def new_msg(msg: MessageModelAPI):
        print("\n --------- New Msg Arrived ───────────────────────────────────")
        print(msg, "\n")

        print(f"--------------Opening the Chat where msg came from : {msg.jid_From}")
        chat = await wapi.chat_manager.get_chat_by_id(msg.jid_From)  # get chatData
        print("Chat ---")
        print(chat)
        await wapi.chat_manager.open_chat(chat=chat)
        print(
            f"----------------Chat Opened name = {chat.formattedTitle} , "
            f"id = {chat.id_serialized} \n"
        )
        success = False

        # Process the msg Commands by some dummy commands.
        if msg.body == "!ping":
            print(f"[*] Command triggered: !ping from {msg.jid_From}")
            # await replyObj.quote_only(message=msg)  # UI: Trigger the quote/reply bubble
            await interaction.send_api_text(
                chat_id=msg.jid_From,
                text=(
                    "**You have been Ponged!!!** \ud83c\udfd3\n"
                    "_Reply from CamouChat Stealth Bridge_"
                ),
                quoted_msg_id=msg.id_serialized,
            )
            success = True

        elif msg.body == "!info":
            print(f"[*] Command triggered: !info from {msg.jid_From}")
            # Tests ChatModelAPI and dynamic metadata extraction
            # await replyObj.quote_only(message=msg)
            info_text = (
                f"\ud83d\udcdd *Chat Info*\n"
                f"\u2022 Title: {chat.formattedTitle}\n"
                f"\u2022 JID: {chat.id_serialized}\n"
                f"\u2022 Unread: {chat.unreadCount}\n"
                f"\u2022 GroupType: {chat.groupType}\n"
                f"\u2022 GroupSafetyChecked Flag: {chat.groupSafetyChecked}\n"
                f"\u2022 Is Archived: {chat.isArchived}\n"
            )
            await interaction.send_api_text(
                text=info_text,
                chat_id=msg.jid_From,
                quoted_msg_id=msg.id_serialized,
            )
            success = True

        elif msg.body == "!me":
            print("[*] Command triggered: !me (Identity Extraction)")
            # Tests identity and sender objects
            sender_name = msg.author if chat.groupType != "DEFAULT" else chat.id_serialized
            push_name = msg.pushname
            await interaction.send_api_text(
                chat_id=msg.jid_From,
                text=(
                    f"\ud83d\udc64 *Identity Profile*\n"
                    f"\u2022 Sender_id: {sender_name}\n"
                    f"\u2022 PushName: {push_name}"
                ),
                quoted_msg_id=msg.id_serialized,
            )
            success = True

        elif msg.body and msg.body.startswith("!echo "):
            print("[*] Command triggered: !echo (Humanized Interaction)")
            echo_text = msg.body.replace("!echo ", "")
            await interaction.send_text(
                message=msg,
                text=f"Echo: {echo_text}",  # Type using manual/clipboard
                quote=True,  # add quote using browser automation
                send=True,  # send to send text or not.
            )
            success = True

        elif msg.body and msg.body == "!media":
            print("[*] Command triggered: !media — requesting test image upload")
            await interaction.send_api_text(
                chat_id=msg.jid_From,
                text="📎 Send me any image, video, or audio to test media save+resend.",
                quoted_msg_id=msg.id_serialized,
            )
            success = True

        elif msg.msgtype in (
            "image",
            "video",
            "audio",
            "ptt",
            "document",
            "sticker",
            "gif",
        ):
            print(f"[*] Media message received — type={msg.msgtype}")

            # 1. Save to disk (WPP managed local-first download)
            saved_path = await media.save_media(message=msg)

            if not saved_path:
                print("[!] save_media returned None — media could not be retrieved.")
                await interaction.send_api_text(
                    chat_id=msg.jid_From,
                    text=f"⚠️ Could not retrieve media (type={msg.msgtype}).",
                    quoted_msg_id=msg.id_serialized,
                )
                return

            print(f"[✔] Media saved → {saved_path}")

            # 2. Re-upload the saved file back to the same chat
            wa_type = msg.msgtype or "document"
            if wa_type in ("image", "sticker"):
                mtype = MediaType.IMAGE
            elif wa_type in ("video", "gif"):
                mtype = MediaType.VIDEO
            elif wa_type in ("audio", "ptt"):
                mtype = MediaType.AUDIO
            else:
                mtype = MediaType.DOCUMENT

            import os

            file_name = os.path.basename(saved_path)
            file_obj = FileTyped(uri=saved_path, name=file_name, mime_type=msg.mimetype)

            print(f"[*] Re-uploading {file_name} as {mtype} to {msg.jid_From}")
            resend_ok = await media.add_media(
                mtype=mtype, file=file_obj, force=True
            )  # Force it cuz we customly adding then sending.
            if resend_ok:
                print("[✔] Media re-sent successfully.")
            else:
                print("[!] add_media returned False — re-send may have failed.")

            success = True

        print("Success for this cmd completion = ", success)

    # Keep the script running to listen for events
    await new_msg()

    print("\n[\u2714] Hook active. Try sending !ping, !info, !me, or !echo <text> in WhatsApp.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc()
