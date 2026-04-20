---
name: agentkit-durable-workflows
description: Build reliable AgentKit workflows with Inngest-backed multi-step tools, retries, concurrency controls, human approval, and production deployment. Use when work is long-running, failure-prone, or user-facing.
origin: distilled from the user's attached AgentKit docs
---

# AgentKit Durable Workflows

Use this when an AgentKit system has slow tools, external APIs, parallel fan-out, approval steps, or production reliability requirements.

## Core Rule

If a tool is long-running, failure-prone, or blocks on humans, move it into an Inngest function instead of a plain inline tool.

## Multi-Step Tools

- Wrap the tool in `inngest.createFunction`.
- Use `step.ai.infer` for model calls you want retried and offloaded.
- Use `step.run` for deterministic sub-steps and parallel fan-out.
- Register the function in `createServer({ functions: [...] })`.
- Expose the function to the relevant agent as a tool.

## Human In The Loop

- Implement approval or escalation tools with `step.waitForEvent`.
- Match on a stable identifier such as `threadId`, `ticketId`, `jobId`, or `reviewId`.
- Define a timeout path and return a clear fallback result.
- Treat missing approval as a modeled workflow outcome, not an accidental hang.

## Multi-Tenancy And Capacity

- Add `concurrency` keyed by `user_id`, `org_id`, or another tenant key.
- Add throttling or rate limits when one tenant can trigger large crawls or expensive model use.
- Pick tenant keys that match billing, safety, and fairness boundaries.

## Retries

- Default retries are useful for transient failures.
- Lower or disable retries for non-idempotent side effects unless you have compensation logic.
- Throw non-retriable errors for validation failures or missing records.
- Make external writes idempotent before raising retry counts.

## Deployment

- Serve the network over HTTP with `createServer`.
- Set `INNGEST_API_KEY` and `INNGEST_SIGNING_KEY`.
- Sync the deployed app with Inngest so functions and traces appear in the dashboard.
- Use traces to inspect step inputs, outputs, and token-heavy branches before tuning prompts.

## Good Fits In Economics Systems

- Deep research over many sources.
- Scheduled monitoring and alerting.
- Large document parsing and enrichment.
- Vendor or data-provider backfills.
- Approval gates before publishing, emailing, or taking action.

## Checklist

- Stable event names
- Idempotent external writes
- Tenant-aware concurrency
- Explicit timeout and retry policy
- Traceable inputs and outputs

## Guardrails

- Do not bury long crawls or batch jobs inside a synchronous tool call.
- Do not wait on human input without a timeout and correlation key.
- Do not ship production workflows without tenant isolation.
