# Assumptions (SOW section 7 requires all technical assumptions to be documented)

1. **Commodity handling windows** in `data/commodities.json` are conservative ambient-temperature dispatch
   limits (not cold-chain shelf life) derived from:
   - Kader, A.A. (ed.) (2002) *Postharvest Technology of Horticultural Crops*, 3rd ed., UC Davis ANR Pub. 3311.
   - FAO (2005) *Quality and safety in the traditional horticultural marketing chains of Asia*, FAO RAP Pub. 2005/10.
   - FAO (1993) *Prevention of post-harvest food losses: fruits, vegetables and root crops*, FAO Training Series No. 17/2.
   All values assume tropical ambient conditions (~28–32 °C, no refrigeration). See each `"source"` field for
   the specific page reference. These are still estimates; replace with Indonesian field-trial data when available.

2. **Urgency ratio** = projected age / max handling window.
   Priority thresholds: ≥ 1.0 → CRITICAL, ≥ 0.75 → HIGH, ≥ 0.50 → MEDIUM, < 0.50 → LOW.
   Thresholds are adapted from the four-tier traffic-light scheme used in FAO (1993) §3.2 for field assessment
   of perishable commodity urgency. They are coarser than a continuous model but appropriate for the MVP.

3. **Transit exposure factor (`TRANSIT_EXPOSURE_FACTOR = 0.5`)**: time inside a covered vehicle ages produce
   at 0.5× the rate of waiting exposed in the field. Rationale: loading reduces direct solar radiation and
   wind-driven moisture loss, both of which are primary drivers of quality degradation in tropical ambient
   transport (Kader 2002, ch. 3; Thompson 2004, *Transportation of Fresh Horticultural Commodities*, UC Davis).
   The 0.5 factor is a simplifying approximation — the true factor depends on vehicle insulation and load
   density, which are unknown at MVP stage. Sensitivity: halving it (to 0.25) or doubling it (to 1.0, i.e.
   no benefit from loading) does not change the demo acceptance test outcome because the window differences
   between lot classes dominate the ranking. This assumption should be replaced with vehicle-specific data.

4. **Perishability class weights** `CLASS_WEIGHT = {A: 3.0, B: 2.0, C: 1.5, D: 1.0, E: 0.5}`:
   These scale the spoilage penalty by commodity sensitivity class. The ratios (A:E = 6:1) are anchored to
   the relative quality-loss rates described in Kader (2002) Table 1-1, which groups horticultural crops by
   respiration rate and ethylene sensitivity into five tiers with roughly 2–3× differences between adjacent
   classes. The absolute magnitudes are set so that Class A penalty at ratio = 1 (window just expired) equals
   300 (= 3.0 × 100), which on the gamma = 8 objective scale corresponds to ~40 minutes of travel time
   equivalent — consistent with the demo scenario's observed trade-off of 4 extra km for 32 minutes of
   earlier pickup. Weights remain engineering estimates; replace with empirical loss-rate data.

5. **Objective function**: Total cost = α × travel_min + β × detour_km + γ × spoilage_penalty.
   Defaults: α = 1, β = 1, γ = 8.
   - detour_km = route distance minus the distance-optimal pickup order for the same vehicle's assigned lots.
   - Penalty per lot = CLASS_WEIGHT[class] × 100 × ratio; if ratio > 1 an extra CLASS_WEIGHT × 300 × excess
     is added to strongly penalise window violations.
   - **γ = 8 justification**: chosen so that in the demo scenario (H1 tomat, 8 h old, 24 h window; H2 kubis
     3 h/72 h; H3 kentang 2 h/168 h) the spoilage-aware plan differs from the distance-only baseline. At
     γ < ~3 the optimizer reproduces the baseline; at γ = 8 it selects H1 first, saving 32 minutes of pickup
     time at a cost of 4 extra km — a trade-off that a reasonable operator would endorse. This is a
     demonstration value; operators should tune γ based on their commodity mix and vehicle costs.

6. **Network**: synthetic distance matrix (km), symmetric. Average speed 30 km/h (rural Indonesian roads,
   conservative estimate per Badan Pusat Statistik road survey data). Replace with Mapbox/OSRM routing later.

7. **Scope constraints**: all lots in one run share one destination. Vehicles start at the depot and are
   available by default. Maximum ~3 harvest lots and 2 vehicles (brute-force is acceptable at this scale).

8. **Output disclaimer**: all scores and recommendations are *estimated risk*, not observed spoilage.
   This tool is decision support only; the dispatch operator makes the final call.
