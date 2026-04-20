---
name: agentkit-orchestration
description: Design AgentKit and Inngest multi-agent systems with typed state, deterministic routers, focused agents, and MCP-backed tools. Use when building research, coding, or economics workflows that need more structure than a single model call.
origin: distilled from the user's attached AgentKit docs
---

# AgentKit Orchestration

Use this when the task is to design or implement an AgentKit system, not just make one model call.

## Default Shape

- Model the workflow as a state machine.
- Let the router read state and pick the next agent.
- Let agents stay narrow and use tools to write structured state.
- Stop when state says the workflow is done or the iteration cap is hit.

## Pick the Routing Mode

- Code router: default for research, policy, finance, and data workflows where order matters.
- Routing agent: use only when delegation is fuzzy and the cost of a wrong branch is low.
- Hybrid: use an agent for broad classification once, then switch to deterministic routing.

## Workflow

1. Define typed state for progress, artifacts, risks, and completion.
2. Split the job into 2 to 5 agents with one responsibility each.
3. Give each agent only the tools it needs.
4. Use tools to update state in a structured way.
5. Route off `network.state.data`, `callCount`, and `lastResult`.
6. Set `maxIter` or explicit stop conditions.

## State Design

- Put workflow facts in state, not only in conversation history.
- Good state fields: `stage`, `entities`, `evidence`, `plan`, `artifacts`, `openQuestions`, `needsReview`, `done`.
- Prefer enums, booleans, and arrays over freeform status prose.

## Tooling Rules

- Use plain tools for short local actions.
- Use MCP servers when external capabilities already exist and the tool surface is stable.
- Keep tool descriptions concrete and return structured data whenever possible.
- Let tools mutate state or emit durable work, but avoid hiding workflow progress inside unstructured text.

## Economics System Patterns

- Research flow: ingest -> classify -> retrieve -> analyze -> draft -> review.
- Market intelligence: universe builder -> company analyst -> risk checker -> memo writer.
- Forecast workflow: data fetcher -> scenario builder -> model runner -> reviewer.
- Publication, trading, or client-facing recommendations should have a human review gate.

## Guardrails

- Do not let agents coordinate only through prose when state can hold the fact cleanly.
- Do not combine planning, execution, and QA in one agent if auditability matters.
- Do not default to autonomous routing for high-stakes outputs.
- Favor explicit progress markers over "the model will remember to do that next."
