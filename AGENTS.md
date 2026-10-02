# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Purpose
Hackathon MVP: spoilage-aware dispatch recommendations for fresh produce.
Flow: Harvest input → spoilage risk score → vehicle feasibility → load consolidation → route recommendation,
compared against a distance-only baseline. An AI agent (Langflow) orchestrates deterministic Python tools and explains results.

## Hard scope limits (see docs/SOW.md exclusions)
- Max ~3 harvest lots, 2 vehicles. Single shared destination per run.
- Rule-based scoring only. NO ML, marketplace, buyer matching, dynamic pricing, IoT, live GPS, computer vision.
- The LLM never computes routes or risk; Python does.

## Commands
- Install: `pip install -r requirements.txt` (langflow separately: `pip install langflow`)
- Test all: `python -m pytest -q`
- Run single test: `python -m pytest tests/test_freshflow.py::test_shortest_route_is_not_best_route -v`
- UI: `streamlit run app.py`

## Layout
- `data/commodities.json`   commodity classes + handling windows (**PLACEHOLDER** values; all `"source": "TODO"`)
- `data/network.json`       synthetic distance matrix (km), 30 km/h fixed speed
- `data/demo_scenario.json` the one demo scenario (H1 tomato, H2 cabbage, H3 potato; V1, V2)
- `src/spoilage.py`         urgency scoring
- `src/vehicles.py`         feasibility checks
- `src/optimizer.py`        brute-force optimizer + baseline
- `src/tools_api.py`        thin JSON-in/JSON-out wrappers — the only functions Langflow calls
- `langflow/`               system prompt + custom component template
- `app.py`                  Streamlit dashboard
- `tests/test_freshflow.py` all tests; must keep `test_shortest_route_is_not_best_route` passing

## Critical non-obvious patterns

### Data model
- Commodities are looked up case-insensitively; aliases are registered in the same lookup table (e.g., `"tomato"` → `"tomat"`).
- `network.json` keys use `"A|B"` pipe-separated node pairs; both directions are auto-registered on load.
- `optimize_dispatch_tool()` with empty strings silently falls back to the demo scenario — useful during agent testing.

### Scoring math (all in docs/ASSUMPTIONS.md)
- Urgency ratio = `projected_age / max_handling_window`. Thresholds: ≥1.0 CRITICAL, ≥0.75 HIGH, ≥0.50 MEDIUM.
- In-vehicle time counts at **0.5×** field wait (`TRANSIT_EXPOSURE_FACTOR`) — so pickup order changes spoilage scores.
- Penalty per lot = `CLASS_WEIGHT[class] × 100 × ratio` (+ extra `× 300 × excess` if ratio > 1).
- Objective: `alpha×travel_min + beta×detour_km + gamma×spoilage_penalty` (defaults 1, 1, 8).
- `detour_km` = route distance minus the distance-optimal order for the same lot set.

### Conventions
- Python 3.10+; type hints on all public functions; docstrings must state assumptions.
- Every new rule/parameter must be added to `docs/ASSUMPTIONS.md`.
- Never write "prevents spoilage"; write "estimated risk".
- `tools_api.py` must stay thin — all logic lives in the other three src modules.
- Add a test for every new function.
