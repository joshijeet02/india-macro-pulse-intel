"""
Backfill historical RBI MPC documents (Oct 2016 — present) into the corpus.

Phase 3 of PRD-2026-05-sid-feedback-theme-diff-and-backfill.

Discovery:
    Annualpolicy.aspx is an ASP.NET WebForm with a year-selector hidden
    behind a `GetYear(year)` JS PostBack. We replicate the PostBack with
    `requests`: GET the page once to capture __VIEWSTATE /
    __EVENTVALIDATION, then POST with hdnYear=N for each fiscal year. The
    response HTML lists every MPC-related PRID + Speech ID from that year.
    Way leaner than probing PRIDs sequentially.

Pipeline:
    1. Discover: per-year PostBack → list of (kind, prid|speech_id, title)
    2. Fetch:    parallel HTTP via ThreadPoolExecutor (5 workers, polite)
    3. Parse:    rbi_resolution.extract_press_release → dict
    4. Extract:  mpc_extractor.extract_mpc_decision (rate, vote, stance,
                 projections); stance_engine.analyze_communication
    5. Persist:  append to data/rbi_communications.json (idempotent —
                 dedup by doc_id)
    6. Failures: written to data/ingestion_failures.json for human triage

Usage:
    python scripts/backfill_mpc_history.py                # all years
    python scripts/backfill_mpc_history.py --year 2024    # single year
    python scripts/backfill_mpc_history.py --dry-run      # discover only
    python scripts/backfill_mpc_history.py --statements-only

Exit codes:
    0  fully successful (no failures)
    1  partial success (some docs failed but corpus grew)
    2  no docs ingested
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.mpc_extractor import extract_mpc_decision  # noqa: E402
from engine.stance_engine import analyze_communication  # noqa: E402
from scrapers._rbi_api import _classify  # noqa: E402
from scrapers.rbi_resolution import extract_press_release  # noqa: E402

UPDATES_PATH = ROOT / "data" / "rbi_communications.json"
FAILURES_PATH = ROOT / "data" / "ingestion_failures.json"

ANNUALPOLICY_URL = "https://rbi.org.in/Scripts/Annualpolicy.aspx"
PRESS_RELEASE_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"

USER_AGENT = "Mozilla/5.0 (research; india-rates-research bot; joshijeet02@gmail.com)"

# RBI's MPC framework began Oct 2016. Their fiscal year runs Apr–Mar, so
# fiscal year 2017 = Apr 2016 – Mar 2017 (which captures the first MPC, Oct 2016).
# Year 2027 captures the most recent (Apr 2026).
DEFAULT_YEARS = list(range(2017, 2028))  # 2017–2027

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("backfill")


# ─── Discovery: per-year PostBack ────────────────────────────────────────────

def _hidden_field(html: str, name: str) -> Optional[str]:
    m = re.search(rf'<input[^>]*name="{name}"[^>]*value="([^"]*)"', html, re.IGNORECASE)
    return m.group(1) if m else None


def discover_year(session: requests.Session, year: int) -> list[dict]:
    """
    POST Annualpolicy.aspx with hdnYear=N, parse the response, return a
    list of {kind, prid, speech_id, title, url} dicts.
    """
    # GET first to grab fresh tokens (RBI's WebForms regenerates them)
    r0 = session.get(ANNUALPOLICY_URL, timeout=20)
    r0.raise_for_status()
    vs = _hidden_field(r0.text, "__VIEWSTATE") or ""
    ev = _hidden_field(r0.text, "__EVENTVALIDATION") or ""
    vsg = _hidden_field(r0.text, "__VIEWSTATEGENERATOR") or ""

    payload = {
        "__VIEWSTATE":          vs,
        "__EVENTVALIDATION":    ev,
        "__VIEWSTATEGENERATOR": vsg,
        "hdnYear":              str(year),
    }
    r = session.post(ANNUALPOLICY_URL, data=payload, timeout=30)
    r.raise_for_status()

    return _parse_year_response(r.text)


def _parse_year_response(html: str) -> list[dict]:
    """Extract all MPC-related (prid|speech_id, title) pairs from a year-HTML response."""
    out: list[dict] = []
    seen: set[tuple] = set()

    # Match <a href="...prid=N" target="_blank" class='link2'>TITLE</a>
    pr_pattern = re.compile(
        r'<a\s+href="([^"]*BS_PressReleaseDisplay\.aspx\?prid=(\d+))"[^>]*>([^<]{5,300})</a>',
        re.IGNORECASE,
    )
    for m in pr_pattern.finditer(html):
        url, prid_str, title = m.group(1), int(m.group(2)), m.group(3).strip()
        kind = _classify(title)
        if kind == "other":
            continue  # skip non-MPC documents
        key = ("prid", prid_str)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "kind":      kind,
            "prid":      prid_str,
            "speech_id": None,
            "title":     title,
            "url":       url if url.startswith("http") else f"https://rbi.org.in{url}",
        })

    sp_pattern = re.compile(
        r'<a\s+href="([^"]*BS_SpeechesView\.aspx\?Id=(\d+))"[^>]*>([^<]{5,300})</a>',
        re.IGNORECASE,
    )
    for m in sp_pattern.finditer(html):
        url, sid, title = m.group(1), int(m.group(2)), m.group(3).strip()
        kind = _classify(title)
        if kind == "other":
            continue
        key = ("speech_id", sid)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "kind":      kind,
            "prid":      None,
            "speech_id": sid,
            "title":     title,
            "url":       url if url.startswith("http") else f"https://rbi.org.in{url}",
        })

    return out


# ─── Fetch + parse a single PRID ─────────────────────────────────────────────

def _fetch_and_parse(session: requests.Session, entry: dict) -> tuple[Optional[dict], Optional[str]]:
    """Fetch a single MPC document and run it through the full pipeline. Returns (record, error)."""
    if not entry.get("prid"):
        return None, "skipping non-PRID entry (speeches handled separately)"

    prid = entry["prid"]
    try:
        r = session.get(
            PRESS_RELEASE_URL,
            params={"prid": prid},
            headers={"Referer": ANNUALPOLICY_URL},
            timeout=30,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        return None, f"HTTP fetch failed: {exc}"

    parsed = extract_press_release(r.text)
    if parsed is None:
        return None, "extract_press_release returned None"

    full_text = parsed["full_text"]
    if not full_text or len(full_text) < 500:
        return None, f"text too short ({len(full_text)} chars) — likely parse miss"

    decision = extract_mpc_decision(full_text, publication_date=parsed["publication_date"])
    signal = analyze_communication(full_text)

    doc_id = f"rbi-pr-{prid}"
    document_type = {
        "mpc_statement":    "MPC Statement",
        "mpc_minutes":      "MPC Minutes",
        "press_conference": "Press Conference",
    }.get(entry["kind"], "Other")

    record = {
        "doc_id":          doc_id,
        "prid":            prid,
        "kind":            entry["kind"],
        "published_at":    parsed["publication_date"],
        "document_type":   document_type,
        "title":           parsed.get("title") or entry["title"],
        "summary":         parsed["paragraphs"][0][:300] if parsed["paragraphs"] else "",
        "full_text":       full_text,
        "url":             entry["url"],
        "signal":          signal.to_record(),
        "decision":        decision if entry["kind"] == "mpc_statement" and decision.get("repo_rate") is not None else None,
    }
    return record, None


# ─── Persistence ─────────────────────────────────────────────────────────────

def _load_corpus() -> dict:
    if UPDATES_PATH.exists():
        try:
            return json.loads(UPDATES_PATH.read_text())
        except json.JSONDecodeError:
            log.warning(f"corpus file unreadable; starting fresh")
    return {
        "_comment": "RBI MPC corpus. Backfill orchestrated by scripts/backfill_mpc_history.py.",
        "documents": [],
    }


def _save_corpus(data: dict) -> None:
    UPDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = UPDATES_PATH.with_suffix(UPDATES_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(UPDATES_PATH)


def _append_failure(failures: list[dict], entry: dict, reason: str) -> None:
    failures.append({
        "prid":          entry.get("prid"),
        "speech_id":     entry.get("speech_id"),
        "title":         entry.get("title"),
        "url":           entry.get("url"),
        "reason":        reason,
        "logged_at":     datetime.utcnow().isoformat() + "Z",
    })


def _save_failures(failures: list[dict]) -> None:
    if not failures:
        return
    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAILURES_PATH.write_text(json.dumps({"failures": failures}, indent=2) + "\n")


# ─── Main orchestrator ───────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, action="append",
                        help="Specific fiscal year(s) to backfill (default: 2017-2027)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Discover PRIDs but don't fetch / persist")
    parser.add_argument("--statements-only", action="store_true",
                        help="Skip Minutes (faster)")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Concurrent HTTP workers (be polite to RBI)")
    args = parser.parse_args()

    years = args.year if args.year else DEFAULT_YEARS

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # 1. Discover all entries across requested years
    all_entries: list[dict] = []
    seen_prids: set[int] = set()
    log.info(f"Discovering MPC docs across years: {years}")
    for year in years:
        try:
            entries = discover_year(session, year)
            new = [e for e in entries if e.get("prid") and e["prid"] not in seen_prids]
            for e in new:
                seen_prids.add(e["prid"])
            log.info(f"  Year {year}: {len(entries)} docs found, {len(new)} new (after dedup)")
            all_entries.extend(new)
            time.sleep(1.0)  # polite delay between year fetches
        except Exception as exc:
            log.error(f"  Year {year}: discovery failed — {exc}")

    if args.statements_only:
        all_entries = [e for e in all_entries if e["kind"] == "mpc_statement"]
        log.info(f"Filtered to mpc_statement only: {len(all_entries)} docs")

    log.info(f"Total to ingest: {len(all_entries)} documents")
    if args.dry_run:
        for e in all_entries[:20]:
            log.info(f"  [{e['kind']:18}] PRID={e['prid']} :: {e['title'][:80]}")
        if len(all_entries) > 20:
            log.info(f"  ... +{len(all_entries) - 20} more")
        return 0

    # 2. Skip ones we already have
    corpus = _load_corpus()
    existing_doc_ids = {d.get("doc_id") for d in corpus.get("documents", [])}
    todo = [e for e in all_entries if f"rbi-pr-{e['prid']}" not in existing_doc_ids]
    log.info(f"Skipping {len(all_entries) - len(todo)} already-ingested docs")
    log.info(f"Will fetch + parse: {len(todo)} new docs")

    # 3. Parallel fetch + parse
    failures: list[dict] = []
    new_records: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        future_to_entry = {
            pool.submit(_fetch_and_parse, session, entry): entry
            for entry in todo
        }
        for i, future in enumerate(as_completed(future_to_entry), 1):
            entry = future_to_entry[future]
            try:
                record, err = future.result()
            except Exception as exc:
                _append_failure(failures, entry, f"unexpected exception: {exc}")
                continue

            if err:
                _append_failure(failures, entry, err)
                if i % 10 == 0:
                    log.info(f"  [{i}/{len(todo)}] {len(new_records)} ok, {len(failures)} failed")
                continue

            new_records.append(record)
            if i % 10 == 0:
                log.info(
                    f"  [{i}/{len(todo)}] {len(new_records)} ok, {len(failures)} failed "
                    f"— latest: {record['published_at']} {record['kind']}"
                )

    log.info(f"Backfill complete: {len(new_records)} new docs, {len(failures)} failures")

    # 4. Persist
    corpus["documents"].extend(new_records)
    # Sort by published_at for cleanliness
    corpus["documents"].sort(key=lambda d: d.get("published_at") or "")
    _save_corpus(corpus)
    log.info(f"Wrote {UPDATES_PATH} ({len(corpus['documents'])} total docs)")

    if failures:
        _save_failures(failures)
        log.info(f"Wrote {FAILURES_PATH} ({len(failures)} failures for human triage)")

    if len(new_records) == 0:
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
