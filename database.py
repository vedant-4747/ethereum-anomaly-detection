"""
database.py — PostgreSQL database layer for Ethereum On-chain Anomaly Detection.

Uses psycopg2 with a conservative connection pool (max 5) safe for Supabase free tier.
Includes automatic reconnection on stale connections.
"""

import os
import logging
import time
from typing import List, Dict, Any
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import pool, OperationalError
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL environment variable is not set.\n"
        "Add it to your .env file:\n"
        "  DATABASE_URL=postgresql://user:password@host:5432/dbname"
    )

# Supabase free tier allows ~15 connections total across ALL services.
# Keep pool small so monitor + dashboard can coexist safely.
_pool: pool.ThreadedConnectionPool | None = None
_POOL_MIN = 1
_POOL_MAX = 5   # conservative — leaves headroom for dashboard connections


def _create_pool() -> pool.ThreadedConnectionPool:
    return pool.ThreadedConnectionPool(
        _POOL_MIN, _POOL_MAX, DATABASE_URL, sslmode="require",
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = _create_pool()
        logger.info("Database connection pool initialized (min=%d, max=%d).", _POOL_MIN, _POOL_MAX)


@contextmanager
def get_connection():
    """Return a managed connection from the thread-safe pool.
    Transparently recreates the pool if it has been closed or corrupted."""
    global _pool
    if _pool is None:
        init_pool()

    conn = None
    retries = 3
    for attempt in range(retries):
        try:
            conn = _pool.getconn()
            # Test the connection is still alive
            conn.cursor().execute("SELECT 1")
            break
        except (OperationalError, psycopg2.InterfaceError) as exc:
            logger.warning("Stale connection (attempt %d/%d): %s — resetting pool.", attempt + 1, retries, exc)
            # close the bad connection and recreate the pool
            try:
                if conn:
                    _pool.putconn(conn, close=True)
            except Exception:
                pass
            try:
                _pool.closeall()
            except Exception:
                pass
            _pool = _create_pool()
            time.sleep(1)
            conn = _pool.getconn()

    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            _pool.putconn(conn)
        except Exception:
            pass


def init_db() -> None:
    """Create the anomalies table and indexes if they do not already exist."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS anomalies (
                        id              SERIAL PRIMARY KEY,
                        tx_hash         TEXT UNIQUE NOT NULL,
                        block_number    INTEGER     NOT NULL,
                        from_address    TEXT,
                        to_address      TEXT,
                        value_eth       REAL,
                        gas_price_gwei  REAL,
                        anomaly_type    TEXT        NOT NULL,
                        severity        TEXT        NOT NULL,
                        description     TEXT,
                        timestamp       TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_block_number ON anomalies(block_number);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_timestamp    ON anomalies(timestamp DESC);"
                )
            conn.commit()
            logger.info("Database initialized successfully.")
        except Exception as exc:
            conn.rollback()
            logger.error("init_db failed: %s", exc)
            raise


def insert_anomaly(
    tx_hash: str, block_number: int, from_address: str, to_address: str,
    value_eth: float, gas_price_gwei: float,
    anomaly_type: str, severity: str, description: str,
) -> None:
    """Insert a single anomaly; silently skip if tx_hash already exists."""
    insert_anomalies([{
        "tx_hash": tx_hash, "block_number": block_number,
        "from_address": from_address, "to_address": to_address,
        "value_eth": value_eth, "gas_price_gwei": gas_price_gwei,
        "anomaly_type": anomaly_type, "severity": severity,
        "description": description,
    }])


def insert_anomalies(anomalies: List[Dict[str, Any]]) -> None:
    """Batch-insert anomalies; rows with duplicate tx_hash are silently skipped."""
    if not anomalies:
        return

    sql = """
        INSERT INTO anomalies
            (tx_hash, block_number, from_address, to_address,
             value_eth, gas_price_gwei, anomaly_type, severity, description)
        VALUES
            (%(tx_hash)s, %(block_number)s, %(from_address)s, %(to_address)s,
             %(value_eth)s, %(gas_price_gwei)s, %(anomaly_type)s, %(severity)s, %(description)s)
        ON CONFLICT (tx_hash) DO NOTHING
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, anomalies, page_size=100)
        conn.commit()
    logger.info("Inserted %d anomalies (duplicates skipped).", len(anomalies))


def get_recent_anomalies(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent anomalies as a list of dicts."""
    with get_connection() as conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM anomalies ORDER BY timestamp DESC LIMIT %s",
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("get_recent_anomalies failed: %s", exc)
            return []


def get_stats() -> Dict[str, Any]:
    """Return total anomaly count and a breakdown by type."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM anomalies")
                total = cur.fetchone()[0]

                cur.execute(
                    "SELECT anomaly_type, COUNT(*) FROM anomalies GROUP BY anomaly_type"
                )
                by_type = dict(cur.fetchall())

            return {"total_anomalies": total, "anomalies_by_type": by_type}
        except Exception as exc:
            logger.error("get_stats failed: %s", exc)
            return {"total_anomalies": 0, "anomalies_by_type": {}}


def get_latest_block() -> int:
    """Return the highest block_number stored in the DB (0 if none)."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(block_number) FROM anomalies")
                result = cur.fetchone()[0]
                return result or 0
        except Exception as exc:
            logger.error("get_latest_block failed: %s", exc)
            return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database ready.")
