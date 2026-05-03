"""
Generic SQLAlchemy storage implementation supporting multiple databases.
Uses async operations for non-blocking performance.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Sequence
from logging import Logger, LoggerAdapter
from typing import Any

from camouchat_browser import DirectoryManager, ProfileInfo
from camouchat_core import MessageProtocol, MessageType, StorageProtocol
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from camouchat_whatsapp.exceptions import WhatsAppStorageError

from ..logger import w_logger
from .models import Base, Message


class SQLAlchemyStorage(StorageProtocol):
    """
    Generic SQLAlchemy storage implementation for MessageProtocol data.

    Features:
    - Async queue-based batch insertion
    - Background writer task for performance
    - Support for SQLite, PostgreSQL, MySQL via connection string
    - Generic message storage (works with any MessageProtocol implementation)

    Connection string examples:
    - SQLite: sqlite+aiosqlite:///path/to/messages.db
    - PostgreSQL: postgresql+asyncpg://user:pass@host/db
    - MySQL: mysql+aiomysql://user:pass@host/db
    """

    _instances: dict[str, SQLAlchemyStorage] = {}
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> SQLAlchemyStorage:
        db_credentials = kwargs.get("db_credentials") or (args[1] if len(args) > 1 else {})
        key = cls._build_database_url(db_credentials)
        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(
        self,
        profile: ProfileInfo,
        queue: asyncio.Queue | None = None,
        db_credentials: dict | None = None,
        log: Logger | LoggerAdapter | None = None,
        batch_size: int = 50,
        flush_interval: float = 2.0,
        echo: bool = False,
    ) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        """
        Initialize SQLAlchemy storage.

        Args:
            queue: Async queue for message batching (created automatically if None)
            db_credentials: DB credential dict
                (storage_type, username, password, host, port, database_name, database_path)
            log: Logger instance
            batch_size: Max messages before auto-flush
            flush_interval: Seconds before auto-flush even if batch not full
            echo: Enable SQL query logging (for debugging)
        """
        self.profile = profile
        self.queue: asyncio.Queue = queue if queue is not None else asyncio.Queue()
        self.log = log or w_logger
        self.db_credentials: dict = db_credentials or {}
        self._initialized = True
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.echo = echo

        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._writer_task: asyncio.Task | None = None
        self._running = False
        self._flush_event = asyncio.Event()
        self._initialized_ = False

    @staticmethod
    def _build_database_url(db_credentials: dict) -> str:
        """
        Build SQLAlchemy-compatible URL from db_credentials dict.

        Uses sqlalchemy.engine.URL.create() for safe dialect construction.
        Falls back to SQLite default if storage_type is missing or sqlite.
        """
        from sqlalchemy.engine import URL

        storage_type = db_credentials.get("storage_type") or "sqlite"
        storage_type = storage_type.lower().replace("storagetype.", "")

        if storage_type == "sqlite":
            db_path = db_credentials.get("database_path")
            # str(None) from from_profile becomes "None" — treat as missing
            if not db_path or db_path == "None":
                from camouchat_browser import DirectoryManager

                platform = db_credentials.get("platform")
                profile_id = db_credentials.get("profile_id")
                if platform and profile_id:
                    db_path = str(DirectoryManager().get_database_path(platform, profile_id))
                else:
                    db_path = "messages.db"
            return f"sqlite+aiosqlite:///{db_path}"

        driver_map = {
            "postgresql": "postgresql+asyncpg",
            "mysql": "mysql+aiomysql",
        }
        dialect = driver_map.get(storage_type, f"{storage_type}+asyncpg")

        url = URL.create(
            drivername=dialect,
            username=db_credentials.get("username"),
            password=db_credentials.get("password"),
            host=db_credentials.get("host", "localhost"),
            port=db_credentials.get("port"),
            database=db_credentials.get("database_name"),
        )
        return str(url)

    @classmethod
    def from_profile(
        cls,
        profile: ProfileInfo,
        queue: asyncio.Queue | None = None,
        log: Logger | LoggerAdapter | None = None,
        batch_size: int = 50,
        flush_interval: float = 2.0,
    ) -> SQLAlchemyStorage:
        """
        Create storage from ProfileInfo.

        Args:
            profile: ProfileInfo from ProfileManager
            queue: Optional async queue (auto-created if None)
            log: Logger
            batch_size: Batch size
            flush_interval: Flush interval

        Returns:
            Configured SQLAlchemyStorage instance
        """
        db_credentials = {
            "storage_type": profile.db_type,
            "database_path": str(
                DirectoryManager().get_database_path(profile.platform, profile.profile_id)
            ),
            "platform": profile.platform,
            "profile_id": profile.profile_id,
            "username": profile.username,
            "password": profile.password,
            "host": profile.host,
            "port": profile.port,
            "database_name": profile.database_name,
        }

        return cls(
            profile=profile,
            queue=queue,
            log=log or w_logger,
            db_credentials=db_credentials,
            batch_size=batch_size,
            flush_interval=flush_interval,
        )

    async def init_db(self, **kwargs) -> None:
        """Initialize SQLAlchemy engine and session factory."""
        try:
            database_url = self._build_database_url(self.db_credentials)
            is_sqlite = database_url.startswith("sqlite")
            engine_kwargs: dict = {"echo": self.echo}
            if not is_sqlite:
                engine_kwargs.update(
                    {
                        "pool_recycle": 3600,
                        "pool_size": 5,
                        "max_overflow": 10,
                        "pool_timeout": 30,
                    }
                )

            self._engine = create_async_engine(database_url, **engine_kwargs)

            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False
            )

            self.log.info(f"SQLAlchemy engine initialized: {database_url}")
        except Exception as e:
            raise WhatsAppStorageError(f"Failed to initialize database: {e}") from e

    async def create_table(self, **kwargs) -> None:
        """Create tables if not exists."""
        if not self._engine:
            raise WhatsAppStorageError("Database not initialized. Call init_db() first.")

        try:
            async with self._engine.begin() as conn:  # type: ignore
                await conn.run_sync(Base.metadata.create_all)
            self.log.info("Tables created/verified.")
        except Exception as e:
            raise WhatsAppStorageError(f"Failed to create tables: {e}") from e

    async def _migrate_add_encryption_columns(self) -> None:
        """
        Safe migration for users upgrading from older versions.

        SQLAlchemy's create_all() only creates missing tables — it does NOT add
        new columns to existing tables. Users who already have a messages.db
        would get OperationalError without this migration.

        Uses 'ALTER TABLE ... ADD COLUMN' with silent error swallowing because
        SQLite does not support 'IF NOT EXISTS' on ADD COLUMN (pre-3.37.0).
        """
        from sqlalchemy import text

        migration_sqls = [
            "ALTER TABLE messages ADD COLUMN encryption_nonce VARCHAR(255)",
            "ALTER TABLE messages ADD COLUMN meta_data JSON",
        ]
        if not self._engine:
            return

        async with self._engine.begin() as conn:  # type: ignore
            for sql in migration_sqls:
                try:
                    await conn.execute(text(sql))
                    self.log.debug(f"Migration applied: {sql}")
                except Exception:
                    pass  # Column already exists — expected on fresh installs

    async def start_writer(self, **kwargs) -> None:
        """Start background task to consume queue and write batches."""
        if self._writer_task and not self._writer_task.done():
            self.log.warning("Writer task already running.")
            return

        self._running = True
        self._flush_event.clear()
        self._writer_task = asyncio.create_task(self._writer_loop())
        self.log.info("Background writer started.")

    async def flush(self) -> None:
        """Force an immediate flush of the batch queue."""
        if not self._running:
            return
        self._flush_event.set()
        await self.queue.put([])  # Wake up queue.get() immediately

    async def _writer_loop(self) -> None:
        """Background loop that consumes queue and writes batches."""
        batch: list[MessageProtocol] = []
        last_flush = asyncio.get_event_loop().time()

        while self._running:
            try:
                now = asyncio.get_event_loop().time()
                time_since_flush = now - last_flush
                time_to_wait = max(0.1, self.flush_interval - time_since_flush)

                try:
                    msg = await asyncio.wait_for(self.queue.get(), timeout=time_to_wait)

                    if msg is None:  # Shutdown sentinel
                        self.queue.task_done()
                        break

                    if isinstance(msg, list):
                        if msg:  # Ignore empty lists used as flush wakeups
                            batch.extend(msg)
                    else:
                        batch.append(msg)

                    self.queue.task_done()
                except TimeoutError:
                    pass

                if not self._running:
                    break

                current_time = asyncio.get_event_loop().time()
                should_flush = (
                    len(batch) >= self.batch_size
                    or (batch and (current_time - last_flush) >= self.flush_interval)
                    or self._flush_event.is_set()
                )

                if should_flush and batch:
                    await self._insert_batch_internally(batch)
                    batch.clear()
                    last_flush = current_time
                    self._flush_event.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Writer loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

        # Flush remaining messages on shutdown
        if batch:
            await self._insert_batch_internally(batch)

    async def enqueue_insert(
        self, msgs: Sequence[MessageProtocol] | MessageProtocol, **kwargs
    ) -> None:
        """
        Add messages to queue for batch insertion.

        Parameters
        ----------
        msgs : Sequence[MessageProtocol] | MessageProtocol
            Messages to insert.
        **kwargs : dict
            Optional arguments.
        min_insert_time : float, optional
            Minimum time to wait before inserting the messages.
            If -1, the default flush interval is used.
            we can change the flush interval via this runtime flag too.
        """
        min_insert_time: float = kwargs.get("min_insert_time", -1)
        if min_insert_time >= 0:
            self.flush_interval = min_insert_time

        if not msgs:
            return

        if isinstance(msgs, MessageProtocol):
            msgs = [msgs]

        for msg in msgs:
            await self.queue.put(msg)

        self.log.debug(f"Enqueued {len(msgs)} messages for insertion.")

    async def _insert_batch_internally(self, msgs: Sequence[MessageProtocol], **kwargs) -> None:
        """Insert batch of messages into database."""
        if not self._session_factory:
            raise WhatsAppStorageError("Database not initialized.")

        if not msgs:
            return

        # Convert messages to Message models
        message_models = []
        for msg in msgs:
            try:
                model = SQLAlchemyStorage._message_to_model(msg=msg)
                message_models.append(model)
            except Exception as e:
                self.log.warning(f"Failed to convert message: {e}")
                continue

        if not message_models:
            return

        # Insert batch
        session_factory = self._session_factory
        if session_factory is None:
            raise WhatsAppStorageError("Database not initialized.")

        session_factory = self._get_session_factory()
        async with session_factory() as session:
            try:
                session.add_all(message_models)
                await session.commit()
                self.log.debug(f"Inserted {len(message_models)} messages.")
            except IntegrityError:
                await session.rollback()
                success_count = 0
                for model in message_models:
                    try:
                        session_factory = self._get_session_factory()
                        async with session_factory() as single_session:
                            single_session.add(model)
                            await single_session.commit()
                            success_count += 1
                    except IntegrityError:
                        continue  # Skip duplicate
                    except Exception as e:
                        self.log.warning(f"Failed to insert message {model.id_serialized}: {e}")

                self.log.debug(
                    f"Inserted {success_count}/{len(message_models)} messages (some duplicates)."
                )
            except Exception as e:
                await session.rollback()
                self.log.error(f"Batch insert failed: {e}", exc_info=True)
                raise WhatsAppStorageError(f"Batch insert failed: {e}") from e

    @staticmethod
    def _message_to_model(msg: MessageProtocol) -> Message:
        """Convert any MessageProtocol implementation to unified Message DB model."""
        msg_id = getattr(msg, "id_serialized", "unknown")
        body = getattr(msg, "body", "")
        msgtype = getattr(msg, "msgtype", None)
        fromme = getattr(msg, "fromMe", None)
        timestamp = getattr(msg, "timestamp", 0.0)
        encryption_nonce = getattr(msg, "encryption_nonce", None)
        chat_id = getattr(msg, "jid_From", "")
        if not chat_id:
            from_chat = getattr(msg, "from_chat", None)
            if from_chat:
                chat_id = getattr(from_chat, "id_serialized", "")

        meta_data = None
        if hasattr(msg, "to_dict"):
            with contextlib.suppress(Exception):
                meta_data = msg.to_dict()

        if encryption_nonce is not None:
            msgtype = MessageType.CAMOU_CIPHERTEXT

        return Message(
            id_serialized=str(msg_id),
            body=str(body) if body else "",
            encryption_nonce=encryption_nonce,
            msgtype=str(msgtype) if msgtype else None,
            fromMe=fromme,
            chat_id=str(chat_id),
            meta_data=meta_data,
            timestamp=float(timestamp),
        )

    def _get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise WhatsAppStorageError("Database not initialized.")
        return self._session_factory

    async def close_db(self, **kwargs) -> None:
        """Close connection and stop writer."""
        self._running = False
        await self.queue.put(None)  # Wake up queue.get() for instant shutdown

        if self._writer_task:
            try:
                await asyncio.wait_for(self._writer_task, timeout=2.0)
            except TimeoutError:
                self.log.warning("Writer task shutdown timed out, cancelling.")
                self._writer_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._writer_task
            self._writer_task = None

        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self.log.info("Database connection closed.")

    async def start(self, **kwargs) -> None:
        """Start database and background writer."""
        if self._initialized_:
            return
        else:
            self._initialized_ = True
            await self.init_db()
            await self.create_table()
            await self._migrate_add_encryption_columns()
            await self.start_writer()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_db()
        return False

    async def get_all_messages_async(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Retrieve all messages from storage asynchronously."""
        factory = self._get_session_factory()
        from sqlalchemy import select

        async with factory() as session:
            stmt = select(Message).order_by(Message.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    async def check_message_if_exists_async(self, msg_id: str, **kwargs) -> bool:
        """Check if a message exists by ID asynchronously."""
        factory = self._get_session_factory()
        from sqlalchemy import select

        async with factory() as session:
            stmt = select(Message.id_serialized).where(Message.id_serialized == msg_id)
            result = await session.execute(stmt)
            return result.scalar() is not None

    async def get_messages_by_chat(
        self, chat_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get messages filtered by chat id with pagination."""
        factory = self._get_session_factory()
        from sqlalchemy import select

        async with factory() as session:
            stmt = (
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.id.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [msg.to_dict() for msg in messages]

    def check_message_if_exists(self, msg_id: str, **kwargs) -> bool:
        """Check if a message exists by ID (sync - not recommended)."""
        # This is just to satisfy the protocol if needed, but it might not work well with async engine
        raise NotImplementedError("Use check_message_if_exists_async")

    def get_all_messages(self, **kwargs) -> list[dict[str, Any]]:
        """Retrieve all messages from storage (sync - not recommended)."""
        raise NotImplementedError("Use get_all_messages_async")
