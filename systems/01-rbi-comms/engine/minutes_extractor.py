"""
Per-member analysis of MPC Minutes.

The Minutes document follows a templated structure:
1. Generic intro paragraphs (committee-level discussion summary).
2. A **voting table**: "Voting on the Resolution to keep policy repo rate
   unchanged at X per cent / Member Vote / Dr. <Name> Yes / Shri <Name> No / ..."
3. **Per-member sections**: "Statement by Dr. <Name>" followed by 1-3
   paragraphs of that member's individual remarks.
4. Concluding paragraphs.

This module:
- Splits a Minutes document into per-member sections
- Parses the voting table for explicit Yes/No votes per member
- Runs the stance engine on each member's section to get an individual
  stance score → reveals which member is the most hawkish vs dovish

Output is a `MemberViews` dataclass per meeting, ready for the UI heatmap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from engine.stance_engine import analyze_communication

# Member name patterns. RBI honorifics: Dr. / Shri / Smt.
_HONORIFICS = r"(?:Dr\.|Shri|Smt\.|Prof\.|Mr\.|Ms\.|Mrs\.)"

# A name token is either a full word (Jayanth, Varma) or a single-letter
# initial with optional period (R., D). Without the initial branch, names
# like "Jayanth R. Varma" silently fail to match — which is exactly what
# happened to Prof. Varma's votes across the entire Dec 2022 – Oct 2023
# dissent series. Tests in tests/test_minutes_extractor.py pin this.
_NAME_TOKEN = r"(?:[A-Z][a-zA-Z]+|[A-Z]\.?)"

# Tokens are separated by horizontal whitespace only — never by newlines —
# so the regex cannot greedy-extend across a line break into the body of a
# Statement section.
_NAME_PATTERN = (
    rf"(?P<honorific>{_HONORIFICS})[ \t]+"
    rf"(?P<name>{_NAME_TOKEN}(?:[ \t]+{_NAME_TOKEN}){{1,3}})"
)

# "Statement by Dr. Foo Bar" — the section delimiter
_SECTION_HEADER_RX = re.compile(
    rf"Statement\s+by\s+{_NAME_PATTERN}",
    re.IGNORECASE,
)

# Voting table parser: looks for "Voting on the Resolution" anywhere in the
# text. The table content varies (e.g. "Member Vote" vs "Magnitude of policy
# repo rate reduction (basis points)"), so we don't anchor on the column
# header — we just scan a window forward looking for member-vote pairs.
_VOTE_TABLE_START_RX = re.compile(
    r"Voting\s+on\s+the\s+Resolution",
    re.IGNORECASE,
)
_VOTE_PAIR_RX = re.compile(
    rf"{_NAME_PATTERN}\s+(?P<vote>Yes|No|Abstain)",
)


@dataclass
class MemberView:
    name: str
    honorific: str            # 'Dr.' / 'Shri' / 'Smt.'
    vote: Optional[str]        # 'Yes' / 'No' / 'Abstain' / None if not parsed
    statement: str             # full text of their Statement section
    stance_label: Optional[str]
    stance_score: Optional[float]
    inflation_label: Optional[str]
    growth_label: Optional[str]


@dataclass
class MinutesAnalysis:
    meeting_date: str
    members: list[MemberView] = field(default_factory=list)
    raw_vote_table: str = ""

    @property
    def dissenting_members(self) -> list[str]:
        return [m.name for m in self.members if m.vote and m.vote.lower() != "yes"]

    @property
    def vote_summary(self) -> dict:
        yes = sum(1 for m in self.members if m.vote == "Yes")
        no = sum(1 for m in self.members if m.vote == "No")
        return {"yes": yes, "no": no, "total": len(self.members)}


def analyze_minutes(full_text: str, meeting_date: str) -> MinutesAnalysis:
    """
    Parse a Minutes document into per-member views with stance scores.

    Returns a MinutesAnalysis even on partial parse — caller checks
    .members for completeness.
    """
    out = MinutesAnalysis(meeting_date=meeting_date)

    # ── Vote table ─────────────────────────────────────────────────────
    member_votes: dict[str, str] = {}
    table_match = _VOTE_TABLE_START_RX.search(full_text)
    if table_match:
        # Take a window of ~600 chars after the table header
        window = full_text[table_match.end(): table_match.end() + 600]
        out.raw_vote_table = window
        for vm in _VOTE_PAIR_RX.finditer(window):
            full_name = f"{vm.group('honorific')} {vm.group('name')}".strip()
            member_votes[full_name] = vm.group("vote")
            # Also store under bare-name key for lookup robustness
            member_votes[vm.group("name").strip()] = vm.group("vote")

    # ── Per-member sections ────────────────────────────────────────────
    # Find every "Statement by <Name>" header and slice the document
    headers = list(_SECTION_HEADER_RX.finditer(full_text))
    for i, hdr in enumerate(headers):
        name = hdr.group("name").strip()
        honorific = hdr.group("honorific").strip()
        section_start = hdr.end()
        section_end = (
            headers[i + 1].start() if i + 1 < len(headers) else len(full_text)
        )
        statement = full_text[section_start:section_end].strip()

        # Run the stance engine on this individual's text
        signal = analyze_communication(statement)

        full_name_key = f"{honorific} {name}"
        out.members.append(MemberView(
            name=name,
            honorific=honorific,
            vote=member_votes.get(full_name_key) or member_votes.get(name),
            statement=statement,
            stance_label=signal.stance.label,
            stance_score=signal.stance.score,
            inflation_label=signal.inflation_assessment.label,
            growth_label=signal.growth_assessment.label,
        ))

    return out


def member_view_summary(analysis: MinutesAnalysis) -> dict:
    """
    Aggregate stats for the Minutes UI header — vote summary, hawk/dove
    distribution, dissent count.
    """
    vs = analysis.vote_summary
    hawks = sum(
        1 for m in analysis.members
        if m.stance_label in ("hawkish", "leaning_hawkish")
    )
    doves = sum(
        1 for m in analysis.members
        if m.stance_label in ("dovish", "leaning_dovish")
    )
    return {
        "members_parsed":     len(analysis.members),
        "vote_for":           vs["yes"],
        "vote_against":       vs["no"],
        "dissenting_members": analysis.dissenting_members,
        "hawks":              hawks,
        "doves":              doves,
    }
