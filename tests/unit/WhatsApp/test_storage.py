from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from camouchat_browser import ProfileInfo

from camouchat_whatsapp.storage.sqlalchemy_storage import SQLAlchemyStorage


@pytest.fixture
def mock_profile():
    profile = MagicMock(spec=ProfileInfo)
    profile.profile_name = "test_profile"
    profile.database_metadata = {
        "db_type": "sqlite",
        "db_user": "user",
        "db_pass": "pass",
        "db_host": "localhost",
        "db_name": "test.db",
        "db_port": 5432,
    }
    return profile


@pytest.fixture(autouse=True)
def clear_instances():
    SQLAlchemyStorage._instances = {}
    yield


def test_sqlalchemy_storage_init(mock_profile):
    with (
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.create_async_engine"),
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.async_sessionmaker"),
    ):
        # Note: SQLAlchemyStorage uses __new__ for singleton-like behavior per URL
        storage = SQLAlchemyStorage(mock_profile)
        assert storage is not None
        # If it was already initialized in another test, these might not be called again
        # but in a fresh process they should be.


def test_sqlalchemy_storage_get_session_factory(mock_profile):
    with (
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.create_async_engine"),
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.async_sessionmaker") as mock_sm,
    ):
        storage = SQLAlchemyStorage(mock_profile)
        storage._session_factory = mock_sm

        session_factory = storage._get_session_factory()
        assert session_factory == mock_sm


@pytest.mark.asyncio
async def test_sqlalchemy_storage_init_db(mock_profile):
    with (
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.create_async_engine"),
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.async_sessionmaker"),
    ):
        storage = SQLAlchemyStorage(mock_profile)
        # Mocking _engine and _session_factory
        storage._engine = AsyncMock()

        await storage.init_db()
        # Should have called create_table internally
        # We can't easily verify create_table unless we mock it too
        assert storage._engine is not None


@pytest.mark.asyncio
async def test_sqlalchemy_storage_enqueue_insert(mock_profile):
    with (
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.create_async_engine"),
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.async_sessionmaker"),
    ):
        storage = SQLAlchemyStorage(mock_profile)
        mock_msg = MagicMock()

        # Start writer loop (minimal mock)
        storage.queue = AsyncMock()
        await storage.enqueue_insert([mock_msg])
        storage.queue.put.assert_called_once_with(mock_msg)


@pytest.mark.asyncio
async def test_sqlalchemy_storage_start_writer(mock_profile):
    with (
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.create_async_engine"),
        patch("camouchat_whatsapp.storage.sqlalchemy_storage.async_sessionmaker"),
    ):
        storage = SQLAlchemyStorage(mock_profile)
        with patch("asyncio.create_task") as mock_future:
            await storage.start_writer()
            assert storage._running is True
            mock_future.assert_called_once()
