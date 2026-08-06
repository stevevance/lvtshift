"""Vacant-land reassessment scenarios for Cook County — explicitly NOT a land value tax.

Models the existing classified property tax with exactly one change: vacant land (Cook class
codes ending in "00" — currently assessed at 10% of market value, the residential ratio) is
instead assessed higher, toward the 25% commercial ratio. Two targets are modeled:
  20%  — partway to the commercial rate
  25%  — the commercial/industrial maximum (the legal ceiling under the classification limit)
and each target is modeled two ways:
  revenue-neutral   — every taxing body holds its levy and re-strikes its rate over the (slightly
                      larger) reassessed base, so vacant land's bill rises and every other
                      parcel's falls a little; total levy fixed per district.
  not revenue-neutral — today's rates are left unchanged, so ONLY vacant land pays more and the
                      county simply collects the extra.
So four scenarios total: rn20 / rz20 / rn25 / rz25 (rn = revenue-neutral, rz = raise).

There is no land value tax here: no split rate, no building abatement, no shift of tax onto
land. This is purely a reassessment of one property class within the current system.

WHICH parcels are reassessed: exactly the x-00 vacant-land classes currently below the 25%
commercial rate (predominantly class 1-00 Vacant Land; plus the handful of 2-00/3-00/8-00 codes).
These carry the "Vacant land (reassessed)" category so the page's "Vacant Land" bar equals exactly
the parcels being reassessed. NOT reassessed, and shown as their own rows for transparency:
class 2-41 (vacant land under common ownership with an adjacent residence — homeowner side-lots),
class 1-90 (Minor Improvement on Vacant Land — a mixed bag; kept in its own bucket, see note in the
report), and the few 5-00 parcels already at the 25% commercial rate.

Data source: the Cook County assessor Postgres mirror (LVT_COOK_DSN). If that is unset, the script
rebuilds from the cached PIN parquet (data/parcels_vacant_reassessment_pins.parquet), reconstructing
gross EAV from the stored current_tax and the composite rate — numerically identical, no DB needed.

Caches data/parcels_vacant_reassessment.parquet for the renderer (_report_vacant_reassessment.py).
"""
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, '../..'); sys.path.insert(0, '../chicago')
from chicago_params import EQUALIZER, class_to_loa, classify, vacant00_eav_factor
from cook_rates import read_rate_xlsx

TAX_YEAR = 2024
TARGETS = {'20': 0.20, '25': 0.25}   # vacant land 10% -> 20% (partway) and 10% -> 25% (commercial max)
PINS_CACHE = 'data/parcels_vacant_reassessment_pins.parquet'

# ---- Agency rates (real taxing bodies; drop TIF placeholders) ----
ar = read_rate_xlsx()
ar['AuthorityName'] = ar['AuthorityName'].astype(str)
ar = ar[~ar['AuthorityName'].str.upper().str.startswith('TIF')].drop_duplicates(['Code24', 'Agency'])
ar = ar[['Code24', 'Agency', 'AuthRate24']].rename(columns={'Code24': 'tax_code'})
comp = ar.groupby('tax_code')['AuthRate24'].sum().rename('composite_pct')

# ---- Taxable parcels: prefer the Postgres mirror, else the cached PIN parquet ----
dsn = os.environ.get('LVT_COOK_DSN')
if dsn:
    from sqlalchemy import create_engine, text
    eng = create_engine(dsn)
    print('reading parcels from Postgres...', flush=True)
    av = pd.read_sql(text(
        "SELECT pin, class, board_land, board_bldg, board_tot, certified_land, certified_bldg, "
        "certified_tot, mailed_land, mailed_bldg, mailed_tot "
        f"FROM assessor_assessed_values2 WHERE year={TAX_YEAR}"), eng)
    pu = pd.read_sql(text(
        f"SELECT pin14 AS pin, tax_code, township_name FROM assessor_parcel_universe WHERE year={TAX_YEAR}"), eng)
    df = av.merge(pu, on='pin', how='left')
    df['tax_code'] = pd.to_numeric(df['tax_code'], errors='coerce')
    for c in ['board_tot', 'certified_tot', 'mailed_tot']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    def coalesce(*cols):
        out = df[cols[0]].copy()
        for c in cols[1:]:
            out = out.where(out > 0, df[c])
        return out.fillna(0).clip(lower=0)
    df['assessed_tot'] = coalesce('board_tot', 'certified_tot', 'mailed_tot')
    df['loa'] = df['class'].map(class_to_loa)
    df['eav'] = df['assessed_tot'] * EQUALIZER
    # taxable: valid LOA, value, and a tax code present in the rate file
    keep = ~(df['class'].astype(str).str.upper().isin(['EX', 'RR'])
             | (df['assessed_tot'] <= 0) | df['loa'].isna()
             | ~df['tax_code'].isin(comp.index))
    df = df[keep].copy()
    df['current_tax'] = df['eav'] * df['tax_code'].map(comp).values / 100.0
