---
name: agentkit-history-memory
description: Add persistent threads, analyst context, research memory, and idempotent storage to AgentKit systems. Use when conversations, research threads, or user preferences must survive across runs.
origin: distilled from the user's attached AgentKit docs
---

# AgentKit History And Memory

Use this when an AgentKit system needs persistent conversations, durable analyst context, or long-term memory that outlives a single run.

## History Adapter Basics

Implement the four lifecycle hooks when possible:

- `createThread`
- `get`
- `appendUserMessage`
- `appendResults`

## History Rules

- `createThread` should upsert when `threadId` already exists.
- Save the user message before agents run so intent survives failures.
- Save only new results after a run.
- Use canonical client-generated message IDs and result checksums for idempotency.
- Keep conversation order intact when reconstructing history.

## Pick The Persistence Pattern

- Server-authoritative: client sends `threadId`, backend loads history. Best for restore and cross-device continuity.
- Client-authoritative: client sends full history. Best for fast active sessions.
- Hybrid: server load first, client-authoritative during the live session.

## Memory Design

- Granular tools: `recall_memories`, `create_memories`, `update_memories`, `delete_memories`.
- Consolidated writes: `recall_memories` plus `manage_memories`. Prefer this for deterministic networks.
- Schedule memory writes in background functions so the response path stays fast.
- Lifecycle hooks can recall memory in `onStart` and schedule updates in `onFinish`.

## Recommended Bias

For economics and research systems, prefer deterministic memory updates over fully autonomous memory behavior.

A strong default pattern is:

1. retrieval agent recalls relevant memories
2. analyst agent answers the user
3. updater agent writes a single consolidated memory change set

## Good Durable Context

- watched entities and sectors
- user sector preferences
- standing hypotheses
- taxonomy or definition mappings
- output style conventions that genuinely recur

## Guardrails

- Separate durable facts from temporary reasoning.
- Never store speculative analysis as memory without a review or confidence rule.
- Distinguish thread history from long-term memory.
- Prefer one explicit memory-update stage at the end of a workflow instead of scattered writes.
