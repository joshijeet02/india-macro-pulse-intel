import os

import anthropic


_SYSTEM = (
    "You are a senior India economist writing an RBI communication note for a rates strategist. "
    "Explain the communication tone, policy bias, and the rates-market implication. "
    "Write three short paragraphs, plain prose, no headers, no throat-clearing."
)


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def generate_communication_brief(document: dict) -> str:
    prompt = f"""RBI Communication Intelligence

TITLE: {document['title']}
TYPE: {document['document_type']}
DATE: {document['published_at']}
SPEAKER: {document.get('speaker') or 'Unknown'}

MODEL SIGNALS:
- Tone label: {document['tone_label']}
- Policy bias: {document['policy_bias']}
- Net score: {document['net_score']}
- Inflation mentions: {document['inflation_mentions']}
- Growth mentions: {document['growth_mentions']}
- Liquidity mentions: {document['liquidity_mentions']}

SUMMARY:
{document.get('summary') or 'No summary provided.'}

TEXT:
{document['full_text'][:4000]}

Write:
1. What changed in the communication stance.
2. What the document implies for the next RBI reaction function.
3. What bond markets should infer from the tone.
"""

    message = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
