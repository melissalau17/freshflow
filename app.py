"""FreshFlow dashboard.  Run:  streamlit run app.py"""
import json
import os
import uuid

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Streamlit Community Cloud: copy secrets into os.environ so agent_client.py
# can read them the same way it reads local environment variables.
# On local dev just set the env vars normally; st.secrets will be empty.
# ---------------------------------------------------------------------------
for _key in ("LANGFLOW_URL", "LANGFLOW_FLOW_ID", "LANGFLOW_API_KEY"):
    if _key not in os.environ:
        try:
            _val = st.secrets.get(_key, "")
            if _val:
                os.environ[_key] = _val
        except Exception:
            pass  # st.secrets not available (e.g. during pytest import)

from src.agent_client import agent_configured, ask_agent
from src.optimizer import optimize_dispatch
from src.spoilage import DATA_DIR

st.set_page_config(page_title="FreshFlow", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1180px;}
      h1 {font-size: 2rem; margin-bottom: 0;}
      h2, h3 {font-weight: 600;}
      .ff-tagline {color: #52606d; font-size: 1.02rem; margin: 0.15rem 0 1.4rem 0;}
      .ff-summary {background: #F3F6F4; border-radius: 8px; padding: 1rem 1.2rem; font-size: 1.05rem; line-height: 1.5;}
      .ff-plan {font-size: 1.02rem; line-height: 1.9;}
      .ff-label {color: #52606d; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- data helpers ----------
def _read(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


DEMO = _read("demo_scenario.json")
COMMODITIES = [c["name"] for c in _read("commodities.json")["commodities"]]
LOCATIONS = _read("network.json")["nodes"]

H_COLS = ["harvest_id", "commodity", "location", "volume_kg", "hours_since_harvest", "destination"]
V_COLS = ["vehicle_id", "capacity_kg", "start_location", "available"]


def demo_frames():
    return (pd.DataFrame(DEMO["harvests"])[H_COLS], pd.DataFrame(DEMO["vehicles"])[V_COLS])


def empty_frames():
    return pd.DataFrame(columns=H_COLS), pd.DataFrame(columns=V_COLS)


def reset_inputs(demo):
    st.session_state.base_h, st.session_state.base_v = demo_frames() if demo else empty_frames()
    st.session_state.ver = st.session_state.get("ver", 0) + 1
    st.session_state.result = None


if "base_h" not in st.session_state:
    reset_inputs(demo=True)
    st.session_state.chat = []
    st.session_state.session_id = str(uuid.uuid4())


def validate(h, v):
    """Return (harvest records, vehicle records, list of plain-language errors)."""
    errors = []
    h, v = h.dropna(how="all"), v.dropna(how="all")
    if h.empty:
        errors.append("Add at least one harvest lot.")
    if v.empty:
        errors.append("Add at least one vehicle.")
    if errors:
        return [], [], errors
    for col, label in [("harvest_id", "a Lot ID"), ("commodity", "a commodity"), ("location", "a pickup location"),
                       ("volume_kg", "a volume"), ("hours_since_harvest", "hours since harvest"),
                       ("destination", "a destination")]:
        if h[col].isna().any():
            errors.append(f"Every harvest lot needs {label}.")
    for col, label in [("vehicle_id", "a Vehicle ID"), ("capacity_kg", "a capacity"), ("start_location", "a start location")]:
        if v[col].isna().any():
            errors.append(f"Every vehicle needs {label}.")
    if errors:
        return [], [], errors
    if (h["volume_kg"] <= 0).any():
        errors.append("Volumes must be greater than zero.")
    if (h["hours_since_harvest"] < 0).any():
        errors.append("Hours since harvest cannot be negative.")
    if (v["capacity_kg"] <= 0).any():
        errors.append("Vehicle capacities must be greater than zero.")
    if h["harvest_id"].duplicated().any():
        errors.append("Lot IDs must be unique.")
    if v["vehicle_id"].duplicated().any():
        errors.append("Vehicle IDs must be unique.")
    if h["destination"].nunique() > 1:
        errors.append("This version supports one destination per run. Use the same destination for all lots.")
    if not v["available"].fillna(True).astype(bool).any():
        errors.append("No vehicle is marked available.")
    if errors:
        return [], [], errors
    v = v.assign(available=v["available"].fillna(True).astype(bool))
    return h.to_dict("records"), v.to_dict("records"), []


# ---------- input section ----------
def render_inputs():
    st.subheader("1. Harvests and vehicles")
    st.caption("Edit the tables, or add rows with the + at the bottom. Distances come from the demo network.")
    bcol1, bcol2, _ = st.columns([1.2, 1, 6])
    if bcol1.button("Load demo scenario"):
        reset_inputs(demo=True)
        st.rerun()
    if bcol2.button("Clear all"):
        reset_inputs(demo=False)
        st.rerun()

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Harvest lots**")
        h = st.data_editor(
            st.session_state.base_h, key=f"h{st.session_state.ver}", num_rows="dynamic", hide_index=True,
            
            column_config={
                "harvest_id": st.column_config.TextColumn("Lot ID", width="small"),
                "commodity": st.column_config.SelectboxColumn("Commodity", options=COMMODITIES),
                "location": st.column_config.SelectboxColumn("Pickup location", options=LOCATIONS),
                "volume_kg": st.column_config.NumberColumn("Volume (kg)", min_value=1, step=10),
                "hours_since_harvest": st.column_config.NumberColumn("Hours since harvest", min_value=0, step=0.5),
                "destination": st.column_config.SelectboxColumn("Destination", options=LOCATIONS),
            },
        )
    with right:
        st.markdown("**Vehicles**")
        v = st.data_editor(
            st.session_state.base_v, key=f"v{st.session_state.ver}", num_rows="dynamic", hide_index=True,
            
            column_config={
                "vehicle_id": st.column_config.TextColumn("Vehicle ID", width="small"),
                "capacity_kg": st.column_config.NumberColumn("Capacity (kg)", min_value=1, step=10),
                "start_location": st.column_config.SelectboxColumn("Start location", options=LOCATIONS),
                "available": st.column_config.CheckboxColumn("Available", default=True),
            },
        )

    with st.expander("Advanced settings"):
        gamma = st.slider("How much to weigh spoilage risk against travel time", 0.0, 20.0, 8.0, 0.5)
        st.caption("At 0 the plan is purely distance-based. Higher values accept longer routes to protect "
                   "the most perishable lots. The default (8) is an MVP assumption, documented in docs/ASSUMPTIONS.md.")

    if st.button("Generate dispatch plan", type="primary"):
        harvests, vehicles, errors = validate(h, v)
        if errors:
            for e in errors:
                st.error(e)
            st.session_state.result = None
        else:
            try:
                res = optimize_dispatch(harvests, vehicles, gamma=gamma)
            except (KeyError, ValueError) as e:
                st.error(f"Could not compute a plan: {e}")
                res = None
            st.session_state.result = res


# ---------- results ----------
def priority_style(val):
    colors = {"LOW": "#E6F4EA", "MEDIUM": "#FFF4D6", "HIGH": "#FFE3CC", "CRITICAL": "#FAD4D4"}
    return f"background-color: {colors.get(val, 'white')}"


def render_plan_card(title, summary, destination):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total distance", f"{summary['total_distance_km']:.0f} km")
        c2.metric("Total driving time", f"{summary['total_duration_min']:.0f} min")
        c3.metric("Highest urgency", f"{summary['max_urgency_score']}/100")
        for r in summary["routes"]:
            st.markdown(f"<div class='ff-plan'><b>{r['vehicle_id']}</b>: " +
                        " → ".join(r["sequence"]) + f" → {destination}</div>", unsafe_allow_html=True)


def render_results(res, harvests_df):
    st.subheader("2. Recommendation")
    if not res["feasible"]:
        st.error(res["message"])
        return
    rec, base = res["recommended"], res["baseline_shortest"]
    dest = rec["routes"][0]["stops"][-1]["location"] if rec["routes"] else "destination"
    lot_info = {l["harvest_id"]: l for r in rec["routes"] for l in r["lots"]}
    top = res["highest_risk_lot"]
    top_label = f"{top} ({lot_info[top]['commodity']})"

    if res["same_plan_as_baseline"]:
        st.markdown("<div class='ff-summary'>The shortest route is also the best route for this scenario. "
                    "No trade-off is needed.</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='ff-summary'>The recommended plan is <b>{res['extra_distance_km']:.0f} km longer</b> than the "
            f"shortest-distance plan, but collects the highest-risk lot, <b>{top_label}</b>, "
            f"<b>{res['highest_risk_pickup_minutes_saved']:.0f} minutes earlier</b>.</div>",
            unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        render_plan_card("Shortest-distance plan (baseline)", base, dest)
    with c2:
        render_plan_card("FreshFlow recommendation", rec, dest)

    st.subheader("3. Details")
    st.markdown("**Route timeline**")
    rows = []
    for r in rec["routes"]:
        for i, s in enumerate(r["stops"], 1):
            rows.append({"Vehicle": r["vehicle_id"], "Stop": i, "Location": s["location"],
                         "Collects lot": s["harvest_id"] or "(delivery)", "ETA (min from start)": s["eta_min"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.markdown("**Spoilage risk per lot (recommended plan)**")
    lot_rows = [{"Vehicle": r["vehicle_id"], "Lot": l["harvest_id"], "Commodity": l["commodity"],
                 "Class": l["class"], "Pickup ETA (min)": l["pickup_eta_min"],
                 "Effective age (h)": l["effective_age_h"], "Urgency score": l["urgency_score"],
                 "Priority": l["priority_level"]} for r in rec["routes"] for l in r["lots"]]
    lot_df = pd.DataFrame(lot_rows)
    styler = lot_df.style
    styler = styler.map(priority_style, subset=["Priority"]) if hasattr(styler, "map") \
        else styler.applymap(priority_style, subset=["Priority"])
    st.dataframe(styler, hide_index=True)
    st.caption("Urgency score = projected age of the produce divided by its handling window. "
               "Classes run from A (very perishable) to E (long-lasting).")


# ---------- agent chat ----------
EXAMPLES = {
    "Run the demo scenario": "Run the demo scenario.",
    "Score a tomato lot": "Score a tomato harvested 9 hours ago with 6 hours of transit.",
    "What should I send first?": "I have 120 kg of tomatoes harvested 8 hours ago, 180 kg of cabbage harvested 3 hours ago, "
                                 "and two vehicles. What should I send first?",
}


def render_agent():
    st.subheader("Ask the AI agent")
    st.caption("The agent calls the same calculation tools as the dashboard and explains the result in plain language.")
    if not agent_configured():
        st.info("The agent is not connected yet. Set these before starting the dashboard (see README):\n\n"
                "`LANGFLOW_URL`, `LANGFLOW_FLOW_ID`, and `LANGFLOW_API_KEY` if your Langflow requires one.")
        return

    cols = st.columns(len(EXAMPLES))
    for col, (label, text) in zip(cols, EXAMPLES.items()):
        if col.button(label, key=f"ex_{label}"):
            st.session_state.pending = text

    prompt = st.chat_input("Describe your harvests and vehicles, or ask a question") or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.chat.append({"role": "user", "text": prompt})
        with st.spinner("The agent is working..."):
            ok, reply = ask_agent(prompt, st.session_state.session_id)
        st.session_state.chat.append({"role": "assistant", "text": reply, "ok": ok})

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            (st.error if m.get("ok") is False else st.markdown)(m["text"])


# ---------- page ----------
st.title("FreshFlow")
st.markdown("<div class='ff-tagline'>Dispatch planning for fresh produce that accounts for how quickly each "
            "commodity spoils, not just how far it has to travel.</div>", unsafe_allow_html=True)

tab_plan, tab_agent = st.tabs(["Dispatch plan", "Ask the AI agent"])
with tab_plan:
    render_inputs()
    if st.session_state.get("result"):
        render_results(st.session_state.result, st.session_state.base_h)
with tab_agent:
    render_agent()

st.divider()
st.caption("Decision support only. Risk values are estimates based on MVP parameters, not observed spoilage. "
           "The operator makes the final dispatch decision.")