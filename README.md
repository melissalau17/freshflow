# FreshFlow - spoilage-aware dispatch MVP

Three harvests, two vehicles, six possible orders. The shortest route is not always the best one when
produce has different spoilage urgency. FreshFlow scores urgency with rules, optimizes dispatch with
deterministic code, and an AI agent (Langflow) orchestrates the tools and explains the trade-off.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q          # 9 tests, includes SOW acceptance test 8.6
streamlit run app.py         # dashboard
```

## Demo result (synthetic data)
| | Distance-only | FreshFlow |
|---|---|---|
| V1 order | H3 -> H1 | H1 -> H3 |
| Total distance | 53 km | 57 km (+4) |
| Highest-risk lot (H1, tomato) pickup | later | 32 min earlier |

## Langflow agent
1. `pip install langflow`, then `export FRESHFLOW_HOME=$(pwd)` and `langflow run`.
2. Create flow: Chat Input -> Agent -> Chat Output.
3. Paste `langflow/system_prompt.txt` into the Agent's instructions.
4. Add the components from `langflow/freshflow_components.py` (one at a time), enable Tool Mode, connect to the Agent's Tools.
5. Test in the Playground: "I have 120 kg tomatoes harvested 8 hours ago ... what should I send first?"

## Chat tab — environment variables

The **💬 Ask the AI Agent** tab in the dashboard connects to your running Langflow flow.
Set these before launching `streamlit run app.py`:

| Variable | Default | Description |
|---|---|---|
| `LANGFLOW_URL` | `http://localhost:7862` | Base URL of the Langflow server |
| `LANGFLOW_FLOW_ID` | *(required)* | Flow UUID — copy from Langflow UI → open your flow → flow settings (top-right ⚙️) |
| `LANGFLOW_API_KEY` | *(optional)* | Sent as `x-api-key` header; only needed if your Langflow deployment requires authentication |

```bash
export LANGFLOW_URL=http://localhost:7862
export LANGFLOW_FLOW_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
export LANGFLOW_API_KEY=your-key   # omit if not required
streamlit run app.py
```

The dashboard works normally even when the chat tab is not configured — the tab shows a setup notice instead of failing.

## Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Repository: `melissalau17/freshflow` · Branch: `main` · Main file: `app.py`
3. Click **Advanced settings → Secrets** and paste:
   ```toml
   LANGFLOW_URL     = "https://your-langflow-deployment-url"
   LANGFLOW_FLOW_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   LANGFLOW_API_KEY = "sk-..."   # omit if not required
   ```
4. Click **Deploy** — the dashboard deploys without the chat tab until the secrets are filled in.

> The chat tab requires a publicly reachable Langflow instance (not `localhost`).
> The dispatch dashboard works fully without any secrets set.

## Open the folder in IBM Bob
Open this folder in Bob IDE, run `/init`, then follow `docs/BOB_PROMPTS.md`.

## Important caveats
- Risk values are estimates, not observed spoilage. Decision support only.
- See `docs/ASSUMPTIONS.md` for every invented parameter.
