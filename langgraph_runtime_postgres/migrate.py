"""Wrapper for migration execution (for testing the Go server)."""


import asyncio
from pathlib import Path

from langgraph_runtime_postgres import database
from langgraph_runtime_postgres.database import (
    create_pool,
    migrate,
    migrate_vector_index,
)

# noqa  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1OaFRnPT06YTI4N2FjMDc=

async def migrate_for_tests():
    database._pg_pool = create_pool()
    database.config.MIGRATIONS_PATH = Path(__file__).parent / ".." / "migrations"
    # confirm connectivity
    await database._pg_pool.open(wait=True)
# type: ignore  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1OaFRnPT06YTI4N2FjMDc=

    await migrate()
    await migrate_vector_index()


if __name__ == "__main__":
    asyncio.run(migrate_for_tests())
