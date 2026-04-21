from camouchat_whatsapp.logger import get_whatsapp_logger


def smoke_test():
    # 1. Initialize WhatsApp Logger with specific profile
    wa_log = get_whatsapp_logger("smoke_test", profile_id="WA_ADMIN", level=10)

    print("\n--- WhatsApp Plugin Logging Test ---")
    wa_log.info("Testing WhatsApp Info Log")
    wa_log.error("Testing WhatsApp Error Log")
    wa_log.debug("Testing WhatsApp Debug Log")
    wa_log.critical("Testing WhatsApp Critical Log")


if __name__ == "__main__":
    smoke_test()
