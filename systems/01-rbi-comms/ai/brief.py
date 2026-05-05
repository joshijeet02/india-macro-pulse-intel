"""
AI brief generator for RBI communications.

Hardened per PRD risk R4 (LLM hallucination of vote split / quotes):
  * Strict system prompt: only use facts in the supplied STRUCTURED SIGNALS
    block; if a signal is missing, say so rather than invent
  * Quote attribution required: any direct quote must reference paragraph
    number from the supplied text
  * "DRAFT — verify before publishing" disclaimer in the rendered brief
    (rendered in the UI; this module just produces clean copy)

Note: `temperature` is NOT set — Anthropic deprecated it for the Claude 4.x
extended-thinking models. Determinism comes from the strict prompt structure
plus the visible draft-verify disclaimer in the UI, not from a sampling
temperature parameter.
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


# ─── Query mode: NL Q&A over the corpus ──────────────────────────────────────

_QUERY_SYSTEM_ANALYST = (
    "You are a senior India economist answering an analyst's question about "
    "RBI communications. Use ONLY the cited context passages provided. "
    "Every factual claim must cite the chunk ID it came from in square "
    "brackets, e.g. '[rbi-pr-62515::3]'. If the passages don't actually "
    "answer the question, say so plainly — do not extrapolate."
)

_QUERY_SYSTEM_LAYMAN = (
    "You are a friendly guide explaining RBI policy to someone with no "
    "economics background. Use ONLY the supplied context passages — never "
    "invent dates, numbers, or quotes.\n\n"
    "Avoid jargon. Never use words like 'hawkish', 'basis points', or "
    "'transmission' without immediately explaining them in plain words. "
    "Focus on what the RBI's decisions mean for everyday people — home "
    "loan EMIs, grocery prices, savings rates, jobs.\n\n"
    "Write in short, simple paragraphs. Be warm, clear, and direct. Cite "
    "the source document title and date (not the chunk ID — readers don't "
    "care about IDs)."
)


def _build_query_prompt(question: str, context_window: str) -> str:
    return (
        f"Question:\n{question}\n\n"
        f"Cited context (use only this):\n{context_window}\n"
    )


def _fallback_cited_answer(question: str, rows: list[dict]) -> str:
    """No-API fallback: stitch the top 3 first-sentence snippets with citations."""
    del question
    if not rows:
        return "I couldn't find passages that match your question in the corpus."
    parts = ["Relevant RBI passages point to the following pattern:"]
    for row in rows[:3]:
        snippet = row["text"].strip().split(". ")[0].strip()
        if not snippet.endswith("."):
            snippet = f"{snippet}."
        parts.append(f"{snippet} [{row['chunk_id']}]")
    return "\n\n".join(parts)


def _fallback_layman_answer(question: str, rows: list[dict]) -> str:
    """No-API fallback for layman mode."""
    del question
    if not rows:
        return "I couldn't find anything in the recent RBI documents that matches your question."
    lines = ["Based on recent RBI documents, here's what we found:\n"]
    for row in rows[:3]:
        snippet = row["text"].strip().split(". ")[0].strip()
        if not snippet.endswith("."):
            snippet = f"{snippet}."
        date = row.get("published_at", "")
        title = row.get("title", "RBI Document")[:80]
        lines.append(f"📄 *{title}* ({date}): {snippet}")
    lines.append(
        "\n*Note: Set ANTHROPIC_API_KEY in Streamlit secrets for a full "
        "plain-English summary.*"
    )
    return "\n\n".join(lines)


def _answer_query_impl(question: str, rows: list[dict], system_prompt: str,
                       fallback_fn) -> str:
    """Shared LLM Q&A driver for analyst + layman modes."""
    if not rows:
        return fallback_fn(question, rows)
    from engine.retrieval import build_context_window
    context = build_context_window(rows)
    try:
        client = _client()
    except EnvironmentError:
        return fallback_fn(question, rows)

    try:
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=700,
            system=system_prompt,
            messages=[{"role": "user", "content": _build_query_prompt(question, context)}],
        )
        return message.content[0].text
    except Exception as exc:
        # Network / API error — degrade gracefully so the UI doesn't crash
        return f"{fallback_fn(question, rows)}\n\n_(LLM unavailable: {exc})_"


def answer_query(question: str, rows: list[dict]) -> str:
    """Analyst-mode Q&A: cited, terse, no jargon-defining."""
    return _answer_query_impl(question, rows, _QUERY_SYSTEM_ANALYST, _fallback_cited_answer)


def answer_query_layman(question: str, rows: list[dict]) -> str:
    """Layman-mode Q&A: jargon-free, focused on real-world impact."""
    return _answer_query_impl(question, rows, _QUERY_SYSTEM_LAYMAN, _fallback_layman_answer)
