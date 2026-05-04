"""
DEPRECATED. Synthetic samples retired in May 2026 (PRD-2026-05-rbi-comms-redesign).

This module exists only as a back-compat shim for legacy imports — it now
delegates to seed.historical_data which loads real RBI Governor's Statements
from committed HTML fixtures.

If you encounter any reference to "rbi.example/..." URLs, that's a sign
something is still pointing at the old synthetic data. Investigate and remove.
"""
from seed.historical_data import seed

# Module-level fail-fast: refuse to ship if anyone re-introduces the synthetic
# data. The previous version had `SAMPLE_COMMUNICATIONS = [...]` with rbi.example
# URLs which the PRD's R8 risk explicitly bans.
SAMPLE_COMMUNICATIONS: list = []  # intentionally empty


__all__ = ["seed", "SAMPLE_COMMUNICATIONS"]
