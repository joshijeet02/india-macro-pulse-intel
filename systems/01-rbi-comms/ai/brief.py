"""
AI brief generator for RBI communications.

Hardened per PRD risk R4 (LLM hallucination of vote split / quotes):
  * temperature = 0 for determinism
  * Strict system prompt: only use facts in the supplied STRUCTURED SIGNALS
    block; if a signal is missing, say so rather than invent
  * Quote attribution required: any direct quote must reference paragraph
    number from the supplied text
  * "DRAFT — verify before publishing" disclaimer in the rendered brief
    (rendered in the UI; this module just produces clean copy)
"""
from __future__ import annotations

import os

import anthropic


_SYSTEM_PROMPT = (
    "You are a senior India macro economist writing a post-MPC communication "
    "note for a sell-side rates strategist. Your readers are professional "
    "investors at banks, hedge funds, and asset managers.\n\n"
    "Write three short paragraphs in plain prose, no headers, no bullet "
    "points, no throat-clearing.\n\n"
    "Constraints:\n"
    "  - Use ONLY the facts supplied in the STRUCTURED SIGNALS and TEXT "
    "blocks. If a signal is missing or null, do NOT invent a value.\n"
    "  - When you reference specific phrasing from the document, cite the "
    "paragraph number: e.g., '(¶4)' after the quoted phrase.\n"
    "  - Never claim a vote split, repo rate, or projection that isn't in "
    "the structured signals.\n"
    "  - Tone: analyst, not journalist. Prefer specifics over rhetoric."
)


_USER_TEMPLATE = """RBI Communication Brief

DOCUMENT
  Title: {title}
  Type:  {document_type}
  Date:  {published_at}
  Speaker: {speaker}

STRUCTURED SIGNALS (use only these — anything else is hallucination)
  Repo rate:                {repo_rate}
  Repo change (bps):        {repo_change_bps}
  Vote:                     {vote_for} for / {vote_against} against
  Stance label:             {stance_label}
  Stance score (-1 to +1):  {stance_score}
  Forward guidance markers: {forward_guidance}
  Growth assessment:        {growth_assessment}
  Inflation assessment:     {inflation_assessment}
  Liquidity stance:         {liquidity_stance}
  Risk balance:             {risk_balance}
  GDP projection:           {gdp_proj}
  CPI projection:           {cpi_proj}

DOCUMENT TEXT (truncated to 5000 chars)
{full_text}

Write three paragraphs:

1. WHAT CHANGED in the policy stance: contrast today's signals with the
   most recent prior MPC if context allows. Cite paragraph numbers (¶N) for
   any quoted phrasing.

2. RBI'S REACTION FUNCTION: how would you read what this document tells
   you about how RBI will react to incoming data — inflation surprises,
   growth disappointments, external shocks?

3. BOND MARKET TAKEAWAY: what should fixed-income investors infer? Be
   specific about the front end vs the long end, the rupee carry, and the
   pricing implications for the next MPC.
"""


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def generate_communication_brief(document: dict) -> str:
    """
    Generate an analyst brief from a document record. The record should
    have stance engine output (stance_score, stance_label, etc.) and
    optionally MPC decision fields (repo_rate, vote_for, etc.).
    """
    prompt = _USER_TEMPLATE.format(
        title=document.get("title", "—"),
        document_type=document.get("document_type", "—"),
        published_at=document.get("published_at", "—"),
        speaker=document.get("speaker") or "—",
        repo_rate=_fmt(document.get("repo_rate"), "{:.2f}%"),
        repo_change_bps=document.get("repo_rate_change_bps", "—"),
        vote_for=document.get("vote_for", "—"),
        vote_against=document.get("vote_against", "—"),
        stance_label=document.get("stance_label", "—"),
        stance_score=_fmt(document.get("stance_score"), "{:+.2f}"),
        forward_guidance=document.get("forward_guidance") or "—",
        growth_assessment=document.get("growth_assessment") or "—",
        inflation_assessment=document.get("inflation_assessment") or "—",
        liquidity_stance=document.get("liquidity_stance") or "—",
        risk_balance=document.get("risk_balance") or "—",
        gdp_proj=_fmt_proj(
            document.get("gdp_projection_curr_value"),
            document.get("gdp_projection_curr_fy"),
        ),
        cpi_proj=_fmt_proj(
            document.get("cpi_projection_curr_value"),
            document.get("cpi_projection_curr_fy"),
        ),
        full_text=(document.get("full_text") or "")[:5000],
    )

    message = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=700,
        temperature=0,            # determinism — same input → same output
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _fmt(value, fmt: str) -> str:
    if value is None:
        return "—"
    try:
        return fmt.format(float(value))
    except (TypeError, ValueError):
        return str(value)


def _fmt_proj(value, fy) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}% for {fy}" if fy else f"{float(value):.1f}%"
