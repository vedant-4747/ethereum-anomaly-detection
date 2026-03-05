"""
monitor.py — Ethereum blockchain real-time anomaly monitoring engine.

Embeds a lightweight HTTP health server (runs in a background thread) so
Render can health-check the process and keep it alive as a Web Service.

Resilience features:
- HTTP /health endpoint on $PORT (Render Web Service health check)
- Resumes from last DB block on startup (catches up missed blocks, capped at 200)
- Web3 retries forever with exponential back-off (never exits on RPC errors)
- Conservative 3-thread pool to stay within Supabase free-tier connection limit
- 60-second heartbeat log so Render sees stdout activity
"""

import os
import time
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

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
#  Configuration                                                      #
# ------------------------------------------------------------------ #
load_dotenv()
ETH_RPC_URL:    str = os.getenv("ETH_RPC_URL", "https://cloudflare-eth.com")
HEALTH_PORT:    int = int(os.getenv("PORT", 10000))   # Render injects $PORT
MAX_CATCHUP:    int = 200   # blocks to replay after downtime

# ------------------------------------------------------------------ #
#  Health HTTP server (keeps Render Web Service alive)               #
# ------------------------------------------------------------------ #
_health_status: dict = {
    "status":         "starting",
    "last_block":     0,
    "anomalies_seen": 0,
    "uptime_s":       0,
}
_start_time: float = time.time()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({
            **_health_status,
            "uptime_s": int(time.time() - _start_time),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Silence the default per-request access log
    def log_message(self, fmt, *args):   # noqa: N802
        pass


def _start_health_server() -> None:
    """Start the health HTTP server in a daemon thread."""
    try:
        srv = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
        logger.info("Health server listening on port %d", HEALTH_PORT)
        srv.serve_forever()
    except Exception as exc:
        logger.error("Health server failed: %s", exc)


# ------------------------------------------------------------------ #
#  Web3 connection                                                    #
# ------------------------------------------------------------------ #

def _build_web3() -> Web3:
    """Return a connected Web3 instance; retry forever with back-off."""
    attempt = 0
    while True:
        try:
            w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 15}))
            if w3.is_connected():
                logger.info("Connected to Ethereum node at %s", ETH_RPC_URL)
                return w3
        except Exception as exc:
            logger.warning("Web3 connect error: %s", exc)
        attempt += 1
        wait = min(10 * attempt, 60)
        logger.info("Retrying RPC connection in %d s …", wait)
        time.sleep(wait)


# ------------------------------------------------------------------ #
#  Transaction processing                                             #
# ------------------------------------------------------------------ #

def _format_tx(raw_tx) -> Optional[dict]:
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
        logger.warning("Failed to format tx: %s", exc)
        return None


def process_block(w3: Web3, block_number: int, detector: AnomalyDetector) -> int:
    """Process one block; return number of anomalies found."""
    logger.info("Processing block %d …", block_number)
    try:
        block        = w3.eth.get_block(block_number, full_transactions=True)
        transactions = block.get("transactions", [])
        batch = []

        for raw_tx in transactions:
            tx = _format_tx(raw_tx)
            if tx is None:
                continue
            anomaly = detector.analyze_transaction(tx)
            if anomaly is None:
                continue
            batch.append({
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

        if batch:
            database.insert_anomalies(batch)

        logger.info(
            "Block %d — %d txs scanned, %d anomalies.", block_number, len(transactions), len(batch)
        )
        return len(batch)

    except Exception as exc:
        logger.error("Error processing block %d: %s", block_number, exc)
        return 0


# ------------------------------------------------------------------ #
#  Main loop                                                          #
# ------------------------------------------------------------------ #

def main() -> None:
    # Start health server in background thread FIRST — so Render's health
    # check passes immediately while the monitor warms up.
    threading.Thread(target=_start_health_server, daemon=True).start()

    database.init_db()
    w3       = _build_web3()
    detector = AnomalyDetector()

    # Smart resume: start from the last block recorded in DB so we don't
    # skip blocks that arrived while the process was down.
    current_tip    = w3.eth.block_number
    db_latest      = database.get_latest_block()
    last_processed = max(db_latest, current_tip - MAX_CATCHUP) if db_latest else current_tip

    _health_status["status"]     = "running"
    _health_status["last_block"] = last_processed

    last_heartbeat     = time.time()
    HEARTBEAT_EVERY    = 60
    consecutive_errors = 0

    logger.info(
        "Monitor ready | DB latest: %d | chain tip: %d | starting at: %d",
        db_latest, current_tip, last_processed,
    )

    while True:
        try:
            latest = w3.eth.block_number

            if latest > last_processed:
                blocks_to_process = list(range(last_processed + 1, latest + 1))
                logger.info(
                    "New blocks %d → %d (%d total)",
                    last_processed + 1, latest, len(blocks_to_process),
                )

                total_anomalies = 0
                # 3 workers: enough parallelism, stays within DB pool limit of 5
                with ThreadPoolExecutor(max_workers=3) as exe:
                    futures = {
                        exe.submit(process_block, w3, bn, detector): bn
                        for bn in blocks_to_process
                    }
                    for fut in as_completed(futures):
                        try:
                            total_anomalies += fut.result()
                        except Exception as exc:
                            logger.error("Block %d error: %s", futures[fut], exc)

                last_processed                   = latest
                last_heartbeat                   = time.time()
                consecutive_errors               = 0
                _health_status["last_block"]     = latest
                _health_status["anomalies_seen"] += total_anomalies

            else:
                # Ethereum block time ≈ 12 s — poll every 4 s
                time.sleep(4)

            # Periodic heartbeat
            if time.time() - last_heartbeat >= HEARTBEAT_EVERY:
                logger.info("Heartbeat ✓ — tip: %d, last processed: %d", latest, last_processed)
                last_heartbeat = time.time()

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
            _health_status["status"] = "stopped"
            break

        except Exception as exc:
            consecutive_errors += 1
            backoff = min(15 * consecutive_errors, 120)
            logger.error(
                "Main loop error #%d: %s — retrying in %ds", consecutive_errors, exc, backoff
            )
            _health_status["status"] = f"error ({exc})"
            time.sleep(backoff)

            if consecutive_errors >= 3:
                logger.info("Reconnecting Web3 …")
                try:
                    w3 = _build_web3()
                    consecutive_errors = 0
                    _health_status["status"] = "running"
                except Exception:
                    pass


if __name__ == "__main__":
    main()
