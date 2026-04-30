"""
Headless Amazon basket scraper for the GitHub Actions weekly cron.

Runs the scraper, persists kept observations to data/amazon_prices.json, and
returns an exit code the workflow uses to decide whether to commit.

Exit codes:
    0 → at least one new observation was persisted
    1 → scraper produced 0 results (Amazon likely blocked the runner)
    2 → unexpected error
"""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scrape_amazon")


def main() -> int:
    try:
        from db.schema import init_db
        from seed.amazon_persist import append_observations, hydrate_db_from_json
        from engine.ecomm_basket import BASKET
        from scrapers.amazon import scrape_amazon
        from engine.outlier import reject_outliers
        from db.store import EcommStore
    except Exception:
        traceback.print_exc()
        return 2

    init_db()
    hydrate_db_from_json()  # so outlier rejection has trailing history

    log.info(f"Scraping {len(BASKET)} basket items from Amazon...")
    try:
        raw = scrape_amazon(BASKET)
    except Exception as exc:
        log.error(f"Scraper crashed: {exc}")
        traceback.print_exc()
        return 2

    if not raw:
        log.warning("Scraper returned 0 items — Amazon may be blocking us")
        return 1

    log.info(f"Scraper returned {len(raw)} items, applying outlier rejection")
    store = EcommStore()
    kept, rejected = reject_outliers(raw, store, platform="amazon")
    if rejected:
        log.warning(f"Rejected {len(rejected)} outlier(s):")
        for r in rejected:
            log.warning(f"  {r['item_id']}: {r.get('_reject_reason', 'no reason')}")

    if not kept:
        log.warning("All scraped items rejected as outliers — nothing to persist")
        return 1

    added = append_observations(kept)
    log.info(f"Persisted {added} new observations to data/amazon_prices.json")

    return 0 if added > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
