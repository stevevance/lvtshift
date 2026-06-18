# Cook County — county-wide LVT model

Models a land value tax across **all ~1.77M parcels of Cook County** (tax year 2024), replacing the
full composite property tax. Reuses the Cook-County assessment logic (class → level of assessment,
class → category, equalizer, ratio) from `../chicago/chicago_params.py` — single source of truth.

## Three scenarios
| | Script | What it models |
|---|---|---|
| **C1** | `_build_data.py` → `_report_byarea.py` | One **single county-wide** revenue-neutral rate replacing every levy. *Also pools tax base across the county* — a far bigger change than a land tax. Illustrative. |
| **C2-MV** | `_build_c2.py` → `_report_c2.py` | **Per taxing district** (each of ~900 school/library/park/municipal/county bodies shifts its own levy to land within its own boundary, revenue-neutral per district), on a **market-value** base. Preserves every district's revenue. |
| **C2-CP** | `_build_c2_cp.py` → `_report_c2cp.py` | Same per-district model on an **assessed** (classification-preserved) base — isolates the pure land shift from the classification-removal effect. |

Each scenario produces both a **2.5:1 split-rate** and a **100% building abatement**.

## Data
- **Parcels & assessed values:** Cook County Assessor — Assessed Values (`uzyt-m557`) and Parcel
  Universe (`nj4t-kc8j`). Seeded locally from a Postgres mirror for speed.
- **Composite & per-agency rates:** Cook County Clerk **Tax Extension and Rates**
  (`2024 Tax Code Agency Rate` file). TIF placeholder rows (rate = 1.0) are excluded; the remaining
  ~900 agencies' rates reconcile exactly to each tax code's composite.

## Running
Set the DB DSN (and optionally the rate-file path) in the environment, place the Clerk rate file in
`data/`, then run the build → report for each scenario:
```bash
export LVT_COOK_DSN='postgresql+psycopg2://USER@HOST:PORT/DB?sslmode=require'   # password via ~/.pgpass
export LVT_COOK_RATE_XLSX='data/2024-tax-code-agency-rate-file.xlsx'
python3 _build_c2.py && python3 _report_c2.py        # C2-MV
python3 _build_c2_cp.py && python3 _report_c2cp.py   # C2-CP
python3 _build_data.py && python3 _report_byarea.py  # C1
```

## Limitations
- **Gross EAV** — homeowner/senior exemptions and TIF increment are not removed, so the modeled
  current total (~$20.8B) runs ~8% above the official TY2024 extension (~$19.2B). Dollar levels run
  slightly high; the revenue-neutral distribution is unaffected.
- **Geography** is assessment township (≈38) for now; municipality (~130) would need a boundary join.
- **C1** bundles tax-base pooling with the land shift; the per-district **C2** scenarios are the
  defensible "what does a land tax do" answers.
