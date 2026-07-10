"""
keepalive.py — Pings ETHWatch services with GET requests to prevent Render free-tier sleep.

Run by the eth-keepalive-cron service every 3 minutes.
Uses GET (not HEAD) so the health handler always returns 200 regardless of HTTP client.
"""

import urllib.request
import urllib.error
import sys
import os
import time

SERVICES = [
    ("eth-anomaly-dashboard", os.getenv(
        "DASHBOARD_URL", "https://eth-anomaly-dashboard.onrender.com/"
    )),
    ("eth-anomaly-monitor", os.getenv(
        "MONITOR_URL", "https://eth-anomaly-monitor.onrender.com/"
    )),
]

TIMEOUT = 28  # seconds — just under Render's 30s cron timeout


def ping(name: str, url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "ETHWatch-Keepalive/1.0")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            print(f"[OK {status}] {name} — {url}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {name} — {url} : {e.reason}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"[FAIL] {name} — {url} : {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] {name} — {url} : {e}", file=sys.stderr)
        return False


def main() -> None:
    print(f"Keep-alive ping started — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    results = [ping(name, url) for name, url in SERVICES]
    ok = sum(results)
    total = len(results)
    print(f"Keep-alive done: {ok}/{total} services reachable.")
    # Exit 1 if any service is down so Render cron logs show a failure
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
