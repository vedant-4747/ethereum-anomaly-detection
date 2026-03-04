"""
monitor.py — Ethereum blockchain real-time anomaly monitoring engine.

Connects to a configured RPC endpoint, polls for new blocks every 4 s,
and delegates analysis to AnomalyDetector. Detected anomalies are
persisted to PostgreSQL via the database module.

Key resilience features:
- Resumes from the DB's last known block after a restart (catches up missed blocks)
- Capped catch-up (max 200 blocks) so startup is fast after long downtime
- Automatic Web3 reconnect on RPC failures
- Conservative thread pool to avoid hammering RPC or DB
"""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from web3 import Web3
from dotenv import load_dotenv

from detector import AnomalyDetector
import database

# ------------------------------------------------------------------ #
#  Logging                                                            #
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Monitor")

# ------------------------------------------------------------------ #
#  Configuration                                                       #
# ------------------------------------------------------------------ #
load_dotenv()
ETH_RPC_URL: str = os.getenv("ETH_RPC_URL", "https://cloudflare-eth.com")

# Max blocks to catch up in one burst (prevents huge startup delay after downtime)
MAX_CATCHUP_BLOCKS = 200

# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _build_web3() -> Web3:
    """Return a connected Web3 instance; retry forever with back-off."""
    while True:
        try:
            w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 15}))
            if w3.is_connected():
                logger.info("Connected to Ethereum node at %s", ETH_RPC_URL)
                return w3
        except Exception as exc:
            logger.warning("Web3 connect failed: %s", exc)
        logger.info("Retrying RPC connection in 10 s …")
        time.sleep(10)


def _format_tx(raw_tx) -> dict | None:
    """Convert a raw transaction object into a plain dict, or None on error."""
    try:
        value_wei     = raw_tx.get("value", 0) or 0
        gas_price_wei = raw_tx.get("gasPrice", 0) or 0
        return {
            "hash":           raw_tx["hash"].hex(),
            "block_number":   raw_tx.get("blockNumber"),
            "from":           raw_tx.get("from",  "Unknown"),
            "to":             raw_tx.get("to",    "Unknown"),
            "value_eth":      float(value_wei) / 1e18,
            "gas_price_gwei": float(gas_price_wei) / 1e9,
            "gas":            raw_tx.get("gas", 0),
        }
    except Exception as exc:
        logger.warning("Failed to format transaction: %s", exc)
        return None


# ------------------------------------------------------------------ #
#  Block processing                                                    #
# ------------------------------------------------------------------ #

def process_block(w3: Web3, block_number: int, detector: AnomalyDetector) -> None:
    """Fetch a full block and run every transaction through the detector."""
    logger.info("Processing block %d …", block_number)
    try:
        block        = w3.eth.get_block(block_number, full_transactions=True)
        transactions = block.get("transactions", [])
        anomalies_to_insert = []

        for raw_tx in transactions:
            tx = _format_tx(raw_tx)
            if tx is None:
                continue

            anomaly = detector.analyze_transaction(tx)
            if anomaly is None:
                continue

            anomalies_to_insert.append({
                "tx_hash":        anomaly["tx_hash"],
                "block_number":   tx["block_number"],
                "from_address":   tx["from"],
                "to_address":     tx["to"],
                "value_eth":      tx["value_eth"],
                "gas_price_gwei": tx["gas_price_gwei"],
                "anomaly_type":   anomaly["anomaly_type"],
                "severity":       anomaly["severity"],
                "description":    anomaly["description"],
            })

        if anomalies_to_insert:
            database.insert_anomalies(anomalies_to_insert)

        logger.info(
            "Block %d done — %d txs scanned, %d anomalies found.",
            block_number, len(transactions), len(anomalies_to_insert),
        )

    except Exception as exc:
        logger.error("Error processing block %d: %s", block_number, exc)


# ------------------------------------------------------------------ #
#  Main loop                                                           #
# ------------------------------------------------------------------ #

def main() -> None:
    database.init_db()
    w3       = _build_web3()
    detector = AnomalyDetector()

    # ── Smart resume: start from the last block saved in DB so we don't skip
    # blocks that arrived while the monitor was down.  Cap at MAX_CATCHUP_BLOCKS
    # behind the current tip so we don't spend forever catching up after long downtime.
    current_tip     = w3.eth.block_number
    db_latest       = database.get_latest_block()
    resume_from     = max(db_latest, current_tip - MAX_CATCHUP_BLOCKS) if db_latest else current_tip

    last_processed  = resume_from
    last_heartbeat  = time.time()
    HEARTBEAT_EVERY = 60   # seconds

    logger.info(
        "Monitor starting. DB latest: %d | Chain tip: %d | Resuming from: %d",
        db_latest, current_tip, last_processed,
    )

    consecutive_errors = 0

    while True:
        try:
            latest = w3.eth.block_number
            if latest > last_processed:
                blocks_to_process = list(range(last_processed + 1, latest + 1))
                logger.info(
                    "New blocks detected: %d → %d (%d blocks)",
                    last_processed + 1, latest, len(blocks_to_process),
                )
                # Use 3 workers — enough parallelism without saturating the DB pool
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        executor.submit(process_block, w3, bn, detector): bn
                        for bn in blocks_to_process
                    }
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as exc:
                            logger.error("Block %d thread error: %s", futures[future], exc)

                last_processed     = latest
                last_heartbeat     = time.time()
                consecutive_errors = 0
            else:
                # Poll every 4 s — Ethereum block time ≈ 12 s → max lag ~4 s
                time.sleep(4)

            # Periodic heartbeat so the process doesn't look stuck in hosted runners
            if time.time() - last_heartbeat >= HEARTBEAT_EVERY:
                logger.info(
                    "Heartbeat ✓ — chain tip: %d, last processed: %d",
                    latest, last_processed,
                )
                last_heartbeat = time.time()

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
            break

        except Exception as exc:
            consecutive_errors += 1
            backoff = min(15 * consecutive_errors, 120)
            logger.error(
                "Unexpected error in main loop (attempt %d): %s — retrying in %d s",
                consecutive_errors, exc, backoff,
            )
            time.sleep(backoff)

            # Reconnect Web3 if too many consecutive RPC failures
            if consecutive_errors >= 3:
                logger.info("Reconnecting to Ethereum RPC …")
                try:
                    w3 = _build_web3()
                    consecutive_errors = 0
                except Exception:
                    pass


if __name__ == "__main__":
    main()
