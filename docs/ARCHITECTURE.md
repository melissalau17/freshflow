# Architecture

Rendered slide version: `architecture.svg` (and `architecture.png`).

```mermaid
flowchart LR
  Op[Operator] -->|chat| Agent[FreshFlow Agent<br/>Langflow + watsonx.ai]
  Op -->|forms| UI[Streamlit dashboard]
  Agent <--> T1[Spoilage Risk tool]
  Agent <--> T2[Dispatch Optimizer tool]
  UI <--> T2
  T1 --> D1[(Commodity parameters)]
  T2 --> E[Vehicle feasibility<br/>Load consolidation<br/>Spoilage-aware routing<br/>vs distance-only baseline]
  E --> D2[(Distance matrix)]
```

- LLM = orchestration and explanation.
- Python = all calculations (risk scoring, feasibility, consolidation, routing).
- The dashboard calls the Python optimizer directly; the agent is a separate chat interface to the same tools.