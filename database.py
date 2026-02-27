"""
database.py — PostgreSQL database layer for Ethereum On-chain Anomaly Detection.

Uses psycopg2. Reads DATABASE_URL from the environment (set in .env or cloud secrets).

Example DATABASE_URL:
    postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres
"""

import os
import logging
from typing import List, Dict, Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Force override=True so cached terminal variables don't ignore the .env file!
load_dotenv(override=True)

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL environment variable is not set.\n"
        "Add it to your .env file:\n"
        "  DATABASE_URL=postgresql://user:password@host:5432/dbname"
    )


def get_connection():
    """Return a live psycopg2 connection to the PostgreSQL database."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db() -> None:
    """Create the anomalies table and indexes if they do not already exist."""
    conn = get_connection()
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
    finally:
        conn.close()


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
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, anomalies, page_size=100)
        conn.commit()
        logger.info("Inserted %d anomalies (duplicates skipped).", len(anomalies))
    except Exception as exc:
        conn.rollback()
        logger.error("insert_anomalies failed: %s", exc)
    finally:
        conn.close()


def get_recent_anomalies(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent anomalies as a list of dicts."""
    conn = get_connection()
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
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    """Return total anomaly count and a breakdown by type."""
    conn = get_connection()
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
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database ready.")
