"""
Persistent storage backends for camouchat.

Handles message caching, session persistence, and local data storage
using SQLAlchemy ORM with support for SQLite, PostgreSQL, and MySQL.
"""

from .sqlalchemy_storage import SQLAlchemyStorage
from .storage_type import StorageType

__all__ = ["SQLAlchemyStorage", "StorageType"]
