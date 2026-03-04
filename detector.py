"""
detector.py — Rule-based transaction anomaly detector.

Each detection rule is a self-contained private method.  New rules can be added
by following the same pattern and registering them in _RULES inside __init__.
"""

import os
import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Data-classes                                                        #
# ------------------------------------------------------------------ #

@dataclass
class AnomalyResult:
    anomaly_type: str
    severity: str
    description: str


@dataclass
class TransactionContext:
    """Pre-parsed view of a raw transaction dict for convenience."""
    tx_hash: str
    value_eth: float
    gas_price_gwei: float
    gas: int
    from_address: str
    to_address: str


# ------------------------------------------------------------------ #
#  Severity ranking helper                                             #
# ------------------------------------------------------------------ #
_SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


# ------------------------------------------------------------------ #
#  Detector class                                                      #
# ------------------------------------------------------------------ #

class AnomalyDetector:
    """
    Evaluates Ethereum transactions against a set of detection rules.
    Rules are configurable via environment variables; sane defaults apply.
    """

    def __init__(self) -> None:
        self._high_value_eth    = float(os.getenv("HIGH_VALUE_THRESHOLD",    100))
        self._high_gas_gwei     = float(os.getenv("HIGH_GAS_PRICE_THRESHOLD", 500))
        self._high_gas_limit    = int(os.getenv("HIGH_GAS_LIMIT",       5_000_000))

        # Register rules in one place — easy to extend
        self._rules: List[Callable[[TransactionContext], Optional[AnomalyResult]]] = [
            self._rule_high_value,
            self._rule_high_gas_price,
            self._rule_suspicious_contract_interaction,
        ]

        logger.info(
            "AnomalyDetector ready | value≥%.0f ETH | gas≥%.0f Gwei | gas_limit≥%d",
            self._high_value_eth, self._high_gas_gwei, self._high_gas_limit,
        )

    # ---------------------------------------------------------------- #
    #  Detection rules                                                   #
    # ---------------------------------------------------------------- #

    def _rule_high_value(self, ctx: TransactionContext) -> Optional[AnomalyResult]:
        if ctx.value_eth >= self._high_value_eth:
            return AnomalyResult(
                anomaly_type="High Value Transfer",
                severity="HIGH",
                description=(
                    f"Transfer of {ctx.value_eth:.4f} ETH exceeds threshold "
                    f"of {self._high_value_eth:.0f} ETH."
                ),
            )
        return None

    def _rule_high_gas_price(self, ctx: TransactionContext) -> Optional[AnomalyResult]:
        if ctx.gas_price_gwei >= self._high_gas_gwei:
            return AnomalyResult(
                anomaly_type="High Gas Price",
                severity="MEDIUM",
                description=(
                    f"Gas price of {ctx.gas_price_gwei:.2f} Gwei exceeds threshold "
                    f"of {self._high_gas_gwei:.0f} Gwei — possible MEV/bot activity."
                ),
            )
        return None

    def _rule_suspicious_contract_interaction(self, ctx: TransactionContext) -> Optional[AnomalyResult]:
        """Zero-value, very high gas limit → possible flash-loan or exploit."""
        if ctx.value_eth == 0 and ctx.gas >= self._high_gas_limit:
            return AnomalyResult(
                anomaly_type="Suspicious Contract Interaction",
                severity="MEDIUM",
                description=(
                    f"Zero ETH transferred but gas limit is {ctx.gas:,} — "
                    "possibly a flash loan, complex exploit, or contract deployment."
                ),
            )
        return None

    # ---------------------------------------------------------------- #
    #  Public API                                                        #
    # ---------------------------------------------------------------- #

    def analyze_transaction(self, tx: dict) -> Optional[dict]:
        """
        Run all rules against a formatted transaction dict.

        Returns a single aggregated anomaly dict  (keys: tx_hash, anomaly_type,
        severity, description) or None when the transaction looks normal.
        """
        ctx = TransactionContext(
            tx_hash        = tx.get("hash", "Unknown"),
            value_eth      = tx.get("value_eth", 0.0),
            gas_price_gwei = tx.get("gas_price_gwei", 0.0),
            gas            = tx.get("gas", 0),
            from_address   = tx.get("from", "Unknown"),
            to_address     = tx.get("to",   "Unknown"),
        )

        hits: List[AnomalyResult] = [
            result for rule in self._rules
            for result in [rule(ctx)] if result is not None
        ]

        if not hits:
            return None

        # Aggregate multiple triggered rules into one record
        top_severity = max(hits, key=lambda r: _SEVERITY_RANK[r.severity]).severity
        return {
            "tx_hash":      ctx.tx_hash,
            "anomaly_type": " + ".join(h.anomaly_type for h in hits),
            "severity":     top_severity,
            "description":  " | ".join(h.description for h in hits),
        }
