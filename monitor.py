"""
monitor.py — Ethereum blockchain real-time anomaly monitoring engine.

Connects to a configured RPC endpoint, polls for new blocks, formats every
transaction, and delegates analysis to AnomalyDetector.  Detected anomalies
are persisted to SQLite via the database module.
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

# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _build_web3() -> Web3:
    """Return a connected Web3 instance; exit on failure."""
    w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))
    if not w3.is_connected():
        logger.critical("Cannot connect to Ethereum RPC at %s", ETH_RPC_URL)
        raise SystemExit(1)
    logger.info("Connected to Ethereum node at %s", ETH_RPC_URL)
    return w3


def _format_tx(w3: Web3, raw_tx) -> dict | None:
    """Convert a raw transaction object into a plain dict, or None on error."""
    try:
        value_wei      = raw_tx.get("value", 0) or 0
        gas_price_wei  = raw_tx.get("gasPrice", 0) or 0

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
            tx = _format_tx(w3, raw_tx)
            if tx is None:
                continue

            anomaly = detector.analyze_transaction(tx)
            if anomaly is None:
                continue

            anomalies_to_insert.append({
                "tx_hash":       anomaly["tx_hash"],
                "block_number":  tx["block_number"],
                "from_address":  tx["from"],
                "to_address":    tx["to"],
                "value_eth":     tx["value_eth"],
                "gas_price_gwei":tx["gas_price_gwei"],
                "anomaly_type":  anomaly["anomaly_type"],
                "severity":      anomaly["severity"],
                "description":   anomaly["description"],
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
    w3       = _build_web3()
    detector = AnomalyDetector()
    database.init_db()

    last_processed = w3.eth.block_number
    logger.info("Starting monitor from block %d …", last_processed)

    while True:
        try:
            latest = w3.eth.block_number
            if latest > last_processed:
                blocks_to_process = list(range(last_processed + 1, latest + 1))
                # Process blocks concurrently to speed up sync
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [
                        executor.submit(process_block, w3, block_num, detector)
                        for block_num in blocks_to_process
                    ]
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as exc:
                            logger.error("Error processing block in thread: %s", exc)
                last_processed = latest
            else:
                # Ethereum block time ≈ 12 s; polling every 10 s keeps lag minimal
                time.sleep(10)

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
            break
        except Exception as exc:
            logger.error("Unexpected error in main loop: %s", exc)
            time.sleep(15)   # back-off before retrying


if __name__ == "__main__":
    main()
