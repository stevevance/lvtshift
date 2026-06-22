# Chicago, IL — LVT Model Methodology & Limitations

**Model:** 2.5:1 split-rate, revenue-neutral (canonical). Also computed: 100% building abatement (pure LVT), and a classification-preserved variant.
**Explainer generated:** 2026-06-17  ·  **Probe depth:** deep (cached parcel data present)
**One-line read:** The headline result — Chicago *housing* pays substantially more and *commercial* pays less — is driven **as much by removing Cook County's classification system as by the land shift itself**, because the reform base is market value. Read every category result through that lens.

---

## 1. What was modeled

- **Jurisdiction / body:** City of Chicago — the **City Corporate levy only** (the City's own general + pension extension). Not the composite tax bill.
- **Reform:** revenue-neutral shift toward land. Canonical export is a **2.5:1 split-rate** (land taxed at 2.5× the improvement rate); the ratio is capped at 2.5:1 to respect the Illinois Constitution's classification limit (Art. IX §4(b)). A **100% building abatement** (pure LVT) and a **classification-preserved** variant are also produced for comparison.
- **Revenue-neutrality basis:** the modeled new revenue is solved to equal the modeled current revenue, which is pinned to the official City Corporate levy.

## 2. Data provenance

- **Committed/reproducible source:** Cook County open-data Socrata — **Assessor Assessed Values** (`uzyt-m557`) for land/building/total assessed values, joined to **Parcel Universe** (`nj4t-kc8j`) for location. City = the eight Chicago assessment townships (codes 70–77), which are coterminous with the municipal boundary.
- **Local cache seeding (this run):** because the public Socrata API was severely rate-limited, the cache (`cities/chicago/data/parcels.gpq`) was seeded from the Chicago Cityscape Postgres — assessed values from `assessor_assessed_values2`, and parcel-centroid lat/lon from `parcel_2025_unioned` (`ST_Centroid`, SRID 3435→4326), with a fallback to `propertytaxes_combined.geom_2025`. The data is identical to the public datasets; the committed notebook still references Socrata.
- **Tax year:** **2024** (the data) vs. the official levy figure (also **TY2024**, Cook County Clerk 2024 Tax Rate Report) — no tax-year drift.
- **Parcel count:** 882,904 total (matches Socrata 2024 for townships 70–77). **830,169 modeled** after holding out **52,735 fully-exempt** parcels.
- **Geometry match:** 100.0% of parcels assigned a centroid (67.1% on `pin14`, → 99.7% via `pin10` parent for condo units, → 100% via the `propertytaxes_combined` fallback). Note the geometry vintage is the **2025** parcel file applied to 2024 assessments; ~2,549 taxable PINs (0.3%) that churned between years were dropped earlier in the pure-Socrata build but recovered here.
- **Census join:** 100.0% of parcels matched to a 2022 ACS block group (`std_geoid` non-null = 100%); **median_income non-null = 90.5%** (some block groups lack an income estimate).

## 3. Tax base & millage

- **Assessed → market value.** Cook County publishes *assessed* values, not market values, and assesses by class: residential/vacant/multi-family (major classes 1/2/3/9) at **10%**, not-for-profit (4) at **20%**, commercial/industrial (5) at **25%**, incentive classes (6/7/8) at a reduced **10%** in their active phase. Each parcel's market value = assessed ÷ its class level of assessment. **The split-rate / abatement are applied to market value**, so a dollar of land is taxed uniformly across classes. *(This is the single most consequential modeling choice — see §9.)*
- **Equalized Assessed Value (EAV)** = assessed × the IDOR Cook County **state equalizer 3.0355** (TY2024 final). Current tax is computed on **gross EAV**.
- **Current millage / rate.** The City Corporate levy is spread across taxable EAV at a uniform citywide rate. Rather than look up the rate, the model **derives** it from the levy: `city_rate = CITY_LEVY / Σ(taxable gross EAV)` = **1.1733%**. Published City Corporate rate (Cook County Clerk) = **1.4958%**. The derived rate is lower because gross EAV exceeds the net taxable base by exemptions + TIF (≈ −22% / ratio 0.78) — see §6/§9.
- **Modeled reform millages (2.5:1 split-rate):** land **8.358** / improvement **3.343** per $1,000 of market value (ratio exactly 2.5:1). Abatement variant: land **19.28**, improvement 0.

## 4. Revenue

| | Amount | Source |
|---|---|---|
| Modeled current revenue | **$1,642,587,611** | notebook §4 output; recomputed `Σ current_tax` from export = $1,642,587,611 |
| Revenue-neutral new revenue | **$1,642,587,611** | notebook §5 output; `Σ new_tax` from export = $1,642,587,611 |
| Official figure | **$1,642,587,611** | City of Chicago **Corporate** extension, Cook County Clerk **2024** Tax Rate Report |
| Gap | **0.000%** | exact by construction — the levy is the revenue-neutral target |

Because current revenue is *set* to the official levy, Gate-1 "revenue match" is satisfied by construction; the meaningful check is the **derived rate (1.17%) vs published (1.50%)** — the 0.78 ratio quantifies the gross-EAV gap (§9, limitation 3).

## 5. Levies modeled vs NOT modeled

- **Modeled:** City of Chicago **Corporate** levy only.
- **Excluded** (all also appear on a Chicago parcel's actual bill): Chicago **Board of Education / CPS** (~$3.99B, the largest single levy), City of Chicago **Library** and **School Building & Improvement** funds, **Cook County**, **Forest Preserve**, **Metropolitan Water Reclamation District**, **City Colleges (Community College Dist. 508)**, **Chicago Park District**, and any **Special Service Areas / TIF**. A resident's composite TY2024 rate was ~6.62%; the modeled City Corporate piece is ~1.50% of that. The model therefore describes the incidence of **the City's own levy only**, not a household's total bill. *(No legality brief present to cross-check the vehicle.)*

## 6. Exemptions

- **Full exemptions:** a parcel is flagged fully exempt if its class is **`EX` or `RR`** (railroad, state-assessed) **or** it has zero/blank assessed value. **52,735 parcels (6.0%)** were flagged and **held out of the revenue-neutral solver** and excluded from the export and charts (the export's `is_fully_exempt` sums to 0 because they were removed upstream).
- **Partial / dollar relief: NONE modeled.** The public Assessed Values dataset carries no per-parcel **homeowner / senior / senior-freeze** exemptions, so the model runs on **gross EAV**. This is a deliberate, documented choice (the user opted for gross-EAV over an owner-occupancy proxy). Consequence: the derived city rate (1.17%) sits below the published 1.50%, and absolute burdens are not exemption-exact.
- **Caps / circuit breakers:** none exist for this levy / none modeled.
- **Credits:** none modeled.
- **How they stack:** with no partial relief, no caps, and no credits, the per-parcel computation reduces to: **full-exempt zeroing → millage**. `calculate_current_tax` is called with `exemption_flag_col='full_exmp'` (no `exemption_col`), so exempt parcels are zeroed; everyone else is `taxable_value × millage / 1000`. The split-rate solver receives only the non-exempt set.

## 7. Property categories

- **Source field:** Cook County 3-character **class code** (`class`), mapped via a function (not a flat table) that splits residential subcodes, condos, townhomes, multifamily, mixed-use, and the commercial/industrial/incentive classes per the CCAO *Classifications of Real Property* (rev. 12/16/2024).
- **Transportation - Parking** category: classes ending in **-22** (5-22/7-22/8-22 automotive) + **7-52**, ending in **-23** (gasoline stations), and ending in **-90** (minor improvements incl. 1-90 and surface lots) — and these are **held out of the $0-improvement→Vacant override** so surface lots aren't reabsorbed into Vacant Land.
- **$0-improvement → Vacant Land override:** applied (except Parking). Any parcel with zero building value is recategorized Vacant Land regardless of class.
- **2-41** (vacant land under common ownership w/ adjacent residence) → Vacant Land, taxed at the 10% residential level.
- **Distribution (modeled, non-exempt = 830,169):**

| Category | Parcels | | Category | Parcels |
|---|---|---|---|---|
| Condominium | 287,166 | | Industrial | 11,404 |
| Single Family Residential | 278,520 | | Large Multi-Family (5+) | 11,258 |
| Small Multi-Family (2-4) | 120,202 | | Other Commercial | 4,359 |
| Vacant Land | 39,925 | | Other Residential | 4,309 |
| Townhome / Rowhouse | 23,020 | | Office / Commercial Condo | 4,245 |
| Mixed Use | 15,962 | | Hotel | 436 |
| Transportation - Parking | 15,957 | | Other | 172 |
| Retail / General Commercial | 13,232 | | Agricultural | 2 |

- **Residual buckets are small** (each <0.6%): `Other Residential` (4,309) is **94% Class 2-01 residential garages** (mostly land — explains its near-vacant behavior), `Other Commercial` (4,359), `Other` (172). None exceed the ~10% threshold.

## 8. Land/improvement split + deep-probe diagnostics

Each parcel's land and improvement market values come **directly** from the assessor's separately-set land and building assessed values (÷ class LOA) — *not* an allocation of a combined total. The deep probes confirm this produces real variation:

**Land-ratio uniformity** (land ÷ (land+building), parcels with building>0). A category with >50% of parcels at one modal ratio would be a flat-allocation artifact (the Maricopa case). **None are:**

| Category | n | median land ratio | std | % at modal (2dp) |
|---|---|---|---|---|
| Single Family Residential | 278,520 | 0.252 | 0.123 | 3.5% |
| Condominium | 287,166 | 0.109 | 0.133 | 7.3% |
| Small Multi-Family (2-4) | 120,202 | 0.216 | 0.127 | 4.0% |
| Industrial | 11,404 | 0.723 | 0.302 | 9.0% |
| Office / Commercial Condo | 4,245 | 0.148 | 0.164 | 13.6% |
| Retail / General Commercial | 13,232 | 0.380 | 0.243 | 2.2% |
| Transportation - Parking | 15,899 | 0.944 | 0.243 | 12.0% |
| Other Residential (garages) | 4,309 | 0.919 | 0.195 | 8.9% |

Land ratios are economically sensible (condos & offices building-heavy; industrial, parking, garages land-heavy) and vary widely — **the split-rate genuinely differentiates parcels.**

**Collapsed % change** (share of a category's parcels within 1 percentage-point of the category median, split-rate):

- **Vacant Land: 99.8%** — collapsed, but **inherently, not as an artifact**: a zero-building parcel's % change is `land_millage / (0.10 × equalizer × city_rate) − 1`, in which land value cancels, so every 10%-assessed vacant parcel moves an identical **+134.7%** citywide. This is correct land economics, not a bookkeeping flat-rate.
- **Every other category: 1.7%–16.8%** within 1pp of median — i.e., genuine spread. No collapsed signal in the built categories.

## 9. Limitations (ranked)

1. **Market-value base bundles two reforms.** Because the split/abatement run on market value, they simultaneously (a) shift tax to land and (b) **undo Cook County's classification system** (residential assessed at 10% vs commercial 25%). The large residential *increases* (SFR +29%) and commercial *cuts* (offices −54%, hotels −55%) are driven **mostly by (b)**. The classification-preserved variant isolates (a): there, housing is roughly flat-to-down and land-heavy commercial rises. **Undermines:** any claim that "the land tax raises homeowner bills" — most of that is the assessment-uniformity change, not the land shift.
2. **City Corporate levy only.** Excludes CPS, County, MWRD, parks, library, community college, TIF, SSAs. **Undermines:** any statement about a household's *total* tax bill — this is ~1.5 percentage points of a ~6.6% composite.
3. **Gross EAV — no exemptions applied.** Homeowner/senior exemptions and TIF increment are not subtracted (public data lacks them), so the derived rate (1.17%) is ~22% below the published 1.50% and per-parcel *levels* are not exemption-exact. **Undermines:** precise dollar burdens, especially for owner-occupied homes that currently hold exemptions. (Revenue-neutral *distribution* is robust.)
4. **TY2024 is the City reassessment year.** Board of Review values are still rolling out (~90% Board-certified); the model uses Board → certified → mailed coalesce, so a minority of parcels reflect a pre-final stage. **Undermines:** precision for not-yet-finalized parcels; will settle as certification completes.
5. **Incentive classes (6/7/8) assumed at 10%.** A minority in years 11–12 (15%/20%) or expired would have market value slightly overstated. Small share. **Undermines:** exact treatment of incentive parcels only.
6. **Geometry vintage mismatch.** 2025 parcel centroids on 2024 assessments; resolved to 100% via fallback, but a handful of churned PINs use a parent-parcel centroid. **Undermines:** nothing material for block-group-level equity.
7. **Median_income coverage 90.5%.** Equity-by-income charts exclude ~9.5% of parcels in block groups without an ACS income estimate. **Undermines:** completeness (not direction) of the income-quintile analysis.

## 10. What the model CAN and CANNOT support

- **CAN:** the *distributional direction and relative magnitude* of shifting the City's own levy toward land — which property types and which neighborhoods pay more vs. less, revenue-neutral; the finding that vacant land and (in high-value areas) land-heavy commercial bear large increases while building-heavy commercial cores (Loop, Near North/West) receive large cuts; the geographic North-vs-South contrast; and — via the classification-preserved variant — separation of the land-shift effect from the classification-removal effect.
- **CANNOT:** a household's actual total tax bill (one levy of many); exemption-exact dollar burdens (gross EAV); the effect on a *specific* parcel without its real exemptions and final Board value; or any claim that the headline housing increase is "the land tax" without crediting the classification-removal effect baked into the market-value base.
