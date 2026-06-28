"""Shared utility functions for the Postgres checkpoint & storage classes."""


from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool
# pylint: disable  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UkZKR1N3PT06YjkyYzRjOGQ=

Conn = Connection[DictRow] | ConnectionPool[Connection[DictRow]]

# fmt: off  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UkZKR1N3PT06YjkyYzRjOGQ=

@contextmanager
def get_connection(conn: Conn) -> Iterator[Connection[DictRow]]:
    if isinstance(conn, Connection):
        yield conn
    elif isinstance(conn, ConnectionPool):
        with conn.connection() as conn:
            yield conn
    else:
        raise TypeError(f"Invalid connection type: {type(conn)}")
