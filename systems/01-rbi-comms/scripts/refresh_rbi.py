"""
Autonomously poll RBI's Annualpolicy.aspx page for new MPC documents and
append parsed entries to data/rbi_communications.json.

Designed to be invoked by .github/workflows/refresh-rbi.yml on a daily cron
during MPC weeks (and weekly otherwise).

Exit codes (mirrors macro-pulse refresh_releases.py):
    0 → at least one new document was added (workflow should commit + push)
    1 → no new documents (workflow does nothing)
    2 → parser failure with NO successful additions (open issue)
    3 → partial success: at least one added AND at least one failed
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.mpc_extractor import extract_mpc_decision  # noqa: E402
from engine.stance_engine import analyze_communication  # noqa: E402
from scrapers._rbi_api import (  # noqa: E402
    discover_current_cycle_documents, fetch_annualpolicy_landing,
    fetch_press_release,
)
from scrapers.rbi_resolution import extract_press_release  # noqa: E402

UPDATES_PATH = ROOT / "data" / "rbi_communications.json"

EXIT_NEW = 0
EXIT_NOCHANGE = 1
EXIT_FAIL = 2
EXIT_PARTIAL = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("refresh_rbi")


def _load_updates() -> dict:
    if UPDATES_PATH.exists():
        try:
            data = json.loads(UPDATES_PATH.read_text())
        except json.JSONDecodeError as exc:
            log.error(f"Cannot parse {UPDATES_PATH}: {exc}")
            return {"_comment": "", "documents": []}
        data.setdefault("documents", [])
        return data
    return {
        "_comment": (
            "Autonomous additions to the RBI communications corpus. Merged "
            "on top of seed/historical_data.py at app boot. Each entry has a "
            "unique 'doc_id'; reruns are idempotent."
        ),
        "documents": [],
    }


def _save_updates(data: dict) -> None:
    """Atomic write: temp file + rename."""
    UPDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = UPDATES_PATH.with_suffix(UPDATES_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(UPDATES_PATH)


def _existing_doc_ids(updates: dict) -> set[str]:
    return {d["doc_id"] for d in updates.get("documents", []) if d.get("doc_id")}


def _document_type(kind: str) -> str:
    return {
        "mpc_statement":    "MPC Statement",
        "mpc_minutes":      "MPC Minutes",
        "press_conference": "Press Conference",
        "speech":           "Speech",
    }.get(kind, "Other")


def _process_press_release(prid: int, kind: str) -> tuple[bool, dict | None, str | None]:
    """Returns (ok, document_dict, error)."""
    html = fetch_press_release(prid)
    if not html:
        return False, None, f"fetch failed for prid={prid}"

    parsed = extract_press_release(html)
    if not parsed:
        return False, None, f"parse failed for prid={prid}"

    full_text = parsed["full_text"]
    decision = extract_mpc_decision(full_text, publication_date=parsed["publication_date"])
    signal = analyze_communication(full_text)

    doc_id = f"rbi-pr-{prid}"
    doc = {
        "doc_id":          doc_id,
        "prid":            prid,
        "kind":            kind,
        "published_at":    parsed["publication_date"],
        "document_type":   _document_type(kind),
        "title":           parsed["title"],
        "summary":         parsed["paragraphs"][0][:300] if parsed["paragraphs"] else "",
        "full_text":       full_text,
        "url":             f"https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={prid}",
        "signal":          signal.to_record(),
        "decision":        decision if kind == "mpc_statement" and decision.get("repo_rate") is not None else None,
    }
    return True, doc, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect new documents but don't write JSON")
    args = parser.parse_args()

    updates = _load_updates()
    existing = _existing_doc_ids(updates)

    # Discover from RBI Annualpolicy landing
    landing = fetch_annualpolicy_landing()
    if landing is None:
        log.error("Annualpolicy.aspx fetch failed — abort")
        return EXIT_FAIL

    found = discover_current_cycle_documents(landing)
    log.info(f"Found {len(found)} document(s) in current MPC cycle")

    any_added = False
    any_failed = False

    for entry in found:
        if entry["kind"] == "press_conference":
            # Press conference is a Speech — different scraper, skipping in v1.
            log.info(f"Skipping press conference (Speech ID {entry['speech_id']}) — v1 scope")
            continue
        if not entry.get("prid"):
            continue
        doc_id = f"rbi-pr-{entry['prid']}"
        if doc_id in existing:
            continue

        ok, doc, err = _process_press_release(entry["prid"], entry["kind"])
        if ok:
            updates["documents"].append(doc)
            existing.add(doc_id)
            log.info(f"ADDED {doc_id}: {doc['title'][:80]}")
            any_added = True
        else:
            log.error(f"FAILED {doc_id}: {err}")
            any_failed = True

    if any_added and not args.dry_run:
        _save_updates(updates)
        log.info(f"Wrote {UPDATES_PATH}")

    if any_added and any_failed:
        return EXIT_PARTIAL
    if any_failed:
        return EXIT_FAIL
    return EXIT_NEW if any_added else EXIT_NOCHANGE


if __name__ == "__main__":
    sys.exit(main())
