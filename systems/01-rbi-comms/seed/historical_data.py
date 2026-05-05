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

from db.store import CommunicationStore, MemberViewStore, MPCDecisionStore
from engine.minutes_extractor import analyze_minutes
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
    # Governor's Statements (one per MPC meeting)
    {"prid": 60605, "fixture": "governor_statement_2025_06_06.html",
     "kind": "mpc_statement", "meeting_key": "Jun-2025", "speaker": "Governor"},
    {"prid": 60958, "fixture": "governor_statement_2025_08_06.html",
     "kind": "mpc_statement", "meeting_key": "Aug-2025", "speaker": "Governor"},
    {"prid": 61333, "fixture": "governor_statement_2025_10_01.html",
     "kind": "mpc_statement", "meeting_key": "Oct-2025", "speaker": "Governor"},
    {"prid": 61750, "fixture": "governor_statement_2025_12_05.html",
     "kind": "mpc_statement", "meeting_key": "Dec-2025", "speaker": "Governor"},
    {"prid": 62170, "fixture": "governor_statement_2026_02_06.html",
     "kind": "mpc_statement", "meeting_key": "Feb-2026", "speaker": "Governor"},
    {"prid": 62515, "fixture": "governor_statement_2026_04_08.html",
     "kind": "mpc_statement", "meeting_key": "Apr-2026", "speaker": "Governor"},
    # Minutes (one per MPC meeting, released ~14 days after the statement)
    {"prid": 60686, "fixture": "mpc_minutes_2025_06_20.html",
     "kind": "mpc_minutes", "meeting_key": "Jun-2025"},
    {"prid": 61056, "fixture": "mpc_minutes_2025_08_20.html",
     "kind": "mpc_minutes", "meeting_key": "Aug-2025"},
    {"prid": 61433, "fixture": "mpc_minutes_2025_10_15.html",
     "kind": "mpc_minutes", "meeting_key": "Oct-2025"},
    {"prid": 61856, "fixture": "mpc_minutes_2025_12_19.html",
     "kind": "mpc_minutes", "meeting_key": "Dec-2025"},
    {"prid": 62261, "fixture": "mpc_minutes_2026_02_20.html",
     "kind": "mpc_minutes", "meeting_key": "Feb-2026"},
    {"prid": 62599, "fixture": "mpc_minutes_2026_04_22.html",
     "kind": "mpc_minutes", "meeting_key": "Apr-2026"},
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
    if entry["kind"] == "mpc_statement" and decision.get("repo_rate") is not None:
        decision_record = {**decision, "doc_id": doc_id}
        MPCDecisionStore().upsert(decision_record)

    # For Minutes documents, do per-member analysis and upsert into the
    # mpc_member_views table. The meeting_date for Minutes is its publication
    # date, but we need to align with the underlying MPC meeting — use the
    # meeting_key (e.g. "Apr-2026") to find the matching Statement's meeting
    # date for member-view association. Fall back to publication_date.
    if entry["kind"] == "mpc_minutes":
        analysis = analyze_minutes(full_text, parsed["publication_date"])
        meeting_date = _meeting_key_to_date(entry.get("meeting_key")) or parsed["publication_date"]
        members_payload = [
            {
                "member_name":      m.name,
                "honorific":        m.honorific,
                "vote":             m.vote,
                "stance_label":     m.stance_label,
                "stance_score":     m.stance_score,
                "inflation_label":  m.inflation_label,
                "growth_label":     m.growth_label,
                "statement_excerpt": m.statement[:1500],
            }
            for m in analysis.members
        ]
        MemberViewStore().upsert_many(meeting_date, members_payload)

    return True, doc_id


# Map meeting_key like "Apr-2026" → an approximate meeting date for member-view
# linkage. Uses the canonical first-Tuesday-ish heuristic; the seed-level Statement
# fixture already has the exact date so this only matters when the Minutes is
# loaded WITHOUT its corresponding Statement.
_MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def _meeting_key_to_date(meeting_key: str | None) -> str | None:
    """'Apr-2026' → '2026-04-08' (heuristic; exact dates set by Statement fixture)."""
    if not meeting_key:
        return None
    try:
        mon, year = meeting_key.split("-")
        m = _MONTHS.get(mon[:3].title())
        if not m:
            return None
        # Look up the actual Statement publication_date from MPCDecisionStore
        from db.store import MPCDecisionStore
        for d in MPCDecisionStore().get_history(limit=24):
            md = d.get("meeting_date") or ""
            if md.startswith(f"{year}-{m}"):
                return md
        # Fall back
        return f"{year}-{m}-08"
    except (ValueError, KeyError):
        return None


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