else:
    print(f'LVT_COOK_DSN unset — rebuilding from {PINS_CACHE} (gross EAV reconstructed from current_tax)', flush=True)
    df = pd.read_parquet(PINS_CACHE)[['class', 'township_name', 'tax_code', 'current_tax']].copy()
    df['tax_code'] = pd.to_numeric(df['tax_code'], errors='coerce')
    df['loa'] = df['class'].map(class_to_loa)
    cp = df['tax_code'].map(comp)
    df['eav'] = np.where(cp > 0, df['current_tax'] * 100.0 / cp, 0.0)   # current_tax = eav * comp / 100
    df = df[df['eav'] > 0].copy()                                       # cached parquet is already taxable-only

comp_pp = df['tax_code'].map(comp)


def restrike(eav_v_col):
    """Revenue-neutral per-agency re-strike: hold each body's levy, spread it over the reassessed
    base, and re-aggregate the re-struck agency rates to a per-code composite → per-parcel bill."""
    codesum = df.groupby('tax_code').agg(eav=('eav', 'sum'), eav_v=(eav_v_col, 'sum'))
    ag = ar.merge(codesum, on='tax_code', how='inner')
    ag['eav_w'] = ag['eav'] * ag['AuthRate24'] / 100.0                  # this agency's real levy contribution
    agg = ag.groupby('Agency').agg(levy=('eav_w', 'sum'), eav_v=('eav_v', 'sum'))
    agg['rate_v'] = np.where(agg['eav_v'] > 0, agg['levy'] / agg['eav_v'] * 100.0, 0.0)
    ar2 = ar.merge(agg[['rate_v']], on='Agency', how='left')
    code_rate_v = df['tax_code'].map(ar2.groupby('tax_code')['rate_v'].sum())
    return df[eav_v_col] * code_rate_v.fillna(0) / 100.0


# ---- Four scenarios: {20,25}% target × {revenue-neutral, rates-unchanged} ----
for tag, target in TARGETS.items():
    ev = f'eav_v{tag}'
    df[ev] = df['eav'] * vacant00_eav_factor(df['class'], df['loa'], new_loa=target)
    df[f'rn{tag}_change'] = restrike(ev) - df['current_tax']                       # revenue-neutral
    df[f'rz{tag}_change'] = df[ev] * comp_pp.fillna(0).values / 100.0 - df['current_tax']  # rates unchanged
    for m in ('rn', 'rz'):
        ch = df[f'{m}{tag}_change']
        df[f'{m}{tag}_pct'] = np.where(df['current_tax'] > 0, ch / df['current_tax'] * 100, np.nan)

# ---- Category: make the "Vacant Land" bar equal exactly the reassessed parcels ----
# The reassessed set is the x-00 vacant-land classes below the 25% commercial rate (all at 10%, so
# they move under both the 20% and 25% targets). 2-41 side-lots, class 1-90 (minor improvement on
# vacant land), and the few 5-00 parcels already at 25% are vacant land but NOT reassessed, so they
# each get their own label instead of padding the bar (1-90 would otherwise sit inside Parking).
c = df['class'].astype(str).str.strip().str.upper()
is_reassessed = c.str.endswith('00') & (c.str.len() >= 3) & (df['loa'] < 0.25)
cat = df['class'].map(classify)
cat = np.where(is_reassessed, 'Vacant land (reassessed)', cat)
cat = np.where(c == '241', 'Vacant land · adjacent to residence', cat)
cat = np.where(c == '190', 'Vacant land · minor improvement (1-90)', cat)
cat = np.where(cat == 'Vacant Land', 'Vacant land · already at commercial 25%', cat)
df['PROPERTY_CATEGORY'] = cat

# ---- Validate ----
cur = float(df['current_tax'].sum())
print(f'Σ current               : ${cur:,.0f}', flush=True)
for tag in TARGETS:
    rn = float(df[f'rn{tag}_change'].sum()); rz = float(df[f'rz{tag}_change'].sum())
    print(f'target {tag}%%  rev-neutral net ${rn:,.0f} (gap {rn/cur:+.5%})  |  '
          f'not-neutral extra +${rz:,.0f} ({rz/cur:+.2%})', flush=True)
print(f'parcels reassessed (x-00 vacant land < 25%): {int(is_reassessed.sum()):,}', flush=True)

out_cols = ['township_name', 'PROPERTY_CATEGORY', 'current_tax'] + \
           [f'{m}{tag}_{k}' for tag in TARGETS for m in ('rn', 'rz') for k in ('change', 'pct')]
out = df[out_cols].rename(columns={'township_name': 'township'})
out.to_parquet('data/parcels_vacant_reassessment.parquet')
print(f'cached {len(out):,} parcels → data/parcels_vacant_reassessment.parquet', flush=True)
