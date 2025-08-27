import asyncio

import pytest

pytestmark = pytest.mark.integration


def test_postgres_connection(request):
    try:
        dsn = request.getfixturevalue("postgres_dsn")
    except pytest.FixtureLookupError:
        pytest.skip("postgres_dsn fixture not provided")

    try:
        import psycopg2
    except Exception:
        psycopg2 = None
    try:
        import asyncpg
    except Exception:
        asyncpg = None

    if psycopg2 is None and asyncpg is None:
        pytest.skip("psycopg2 or asyncpg is required for this test")

    if psycopg2 is not None:
        try:
            conn = psycopg2.connect(dsn, connect_timeout=1)
        except Exception:
            pytest.skip("psycopg2 could not connect")
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
        conn.close()
        return

    async def _check_asyncpg():
        try:
            conn = await asyncpg.connect(dsn, timeout=1)
        except Exception:
            pytest.skip("asyncpg could not connect")
        val = await conn.fetchval("SELECT 1")
        assert val == 1
        await conn.close()

    asyncio.run(_check_asyncpg())
