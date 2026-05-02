import functools
import inspect
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from camouchat_browser import ProfileInfo
from camouchat_core import KeyManager, MessageEncryptor, MessageProtocol

from camouchat_whatsapp.logger import w_logger

# Keyed by profile_id string — ProfileInfo is not hashable so WeakKeyDictionary cannot be used.
key_cache: dict[str, MessageEncryptor] = {}


def on_encrypt(profile: ProfileInfo) -> Callable:
    """
    Decorator factory that encrypts incoming messages.
    Caches the MessageEncryptor instance per profile to avoid redundant IO.
    """
    if profile is None:
        raise ValueError(
            "@on_encrypt: 'encrypt=True' requires a profile in RegistryConfig."
            "Pass: RegistryConfig(profile=your_profile, encrypt=True)."
        )
    if profile.profile_id in key_cache:
        encryptor = key_cache[profile.profile_id]
    else:
        en_dict: dict[str, Any] = profile.encryption
        enabled_flag = en_dict.get("enabled", False) and en_dict.get("created_at") is not None
        key_path = en_dict.get("key_file")
        raw_key: bytes = b""

        if enabled_flag and key_path:
            with open(key_path, "rb") as f:
                key_b = f.read()
                raw_key = KeyManager.decode_key_from_storage(key_b.decode())
        else:
            raw_key = KeyManager.generate_random_key()
            if key_path:
                with open(key_path, "wb") as fw:
                    fw.write(KeyManager.encode_key_for_storage(raw_key).encode())
                profile.encryption["enabled"] = True
                profile.encryption["created_at"] = datetime.now(UTC).isoformat()
            else:
                w_logger.warning("Encryption is enabled but key path is currupted.")

        encryptor = MessageEncryptor(raw_key)
        key_cache[profile.profile_id] = encryptor

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        sig = inspect.signature(func)
        msg_param_name = None

        # First try: find param annotated with MessageProtocol
        for name, param in sig.parameters.items():
            if param.annotation == MessageProtocol:
                msg_param_name = name
                break

        # Fallback: use first positional param
        if msg_param_name is None:
            params = list(sig.parameters.keys())
            if params:
                msg_param_name = params[0]

        if msg_param_name is None:
            raise TypeError(
                f"@on_encrypt: '{func.__name__}' must have at least one parameter for the message."
            )

        @functools.wraps(func)
        async def register(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            msg_obj: MessageProtocol = bound.arguments.get(msg_param_name)  # type: ignore[assignment]

            if msg_obj and msg_obj.body:
                # Use the cached encryptor instance
                nonce, encrypted_bytes = encryptor.encrypt_message(
                    message=msg_obj.body, message_id=msg_obj.id_serialized
                )
                # Convert bytes to base64 string for JSON/DB storage
                msg_obj.body = KeyManager.encode_key_for_storage(encrypted_bytes)
                msg_obj.encryption_nonce = KeyManager.encode_key_for_storage(nonce)  # type: ignore[assignment]

            return await func(*args, **kwargs)

        return register

    return decorator
