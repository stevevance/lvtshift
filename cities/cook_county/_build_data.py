"""COMPUTE step for the Cook County full-composite LVT model (Option C1).

Models the CURRENT full property tax (every taxing body combined) on all ~1.86M Cook
County parcels, then a single revenue-neutral county-wide land shift raising the same
grand total. Caches per-parcel results to data/parcels_modeled.parquet for the renderers.

Current tax  = gross EAV × the parcel's tax-code composite rate (Cook County Clerk
               2024 Tax Code Agency Rate file; gross EAV ⇒ exemptions/TIF not removed —
               documented limitation, same as the Chicago model).
Reform       = one county-wide revenue-neutral 2.5:1 split-rate (and 100% abatement) on
               market-value land/building, raising Σ(current_tax).

Reuses the Cook-County assessment logic (class→LOA, class→category, equalizer, ratio)
from the shared cities/chicago/chicago_params.py — single source of truth.
"""
import os
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../..')          # lvt package
sys.path.insert(0, '../chicago')     # shared Cook-County params (single source of truth)
from lvt.lvt_utils import (calculate_current_tax, model_split_rate_tax,
                           model_full_building_abatement)
from chicago_params import EQUALIZER, LAND_IMPROVEMENT_RATIO as RATIO, class_to_loa, classify

TAX_YEAR = 2024
DATA_DIR = Path('data'); DATA_DIR.mkdir(exist_ok=True)
DSN = os.environ["LVT_COOK_DSN"]   # Cook County assessor Postgres DSN (set in env; not committed)     # password via ~/.pgpass
eng = create_engine(DSN)

# ---- Assessed values (all townships) ----
print('reading assessed values (county-wide)...', flush=True)
av = pd.read_sql(text(
    "SELECT pin, class, township_name, "
    "board_land, board_bldg, board_tot, certified_land, certified_bldg, certified_tot, "
    "mailed_land, mailed_bldg, mailed_tot "
    f"FROM assessor_assessed_values2 WHERE year={TAX_YEAR}"), eng)
print(f'  assessed: {len(av):,}', flush=True)

# ---- Tax code per parcel ----
print('reading tax codes...', flush=True)
pu = pd.read_sql(text(
    f"SELECT pin14 AS pin, tax_code FROM assessor_parcel_universe WHERE year={TAX_YEAR}"), eng)
print(f'  tax codes: {len(pu):,}', flush=True)

# ---- Composite rate per tax code (Cook County Clerk 2024 Tax Code Agency Rate file) ----
rates = pd.read_csv('data/tax_code_rates.csv')
rates['tax_code'] = rates['tax_code'].astype(str).str.strip()

df = av.merge(pu, on='pin', how='left')
df['tax_code'] = df['tax_code'].astype('string').str.strip()
df = df.merge(rates, on='tax_code', how='left')

# ---- Assessment prep (shared logic) ----
def coalesce(*cols):
    out = df[cols[0]].copy()
    for c in cols[1:]: out = out.where(out > 0, df[c])
    return out.fillna(0).clip(lower=0)
for c in ['board_land','board_bldg','board_tot','certified_land','certified_bldg',
          'certified_tot','mailed_land','mailed_bldg','mailed_tot']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['assessed_land'] = coalesce('board_land','certified_land','mailed_land')
df['assessed_bldg'] = coalesce('board_bldg','certified_bldg','mailed_bldg')
df['assessed_tot']  = coalesce('board_tot','certified_tot','mailed_tot')
df['loa'] = df['class'].map(class_to_loa)
df['PROPERTY_CATEGORY'] = df['class'].map(classify)
df['full_exmp'] = (df['class'].astype(str).str.upper().isin(['EX','RR'])
                   | (df['assessed_tot'] <= 0) | df['loa'].isna()
                   | df['composite_rate_pct'].isna()).astype(int)
loa = df['loa'].fillna(0.10)
df['market_land'] = (df['assessed_land']/loa).clip(lower=0)
df['market_bldg'] = (df['assessed_bldg']/loa).clip(lower=0)
df.loc[(df['assessed_bldg'] <= 0) & (df['PROPERTY_CATEGORY'] != 'Transportation - Parking'),
       'PROPERTY_CATEGORY'] = 'Vacant Land'

# ---- Current full-composite tax = gross EAV × tax-code composite rate ----
# millage(per $1000) = rate% × 10  ⇒  tax = eav × rate%/100
df['eav'] = df['assessed_tot'] * EQUALIZER
df['millage_rate'] = df['composite_rate_pct'].fillna(0) * 10.0
_, _, df = calculate_current_tax(df, tax_value_col='eav', millage_rate_col='millage_rate',
                                 exemption_flag_col='full_exmp')
gross_total = float(df['current_tax'].sum())
print(f'  parcels w/o matched rate (excluded): {int(df["composite_rate_pct"].isna().sum()):,}', flush=True)
print(f'  Σ current (gross EAV × composite rate): ${gross_total:,.0f}', flush=True)

# ---- Reform: one county-wide revenue-neutral split-rate + 100% abatement ----
m = df[df['full_exmp'] == 0].copy()
m['taxable_land_value'] = m['market_land']
m['taxable_improvement_value'] = m['market_bldg']
print('modeling county-wide split + abatement...', flush=True)
lm, im, _, gs = model_split_rate_tax(m, 'taxable_land_value', 'taxable_improvement_value',
                                     current_revenue=m['current_tax'].sum(), land_improvement_ratio=RATIO)
_, _, ga = model_full_building_abatement(m.copy(), 'taxable_land_value', 'taxable_improvement_value',
                                         current_revenue=m['current_tax'].sum(), abatement_percentage=1.0)
print(f'  land millage {lm:.4f} / improvement {im:.4f} (2.5:1)', flush=True)

out = pd.DataFrame({
    'township': gs['township_name'].astype('string'),
    'tax_code': gs['tax_code'].astype('string'),
    'PROPERTY_CATEGORY': gs['PROPERTY_CATEGORY'].astype('string'),
    'current_tax': gs['current_tax'].astype('float64'),
    'tax_change': gs['tax_change'].astype('float64'),
    'tax_change_pct': gs['tax_change_pct'].astype('float64'),
    'abate_change': ga['tax_change'].astype('float64'),
    'abate_pct': ga['tax_change_pct'].astype('float64'),
})
out.to_parquet('data/parcels_modeled.parquet')
print(f'cached {len(out):,} modeled parcels (held out {int((df["full_exmp"]==1).sum()):,} exempt/unrated)', flush=True)
print(f'NOTE: validate Σ current ${gross_total:,.0f} vs official TY2024 total extension '
      '(Cook County Clerk Tax Extension & Rates page).', flush=True)
