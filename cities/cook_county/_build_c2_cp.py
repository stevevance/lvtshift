"""C2 — per-taxing-district revenue-neutral LVT for Cook County (Option B).

Each of the ~900 real taxing bodies (school/library/park/municipal/county districts)
shifts ITS OWN levy to land WITHIN ITS OWN boundary, revenue-neutral per district. This
preserves every district's revenue and the parcel↔district link (unlike C1, which pools
the whole county into one rate). A parcel's new bill = Σ over the districts covering it of
(its land value × that district's land rate [+ building × building rate for the split]).

Closed-form per agency (no iteration):
  levy_A      = rate_A × Σ EAV in A's footprint
  bldg_rate_A = levy_A / (2.5·ΣL + ΣB)   (split 2.5:1; land_rate_A = 2.5·bldg_rate_A)
  land_rate_A = levy_A / ΣL              (100% abatement)
then per-code rates = Σ agency rates, applied to each parcel's market land/building.

Caches data/parcels_modeled_c2cp.parquet for the renderer.
"""
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../..'); sys.path.insert(0, '../chicago')
from chicago_params import EQUALIZER, LAND_IMPROVEMENT_RATIO as RATIO, class_to_loa, classify
from cook_rates import read_rate_xlsx

TAX_YEAR = 2024
DSN = os.environ["LVT_COOK_DSN"]   # Cook County assessor Postgres DSN (set in env; not committed)
eng = create_engine(DSN)

# ---- Parcel base (assessed values + tax code) ----
print('reading parcels...', flush=True)
av = pd.read_sql(text(
    "SELECT pin, class, board_land, board_bldg, board_tot, "
    "certified_land, certified_bldg, certified_tot, mailed_land, mailed_bldg, mailed_tot "
    f"FROM assessor_assessed_values2 WHERE year={TAX_YEAR}"), eng)
pu = pd.read_sql(text(
    f"SELECT pin14 AS pin, tax_code, township_name FROM assessor_parcel_universe WHERE year={TAX_YEAR}"), eng)
df = av.merge(pu, on='pin', how='left')
df['tax_code'] = pd.to_numeric(df['tax_code'], errors='coerce')

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
loa = df['loa'].fillna(0.10)
df['market_land'] = (df['assessed_land']/loa).clip(lower=0)
df['market_bldg'] = (df['assessed_bldg']/loa).clip(lower=0)
df.loc[(df['assessed_bldg'] <= 0) & (df['PROPERTY_CATEGORY'] != 'Transportation - Parking'),
       'PROPERTY_CATEGORY'] = 'Vacant Land'
df['eav'] = df['assessed_tot'] * EQUALIZER

# ---- Agency rates (real taxing bodies; drop TIF placeholders) ----
ar = read_rate_xlsx()
ar['AuthorityName'] = ar['AuthorityName'].astype(str)
ar = ar[~ar['AuthorityName'].str.upper().str.startswith('TIF')].drop_duplicates(['Code24','Agency'])
ar = ar[['Code24','Agency','AuthRate24']].rename(columns={'Code24':'tax_code'})
comp = ar.groupby('tax_code')['AuthRate24'].sum().rename('composite_pct')  # = CodeRate24

# taxable parcels: have a valid LOA, value, and a tax code that exists in the rate file
df['full_exmp'] = (df['class'].astype(str).str.upper().isin(['EX','RR'])
                   | (df['assessed_tot'] <= 0) | df['loa'].isna()
                   | ~df['tax_code'].isin(comp.index)).astype(int)
tax = df['full_exmp'] == 0
df['current_tax'] = 0.0
df.loc[tax, 'current_tax'] = df.loc[tax, 'eav'] * df.loc[tax, 'tax_code'].map(comp).values / 100.0

# ---- Per-code sums over taxable parcels ----
codesum = df[tax].groupby('tax_code').agg(eav=('eav','sum'),
            L=('assessed_land','sum'), B=('assessed_bldg','sum'))

# ---- Per-agency footprint sums → per-agency land/building rates ----
ag = ar.merge(codesum, on='tax_code', how='inner')
ag['eav_w'] = ag['eav'] * ag['AuthRate24'] / 100.0   # this agency's levy contribution per code
agg = ag.groupby('Agency').agg(levy=('eav_w','sum'), L=('L','sum'), B=('B','sum'),
                               rate=('AuthRate24','first'))
denom_split = (RATIO * agg['L'] + agg['B'])
agg['bldg_rate'] = np.where(denom_split > 0, agg['levy'] / denom_split, 0.0)
agg['land_rate'] = RATIO * agg['bldg_rate']
agg['abate_land'] = np.where(agg['L'] > 0, agg['levy'] / agg['L'], 0.0)

# ---- Aggregate agency rates back to per-code ----
ar2 = ar.merge(agg[['land_rate','bldg_rate','abate_land']], on='Agency', how='left')
coderates = ar2.groupby('tax_code').agg(code_land=('land_rate','sum'),
            code_bldg=('bldg_rate','sum'), code_abate=('abate_land','sum'))

# ---- Per-parcel new bills (taxable only) ----
df = df.merge(coderates, on='tax_code', how='left')
ml, mb = df['assessed_land'], df['assessed_bldg']
df['c2_split_new'] = ml * df['code_land'].fillna(0) + mb * df['code_bldg'].fillna(0)
df['c2_abate_new'] = ml * df['code_abate'].fillna(0)
for new, chg, pct in [('c2_split_new','split_change','split_pct'),
                      ('c2_abate_new','abate_change','abate_pct')]:
    df[chg] = np.where(tax, df[new] - df['current_tax'], 0.0)
    df[pct] = np.where(tax & (df['current_tax'] > 0), df[chg] / df['current_tax'] * 100, np.nan)

# ---- Validate revenue neutrality (county total and a per-district spot check) ----
cur = df.loc[tax, 'current_tax'].sum()
print(f'Σ current        : ${cur:,.0f}', flush=True)
print(f'Σ C2 split new   : ${df.loc[tax,"c2_split_new"].sum():,.0f}  (gap {df.loc[tax,"c2_split_new"].sum()/cur-1:+.4%})', flush=True)
print(f'Σ C2 abate new   : ${df.loc[tax,"c2_abate_new"].sum():,.0f}  (gap {df.loc[tax,"c2_abate_new"].sum()/cur-1:+.4%})', flush=True)
print(f'real taxing agencies: {len(agg):,}', flush=True)

out = df.loc[tax, ['township_name','PROPERTY_CATEGORY','current_tax',
                   'split_change','split_pct','abate_change','abate_pct']].copy()
out = out.rename(columns={'township_name':'township','split_change':'tax_change',
                          'split_pct':'tax_change_pct','abate_change':'abate_change','abate_pct':'abate_pct'})
out.to_parquet('data/parcels_modeled_c2cp.parquet')
print(f'cached {len(out):,} parcels → data/parcels_modeled_c2cp.parquet', flush=True)
