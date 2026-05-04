"""
Real RBI MPC seed data — replaces the synthetic samples in sample_data.py.

Sources: parsed live from RBI's BS_PressReleaseDisplay.aspx pages and committed
as fixtures under tests/fixtures/html/. Each seed entry corresponds to one
real Governor's Statement (or Resolution) with full text, structured stance
extraction, and an mpc_decisions row.

For backfill before Feb 2026, the autonomous workflow (scripts/refresh_rbi.py)
catches new MPCs going forward; older meetings can be added by appending PRIDs
to PRIOR_MPC_PRIDS and re-running the seed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from db.store import CommunicationStore, MPCDecisionStore
from engine.mpc_extractor import extract_mpc_decision
from engine.stance_engine import analyze_communication
from scrapers.rbi_resolution import extract_press_release

log = logging.getLogger(__name__)

FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "html"
UPDATES_PATH = Path(__file__).parent.parent / "data" / "rbi_communications.json"

# Each seed entry:
#   - prid: RBI's internal Press Release ID
#   - fixture: path of locally-committed HTML fixture (so seed works offline)
#   - kind: 'mpc_statement' (Governor's Statement) | 'mpc_minutes' | 'speech'
#   - meeting_key: human-readable label for the MPC cycle
SEED_DOCUMENTS = [
    {
        "prid": 62170,
        "fixture": "governor_statement_2026_02_06.html",
        "kind": "mpc_statement",
        "meeting_key": "Feb-2026",
        "speaker": "Governor",
    },
    {
        "prid": 62515,
        "fixture": "governor_statement_2026_04_08.html",
        "kind": "mpc_statement",
        "meeting_key": "Apr-2026",
        "speaker": "Governor",
    },
]


def _load_fixture(name: str) -> str:
    path = FIXTURE_DIR / name
    return path.read_text()


def _document_type(kind: str) -> str:
    return {
        "mpc_statement":    "MPC Statement",
        "mpc_minutes":      "MPC Minutes",
        "press_conference": "Press Conference",
        "speech":           "Speech",
    }.get(kind, "Other")


def _seed_one(entry: dict) -> tuple[bool, str]:
    """Parse one fixture and persist it. Returns (success, reason)."""
    html = _load_fixture(entry["fixture"])
    parsed = extract_press_release(html)
    if not parsed:
        return False, f"parse failed for {entry['fixture']}"

    full_text = parsed["full_text"]
    decision = extract_mpc_decision(full_text, publication_date=parsed["publication_date"])
    signal = analyze_communication(full_text)

    doc_id = f"rbi-pr-{entry['prid']}"
    url = f"https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={entry['prid']}"

    document = {
        "doc_id":          doc_id,
        "series_key":      f"mpc:{entry['kind']}",
        "meeting_key":     entry["meeting_key"],
        "published_at":    parsed["publication_date"],
        "document_type":   _document_type(entry["kind"]),
        "title":           parsed["title"],
        "speaker":         entry.get("speaker"),
        "url":             url,
        "source":          "RBI",
        "summary":         (parsed["paragraphs"][0][:300] if parsed["paragraphs"] else ""),
        "full_text":       full_text,
        **signal.to_record(),
    }

    CommunicationStore().upsert(document)

    # Persist the structured mpc_decisions row only if we got a real repo rate.
    # Minutes / speeches don't have all the fields populated.
    if entry["kind"] == "mpc_statement" and decision.get("repo_rate") is not None:
        decision_record = {**decision, "doc_id": doc_id}
        MPCDecisionStore().upsert(decision_record)

    return True, doc_id


def _seed_from_json_sidecar() -> int:
    """
    Merge any docs from data/rbi_communications.json (written by the
    autonomous refresh workflow) into the store. Returns count seeded.
    """
    if not UPDATES_PATH.exists():
        return 0
    try:
        data = json.loads(UPDATES_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(f"JSON sidecar unreadable: {exc}")
        return 0

    documents = data.get("documents") or []
    docs_store = CommunicationStore()
    decisions_store = MPCDecisionStore()
    count = 0
    for d in documents:
        if not all(k in d for k in ("doc_id", "published_at", "title", "full_text")):
            continue
        document = {
            "doc_id":          d["doc_id"],
            "series_key":      f"mpc:{d.get('kind') or 'mpc_statement'}",
            "meeting_key":     d.get("published_at", "")[:7],  # YYYY-MM
            "published_at":    d["published_at"],
            "document_type":   d.get("document_type") or "MPC Statement",
            "title":           d["title"],
            "speaker":         d.get("speaker") or "Governor",
            "url":             d["url"],
            "source":          "RBI",
            "summary":         d.get("summary", ""),
            "full_text":       d["full_text"],
            **(d.get("signal") or {}),
        }
        docs_store.upsert(document)

        decision = d.get("decision")
        if decision and decision.get("repo_rate") is not None:
            decisions_store.upsert({**decision, "doc_id": d["doc_id"]})
        count += 1
    return count


def seed() -> None:
    """
    Idempotent boot-time seeder. Order: bundled fixtures first (frozen
    historical baseline), then JSON sidecar (autonomous additions). Sidecar
    entries with the same doc_id override fixture entries.
    """
    log.info("Seeding RBI communications from fixtures...")
    for entry in SEED_DOCUMENTS:
        ok, info = _seed_one(entry)
        marker = "✓" if ok else "✗"
        log.info(f"  {marker} {entry['meeting_key']} ({entry['kind']}): {info}")

    json_count = _seed_from_json_sidecar()
    if json_count:
        log.info(f"Merged {json_count} record(s) from JSON sidecar")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    seed()
