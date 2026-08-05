"""
Fetch live prices and append a snapshot, for the scheduled GitHub Action.

Why this exists rather than relying on the app's button:

Streamlit Cloud's filesystem is ephemeral. A snapshot written by the deployed
app vanishes on the next container restart, so the chain of price links can
never accumulate there — the same dead end that left the Amazon basket with no
history for months.

A GitHub Action can commit back to the repo, which is where this system keeps
its data. Running the fetchers here means the chain grows whether or not anyone
opens the app, and each link is one day long rather than however long it
happened to be between two visitors pressing a button.

Exit codes, matching the other refresh scripts:
    0 -> a snapshot was appended (workflow should commit)
    1 -> no source returned data (nothing to commit, not an error worth an issue)
    2 -> unexpected failure
"""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_live_prices")

EXIT_APPENDED = 0
EXIT_NO_DATA = 1
EXIT_FAIL = 2


def main() -> int:
    try:
        from engine.live_index import ANCHOR_MONTH, compute_live_index
        from engine.live_sources import chained_relatives, fetch_all, load_snapshots, save_snapshot
    except Exception:
        traceback.print_exc()
        return EXIT_FAIL

    try:
        prices = fetch_all()
    except Exception as exc:
        log.error(f"fetch failed: {exc}")
        traceback.print_exc()
        return EXIT_FAIL

    if not prices:
        log.warning("no source returned data — nothing appended")
        return EXIT_NO_DATA

    for division, items in prices.items():
        log.info(f"{division}: {len(items)} item(s)")

    save_snapshot(prices)
    snapshots = load_snapshots()
    log.info(f"appended snapshot #{len(snapshots)}")

    # Measure the bullion move INTO the month we are estimating. Back-dated,
    # because gold has a public daily history and our own snapshots do not
    # reach back that far. Done here rather than in the app so no page load
    # ever waits on it.
    try:
        from engine.live_index import ANCHOR_MONTH as anchor
        from scrapers.metals_history import measured_bullion_mom, save_measured

        year, month = (int(x) for x in anchor.split("-"))
        target = f"{year + 1:04d}-01" if month == 12 else f"{year:04d}-{month + 1:02d}"
        measured = measured_bullion_mom(anchor, target)
        if measured:
            save_measured(measured)
            log.info(
                f"measured bullion {anchor}->{target}: {measured['mom_pct']:+.3f}% "
                f"(Rs {measured['from_inr_per_gram']:,.2f} -> "
                f"{measured['to_inr_per_gram']:,.2f} per gram)"
            )
        else:
            log.warning("bullion move could not be measured this run")
    except Exception as exc:
        log.warning(f"bullion measurement skipped: {exc}")

    # Report what the chain now says, so the workflow log carries the reading
    # rather than only the fact that something was written.
    relatives = chained_relatives(snapshots)
    if relatives:
        live = compute_live_index(relatives)
        log.info(
            f"live index {live.index} vs anchor {live.anchor_index} "
            f"({live.pct_change_since_anchor:+.3f}% since {ANCHOR_MONTH}), "
            f"{live.observed_weight:.2f}% of basket repriced"
        )
    else:
        log.info("first snapshot — reference established, nothing measured yet")

    return EXIT_APPENDED


if __name__ == "__main__":
    sys.exit(main())
