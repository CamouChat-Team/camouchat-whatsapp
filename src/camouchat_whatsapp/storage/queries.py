"""
This gives all the message retrieval, check, update queries for DB.
"""

import base64 as _b64
from datetime import datetime
from typing import Any

from camouchat_browser import ProfileInfo
from camouchat_core import MessageDecryptor, MessageProtocol, MessageType
from sqlalchemy import func, select, text

from .models import Message
from .sqlalchemy_storage import SQLAlchemyStorage


class Query:
    def __init__(self, profile: ProfileInfo) -> None:
        self.profile = profile
        self.storage = SQLAlchemyStorage.from_profile(profile=profile)

    async def get_all_messages(self) -> list[Message]:
        """
        Returns all messages.
        """
        async with self.storage._get_session_factory()() as session:
            result = await session.execute(select(Message))
            return list(result.scalars().all())

    async def is_msgs_exist(
        self, messages: list[MessageProtocol] | MessageProtocol
    ) -> bool | list[bool]:
        """
        Checks if messages are already existing in DB.
        :param messages: either a single MessageProtocol or list of MessageProtocol
        :return: True if all messages exist, False otherwise. If list is passed then returns list of booleans.
        """
        is_single = False
        if not isinstance(messages, list):
            messages = [messages]
            is_single = True

        msg_ids = [m.id_serialized for m in messages if hasattr(m, "id_serialized")]
        if not msg_ids:
            return False if is_single else []

        async with self.storage._get_session_factory()() as session:
            stmt = select(Message.id_serialized).where(Message.id_serialized.in_(msg_ids))
            result = await session.execute(stmt)
            existing_ids = set(result.scalars().all())

        bool_list = [m_id in existing_ids for m_id in msg_ids]
        return bool_list[0] if is_single else bool_list

    async def custom_query(
        self, query: str, param: tuple | dict | list | None = None
    ) -> list[Any] | Any:
        """To run any custom specific raw SQL query."""
        async with self.storage._get_session_factory()() as session:
            stmt = text(query)
            if param is not None:
                result = await session.execute(stmt, param)
            else:
                result = await session.execute(stmt)
            return result.fetchall()

    async def total_messages(self) -> int:
        """return length of messages in DB"""
        async with self.storage._get_session_factory()() as session:
            result = await session.execute(select(func.count(Message.id_serialized)))
            return result.scalar() or 0

    async def get_messages_between_dates(
        self, start_date: datetime, end_date: datetime | None = None, encrypted: bool = False
    ) -> list[Message]:
        """
        return messages between start_date and end_date (including both).
        if end_date is None then messages from start_date to last available date.
        """
        async with self.storage._get_session_factory()() as session:
            start_ts = start_date.timestamp()
            stmt = select(Message).where(Message.timestamp >= start_ts)

            if end_date is not None:
                end_ts = end_date.timestamp()
                stmt = stmt.where(Message.timestamp <= end_ts)

            if encrypted:
                stmt = stmt.where(Message.encryption_nonce.is_not(None))
            else:
                stmt = stmt.where(Message.encryption_nonce.is_(None))

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_all_messages_id_serialized(self, encrypted: bool = False) -> list[str]:
        """
        Returns all messages id_serialized
        by default `encrypted` is False so it will return all non-encrypted messages
        """
        async with self.storage._get_session_factory()() as session:
            stmt = select(Message.id_serialized)

            if encrypted:
                stmt = stmt.where(Message.encryption_nonce.is_not(None))
            else:
                stmt = stmt.where(Message.encryption_nonce.is_(None))

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_all_message_type(self, msgtype: MessageType | str) -> list[Message]:
        """return all messages with this msgtype"""
        msg_type_str = msgtype.value if isinstance(msgtype, MessageType) else str(msgtype)
        async with self.storage._get_session_factory()() as session:
            stmt = select(Message).where(Message.msgtype == msg_type_str)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_all_messages_from_me(self, fromme: bool) -> list[Message]:
        """on True, returns from_me all messages else all messages with not fromme"""
        async with self.storage._get_session_factory()() as session:
            stmt = select(Message).where(Message.fromMe == fromme)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_messages_by_chat(
        self, chat_id: str, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        """Get messages filtered by chat id with pagination."""
        async with self.storage._get_session_factory()() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.id.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_messages_by_ids_async(self, message_ids: list[str]) -> list[Message]:
        """Retrieve specific messages by their serialized IDs."""
        if not message_ids:
            return []
        async with self.storage._get_session_factory()() as session:
            stmt = select(Message).where(Message.id_serialized.in_(message_ids))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_distinct_chat_ids(self) -> list[str]:
        """Return a list of all distinct chat_ids stored in the database."""
        async with self.storage._get_session_factory()() as session:
            stmt = select(Message.chat_id).distinct()
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search_messages_by_text(self, text_query: str, limit: int = 100) -> list[Message]:
        """Search for messages containing the text_query (case-insensitive if supported)."""
        async with self.storage._get_session_factory()() as session:
            # Using ilike for case-insensitive search
            stmt = (
                select(Message)
                .where(Message.body.ilike(f"%{text_query}%"))
                .order_by(Message.id.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_message_for_chat(self, chat_id: str) -> Message | None:
        """Get the most recent message for a specific chat_id."""
        async with self.storage._get_session_factory()() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_messages_by_ids(self, message_ids: list[str]) -> int:
        """Delete messages by their serialized IDs. Returns the number of deleted rows."""
        from sqlalchemy import delete

        if not message_ids:
            return 0

        async with self.storage._get_session_factory()() as session:
            stmt = delete(Message).where(Message.id_serialized.in_(message_ids))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def get_decrypted_messages_async(
        self,
        key: bytes,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Fetch all messages and decrypt body + chat name on-the-fly.
        """

        async with self.storage._get_session_factory()() as session:
            stmt = select(Message).order_by(Message.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            messages = result.scalars().all()

        decryptor = MessageDecryptor(key)
        result_list = []

        for msg in messages:
            out = msg.to_dict()
            enc_nonce = out.get("encryption_nonce")
            if enc_nonce and out.get("body"):
                try:
                    nonce_bytes = _b64.b64decode(enc_nonce)
                    cipher_bytes = _b64.b64decode(out["body"])
                    msg_id = out.get("id_serialized", "")
                    out["body"] = decryptor.decrypt_message(
                        nonce_bytes, cipher_bytes, msg_id or None
                    )
                except Exception as e:
                    self.storage.log.warning(
                        f"Failed to decrypt message {out.get('id_serialized')}: {e}"
                    )
                    out["body"] = "<decryption failed>"
            result_list.append(out)

        return result_list
