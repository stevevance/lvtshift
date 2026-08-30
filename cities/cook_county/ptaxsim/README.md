# Cook County class 1-00 at 25% — an independent PTAXSIM analysis

**Question.** What is the aggregate change in property taxes, by class, if Cook County class
**1-00 (vacant land)** — today assessed at **10%** of market value — were instead assessed at
**25%**, the commercial level of assessment, with every other class left alone?

This analysis is **deliberately independent of the LVTShift pipeline**. It shares no code,
no parameters and no class mappings with `../` or `lvt/`. Its only inputs are the Cook County
Assessor's Office [`ptaxsim`](https://github.com/ccao-data/ptaxsim) database and the bill
algorithm published in that package. It is a second opinion on the same question the
LVTShift Cook County scenario answers, arrived at by a separate route.

It is **not a land value tax**: no split rate, no building abatement, no shift of tax onto land.
It reassesses one class inside the existing classified system.

## Data

Everything comes from `ptaxsim-2024.0.0.db` (tax year 2024), the Assessor's published database.
It is ~9.4 GB uncompressed and gitignored; fetch it once:

```bash
mkdir -p data
curl -L -o data/ptaxsim-2024.0.0.db.bz2 \
  https://ccao-data-public-us-east-1.s3.amazonaws.com/ptaxsim/ptaxsim-2024.0.0.db.bz2
bunzip2 data/ptaxsim-2024.0.0.db.bz2
```

Tables used: `pin` (1,859,067 TY2024 parcels — class, Clerk-stage AV, tax code, twelve exemption
columns, and the real billed total), `tax_code`, `agency`, `agency_info`, `eq_factor`, and
`pin_tif_distribution`.

## Method

The bill is transcribed from `ptaxsim::tax_bill` (`R/tax_bill.R`) and `ptaxsim::lookup_*`
(`R/lookup.R`):

```
eav          = round(av_clerk × eq_factor_final)          (class 239 farmland: eav = av)
exe_total    = sum of the twelve exe_* columns
taxable_eav  = max(eav − exe_total, 0), and 0 when eav − exe_total < 150
agency_rate  = agency.total_ext ÷ agency.cty_cook_eav
bill         = taxable_eav × Σ agency_rate over the agencies of the pin's tax code
```

The equalizer (3.0355) is read from the database, not hardcoded. The TIF share
(`pin_tif_distribution.pin_distribution_pct`, PIN-level for tax year 2024 onward) decides where
a bill's dollars *go*, not what the taxpayer *owes*, so it does not enter the bill — but it does
enter the re-strike, because EAV a TIF captures never reaches a taxing district's base.

**Baseline validation.** Rebuilding all 1.86M bills this way gives **$19.2066B** against the
**$19.1924B** actually billed — **+0.074%**, with a median per-parcel error of **0.0003%**.

**The change.** Class 1-00's assessed value is multiplied by 2.5 (10% → 25%). Nothing else moves.

**Two rate modes.**

| Mode | What is held fixed | What moves |
|---|---|---|
| **revenue-neutral** | Every agency's TY2024 extension | Each agency re-strikes its rate over the larger base; every other class's bill falls |
| **fixed-rate** | The TY2024 rates exactly as struck | Only class 1-00's bills; total collections rise |

Under the revenue-neutral mode the re-strike is validated: district revenue returns to
**$17.1310B** against **$17.1302B** today (**+0.005%**). TIF districts collect **+$13.8M**,
because a TIF captures the increment inside its own boundary — that is why the county-wide
total is not exactly flat.

## Running

```bash
pip install pandas numpy pyarrow
python3 build_vacant25.py
```

Writes to `data/`: `by_major_class.csv`, `by_class.csv`, `by_agency_type.csv`, `parcels.parquet`.

## Result

59,145 class 1-00 parcels, **$495.7M** of assessed value, become **$1,239.2M** — about **0.9%**
added to the county's EAV base.

Revenue-neutral, by major class:

| Class | Parcels | Current tax | Change | % |
|---|---:|---:|---:|---:|
| 1 — Vacant land | 61,731 | $138.7M | **+$185.2M** | **+133.5%** |
| 2 — Residential, 1-6 units | 1,587,722 | $11,110.3M | −$96.6M | −0.87% |
| 3 — Multifamily rental, 7+ | 18,958 | $1,219.6M | −$10.6M | −0.87% |
| 4 — Not-for-profit | 450 | $27.8M | −$0.2M | −0.84% |
| 5 — Commercial & industrial | 91,290 | $6,227.3M | −$56.9M | −0.91% |
| 6 — Industrial incentive | 2,427 | $293.5M | −$2.7M | −0.93% |
| 7 — Commercial incentive | 392 | $79.9M | −$0.7M | −0.88% |
| 8 — Commercial/industrial incentive | 1,872 | $84.1M | −$2.6M | **−3.11%** |
| 9 — Multifamily incentive | 941 | $25.3M | −$0.3M | −1.01% |

Class 1's aggregate (+133.5%) is diluted by class **1-90** (2,586 minor-improvement parcels,
untouched, −1.26%). Class **1-00 itself** goes from **$127.0M to $312.4M — +146%**; the median
1-00 bill rises from **$700 to $1,690**.

Class 8 falls three times as far as everyone else because it is the south-suburban incentive
class, and those tax codes hold a far larger share of the county's vacant land.

Under the fixed-rate mode class 1-00 pays **+$190.5M** (+137% for class 1 as a whole), every
other class is unchanged in dollars, and county-wide collections rise **+0.99%**.

## Limitations

- `tif_share` is held at its TY2024 value. A real reassessment would shift the TIF's own
  base-versus-increment split; the effect is second-order and confined to the $13.8M TIF line.
- The transit-TIF carve-out (CPS takes its full share ahead of the TIF) is not modeled. It
  redistributes among districts and does not change any taxpayer's bill.
- Per-agency rounding to the cent, which real bills apply, is not reproduced; it is worth well
  under $0.05 per bill and cancels in aggregate.
- `by_agency_type.csv` splits each bill across its agencies in proportion to their rates, gross
  of TIF diversion, so its revenue-neutral column carries the TIF gain rather than showing zero.
- The behavioral response — owners developing or selling land that has become more expensive
  to hold — is not modeled. This is a first-round incidence estimate.

## Report

`report.html` — a standalone page of the result: the class table with both rate modes, the
class-1 breakout, the bill algorithm, and the two validation checks. Built by hand from the
CSVs above rather than by a script, since the numbers are fixed once `build_vacant25.py` runs.
