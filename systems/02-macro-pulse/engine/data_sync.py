"""
Keep the running app in step with the data files the scheduled jobs commit.

Why this exists — the app went three months stale on 23 Oct 2026 while every
release was sitting in the repo:

1. app.py seeded the SQLite store only when it was EMPTY. Streamlit Cloud keeps
   a container (and its gitignored macro_pulse.db) alive across pushes, so
   once seeded in July the store never took another release.
2. engine.live_index reads its anchor at IMPORT time. A push re-runs app.py
   but does not reliably re-import modules already in sys.modules, so even a
   fresh division_indices.json left the Nowcast measuring from June.

Both are fixed by keying on the files themselves: whenever the bytes of a data
file change, re-seed (upserts are idempotent) and re-read the anchor. This is a
new module on purpose — see ui/header_status.py for why app.py should never
import a new name from an existing one.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_DATA = Path(__file__).parent.parent / "data"
RELEASE_UPDATES = _DATA / "release_updates.json"
DIVISION_INDICES = _DATA / "division_indices.json"


def file_signature(*paths: Path) -> str:
    """A digest of the files' contents; changes whenever any of them does."""
    digest = hashlib.sha256()
    for path in paths:
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def sync_store() -> None:
    """Upsert the merged seed and the JSON sidecar into SQLite."""
    from seed.historical_data import seed
    seed()


def refresh_anchor() -> str:
    """
    Re-read the live index anchor into the module's globals.

    compute_live_index looks these up at call time, so reassigning them is
    enough; no module reload needed. Returns the anchor month now in force.
    """
    import engine.live_index as live_index

    (
        live_index.ANCHOR_MONTH,
        live_index.ANCHOR_DIVISION_INDICES,
        live_index.ANCHOR_HEADLINE_INDEX,
    ) = live_index.load_anchor()
    return live_index.ANCHOR_MONTH
