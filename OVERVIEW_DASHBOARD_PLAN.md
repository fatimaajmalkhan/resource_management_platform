# Plan: Workforce Overview Dashboard

## Context
The app has three views (AI Assistant, Demand Funnel, Resource Master). The Demand Funnel is
**forward-looking / sales-driven** — every metric on it derives from *deals* (hiring demand,
bench-to-deal matching). What's missing is a view of the **current workforce's health**,
independent of any deal: how many people we have, how well they're deployed, what they bill,
and where the data is broken. This is a distinct question from the Funnel ("what must we
acquire") vs. Overview ("what do we have and how is it used").

This adds a fourth view, **Overview**, as the workforce-health home. No deal/demand content,
so it stays clearly separate from the Funnel.

## Grounding: what the real data supports (167 resources)
Verified against the live DB — build only tiles/charts backed by real data:
- **Populated:** headcount (167), practice split (A&I 107 / Software-TSF 60), billable_flag
  (118 true), monthly_billing_usd (sum ≈ $384k), daily_rate_usd (avg ≈ $144), data_flag
  (9 flagged: 9 missing_hr_fields, 2 zero_billing_active), grades (L1–L5 + Contractual),
  bench heuristic (45).
- **EMPTY — do NOT build tiles for these** (would render blank/N/A): `billable_pct` (0 rows),
  `release_date` (0 rows). So: **no "avg billable %" tile and no "roll-off risk" panel.**
  (Note in the UI copy that roll-off tracking activates once release dates are populated.)

## Backend: one new aggregation endpoint
Add `GET /api/overview` to `app/server.py` (reuses `get_benched_resources` already there).
Returns a single JSON payload computed server-side (no row dumps):

```
{
  "headcount": 167,
  "billable_count": 118,
  "bench_count": 45,
  "bench_rate": 26.9,                      # bench/headcount %
  "total_monthly_billing": 384220,
  "avg_daily_rate": 144,
  "flagged_count": 9,
  "by_practice": [ {practice, headcount, billable, benched, monthly_billing} , ... ],
  "by_grade":    [ {grade, count}, ... ],           # sorted L1..L5, Contractual last
  "flags":       [ {flag, count}, ... ]             # missing_hr_fields, zero_billing_active
}
```
- Pure read, no side effects (unlike `/api/funnel` which writes snapshots — deliberately avoid that here).
- Round money/rates to ints; guard empty lists.

## Frontend: new `OverviewDashboard.jsx`
Wire into the existing view-switch pattern (no router): add `overview` to `App.jsx`'s
`activeView` conditional and a nav item (with icon) in `ChatSidebar.jsx`'s `VIEWS` array.
Make it the **default view** on load (`useState('overview')`) since it's the natural home —
Funnel/Resources/Assistant remain one click away. FloatingAssistant already shows on all
non-chat views, so it appears here too automatically.

### Layout (reuses funnel-container shell + existing card styles)
1. **KPI tile row** — 5 stat tiles reusing `.estimate-card`/`.metric-val` styling:
   Headcount · Billable (with % of headcount) · On Bench (with bench-rate %) ·
   Monthly Billing ($) · Data Flags (status-colored if >0).
   These are **stat tiles, not charts** (single headline numbers — correct per dataviz "is it
   even a chart?" heuristic).
2. **Two charts** (inline SVG, no external libs — CSP-safe, matches self-contained ethos):
   - **Headcount by practice** — horizontal bar (magnitude by identity). 2 bars now, but
     scales. Direct value labels.
   - **Grade distribution** — horizontal bar, ordered L1→L5→Contractual (ordinal).
3. **Practice breakdown table** — headcount / billable / benched / monthly billing per
   practice (reuses `.resources-table` + `.table-responsive`).
4. **Data-quality panel** — flag chips with counts, linking conceptually to Resource Master.

### Charts: dataviz method (already partly done)
- Palette **validated** against the app's dark surface `#1a0a12`:
  `#3987e5,#199e70,#c98500,#9085e9,#e66767,#d95926` — ALL CHECKS PASS (worst adjacent CVD
  ΔE 26.3, contrast ≥3:1). App is single-dark-theme, so dark-only (no light mode needed).
- Bars: thin marks, 4px rounded data-end, 2px surface gap, direct value labels (relief rule —
  some hues sit low-contrast so labels are mandatory anyway).
- Hover tooltip per bar (count + % of total). Recessive gridlines, muted axis ink.
- Single-series bars → no legend box (title names it); practice colors follow the entity.

## Files touched
- `app/server.py` — add `GET /api/overview` (+ small aggregation helper).
- `frontend/src/components/OverviewDashboard.jsx` — new.
- `frontend/src/components/icons.jsx` — add one nav icon (e.g. `IconOverview`, a grid/gauge glyph).
- `frontend/src/components/ChatSidebar.jsx` — add nav entry to `VIEWS`.
- `frontend/src/App.jsx` — import + render `overview` branch; default `activeView='overview'`.
- `frontend/src/index.css` — dashboard grid, KPI tile tweaks, SVG chart + tooltip styles.

## Verification
1. `./venv/Scripts/python.exe -c "..."` — hit the aggregation helper directly, assert numbers
   match the DB probe (headcount 167, billing ≈384220, flagged 9).
2. `curl http://127.0.0.1:8000/api/overview` — confirm 200 + shape.
3. `npm run build` — clean compile; server (`--reload`) serves new bundle.
4. Eyeball: load `/`, confirm Overview is default, tiles show real numbers, bars render with
   labels + hover, no empty/N/A tiles, responsive at mobile width.
5. Confirm no regression to Funnel/Resources/Assistant nav.

## Explicitly out of scope (call out, don't silently drop)
- Roll-off risk & billable-% (no data).
- Utilization trend over time (no time-series data; would need snapshots).
- Auth/role-gating of the financial tiles (separate, larger effort — flag that billing $ is
  now visible to anyone).
