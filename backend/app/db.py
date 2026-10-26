"""Database connection pool management with automatic local SQLite fallback.

If PostgreSQL is running, connects to PostgreSQL with pgvector support.
If PostgreSQL is offline/unavailable, seamlessly falls back to embedded SQLite
with NumPy-based cosine similarity vector search.
"""

from __future__ import annotations

import logging
import socket
from contextlib import contextmanager
from urllib.parse import urlparse

from .config import settings
from .local_db import LocalDatabasePool

logger = logging.getLogger(__name__)


def _can_reach_postgres(url: str) -> bool:
    """Fast check whether PostgreSQL port is open before initializing pool."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        socket.setdefaulttimeout(1.0)
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except Exception:
        return False


class SmartConnectionPool:
    """Connection pool proxy that routes to PostgreSQL or local SQLite."""

    def __init__(self):
        self._pg_pool = None
        self._local_pool = None
        self._use_local = not _can_reach_postgres(settings.postgres_url)
        if not self._use_local:
            self._init_pg()
        else:
            logger.info("PostgreSQL not reachable at %s. Using local SQLite vector DB.", settings.postgres_url)

    def _init_pg(self):
        try:
            from psycopg_pool import ConnectionPool
            from pgvector.psycopg import register_vector

            def _configure_connection(conn):
                register_vector(conn)

            self._pg_pool = ConnectionPool(
                settings.postgres_url,
                min_size=1,
                max_size=10,
                configure=_configure_connection,
                open=False,
            )
        except Exception as e:
            logger.warning("Postgres pool init failed: %s. Using local SQLite DB.", e)
            self._use_local = True

    def open(self):
        if not self._use_local and self._pg_pool:
            try:
                self._pg_pool.open(wait=False, timeout=1.0)
                with self._pg_pool.connection(timeout=1.0) as conn:
                    conn.execute("SELECT 1")
                logger.info("Connected to PostgreSQL successfully")
                return
            except Exception as e:
                logger.warning(
                    "Could not connect to PostgreSQL (%s). Falling back to local SQLite + NumPy vector DB.",
                    e,
                )
                self._use_local = True
                try:
                    self._pg_pool.close()
                except Exception:
                    pass

        if self._local_pool is None:
            self._local_pool = LocalDatabasePool()
        self._local_pool.open()

    def close(self):
        if not self._use_local and self._pg_pool:
            try:
                self._pg_pool.close()
            except Exception:
                pass
        if self._local_pool:
            self._local_pool.close()

    @contextmanager
    def connection(self):
        if self._use_local:
            if self._local_pool is None:
                self._local_pool = LocalDatabasePool()
            with self._local_pool.connection() as conn:
                yield conn
            return

        try:
            with self._pg_pool.connection() as conn:
                yield conn
        except Exception as e:
            logger.warning("PostgreSQL connection lost (%s). Falling back to local SQLite DB.", e)
            self._use_local = True
            if self._local_pool is None:
                self._local_pool = LocalDatabasePool()
            with self._local_pool.connection() as conn:
                yield conn


# Global pool singleton
pool = SmartConnectionPool()
