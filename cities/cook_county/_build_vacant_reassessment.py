"""Vacant-land reassessment scenario for Cook County — explicitly NOT a land value tax.

Models the existing classified property tax with exactly one change: vacant land (Cook class
codes ending in "00" — currently assessed at 10% of market value, the residential ratio) is
instead assessed at 20%, a step toward the 25% commercial ratio. Every other class, the levy of
every taxing body, the equalizer, and the rate structure are untouched. Each of the ~900 real
taxing bodies re-strikes its own rate over the (slightly larger) reassessed base, holding its
levy fixed — so the change is revenue-neutral per district. Vacant land's bill rises; every
other parcel's falls by a small amount.

There is no land value tax here: no split rate, no building abatement, no shift of tax onto
land. This is purely a reassessment of one property class within the current system.

Caches data/parcels_vacant_reassessment.parquet for the renderer (_report_vacant_reassessment.py).
"""
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../..'); sys.path.insert(0, '../chicago')
from chicago_params import EQUALIZER, class_to_loa, classify, vacant00_eav_factor
from cook_rates import read_rate_xlsx

TAX_YEAR = 2024
NEW_LOA = 0.20          # vacant land moves from 10% to 20% (commercial is 25%)
DSN = os.environ["LVT_COOK_DSN"]   # Cook County assessor Postgres DSN (password via ~/.pgpass)
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
df['assessed_bldg'] = coalesce('board_bldg','certified_bldg','mailed_bldg')
df['assessed_tot']  = coalesce('board_tot','certified_tot','mailed_tot')
df['loa'] = df['class'].map(class_to_loa)
df['PROPERTY_CATEGORY'] = df['class'].map(classify)
df.loc[(df['assessed_bldg'] <= 0) & (df['PROPERTY_CATEGORY'] != 'Transportation - Parking'),
       'PROPERTY_CATEGORY'] = 'Vacant Land'

# ---- Current EAV and the reassessed EAV (x-00 vacant land moved to 20%) ----
df['eav'] = df['assessed_tot'] * EQUALIZER
df['eav_v'] = df['eav'] * vacant00_eav_factor(df['class'], df['loa'], new_loa=NEW_LOA)
df['is_reassessed'] = (df['eav_v'] != df['eav'])

# ---- Agency rates (real taxing bodies; drop TIF placeholders) ----
ar = read_rate_xlsx()
ar['AuthorityName'] = ar['AuthorityName'].astype(str)
ar = ar[~ar['AuthorityName'].str.upper().str.startswith('TIF')].drop_duplicates(['Code24','Agency'])
ar = ar[['Code24','Agency','AuthRate24']].rename(columns={'Code24':'tax_code'})
comp = ar.groupby('tax_code')['AuthRate24'].sum().rename('composite_pct')

# taxable parcels: valid LOA, value, and a tax code present in the rate file
df['full_exmp'] = (df['class'].astype(str).str.upper().isin(['EX','RR'])
                   | (df['assessed_tot'] <= 0) | df['loa'].isna()
                   | ~df['tax_code'].isin(comp.index)).astype(int)
tax = df['full_exmp'] == 0
df['current_tax'] = 0.0
df.loc[tax, 'current_tax'] = df.loc[tax, 'eav'] * df.loc[tax, 'tax_code'].map(comp).values / 100.0

# ---- Per-agency re-strike: hold each body's levy, spread it over the reassessed base ----
codesum = df[tax].groupby('tax_code').agg(eav=('eav','sum'), eav_v=('eav_v','sum'))
ag = ar.merge(codesum, on='tax_code', how='inner')
ag['eav_w'] = ag['eav'] * ag['AuthRate24'] / 100.0          # this agency's real levy contribution per code
agg = ag.groupby('Agency').agg(levy=('eav_w','sum'), eav_v=('eav_v','sum'))
agg['rate_v'] = np.where(agg['eav_v'] > 0, agg['levy'] / agg['eav_v'] * 100.0, 0.0)   # re-struck % rate

# ---- Aggregate the re-struck agency rates back to a per-code composite ----
ar2 = ar.merge(agg[['rate_v']], on='Agency', how='left')
coderates = ar2.groupby('tax_code').agg(code_rate_v=('rate_v','sum'))

# ---- Per-parcel reassessed bill (taxable only) ----
df = df.merge(coderates, on='tax_code', how='left')
df['vac_new'] = np.where(tax, df['eav_v'] * df['code_rate_v'].fillna(0) / 100.0, 0.0)
df['vac_change'] = np.where(tax, df['vac_new'] - df['current_tax'], 0.0)
df['vac_pct'] = np.where(tax & (df['current_tax'] > 0), df['vac_change'] / df['current_tax'] * 100, np.nan)

# ---- Mode 2: NOT revenue-neutral — keep today's rates, just reassess vacant land ----
# Rates are unchanged, so only vacant land's bill moves (its EAV roughly doubles) and the
# county simply collects the extra. Every other parcel is unchanged; total revenue rises.
comp_pp = df['tax_code'].map(comp)
df['raise_new'] = np.where(tax, df['eav_v'] * comp_pp.fillna(0).values / 100.0, 0.0)
df['raise_change'] = np.where(tax, df['raise_new'] - df['current_tax'], 0.0)
df['raise_pct'] = np.where(tax & (df['current_tax'] > 0), df['raise_change'] / df['current_tax'] * 100, np.nan)

# ---- Validate ----
cur = float(df.loc[tax, 'current_tax'].sum())
new = float(df.loc[tax, 'vac_new'].sum())
raised = float(df.loc[tax, 'raise_new'].sum())
n_re = int(df.loc[tax, 'is_reassessed'].sum())
print(f'Σ current               : ${cur:,.0f}', flush=True)
print(f'Σ revenue-neutral mode  : ${new:,.0f}  (gap {new/cur-1:+.4%})', flush=True)
print(f'Σ not-revenue-neutral   : ${raised:,.0f}  (+${raised-cur:,.0f} extra, {raised/cur-1:+.2%})', flush=True)
print(f'parcels reassessed (x-00 vacant land): {n_re:,}', flush=True)

out = df.loc[tax, ['township_name','PROPERTY_CATEGORY','current_tax',
                   'vac_change','vac_pct','raise_change','raise_pct']].copy()
out = out.rename(columns={'township_name':'township'})
out.to_parquet('data/parcels_vacant_reassessment.parquet')
print(f'cached {len(out):,} parcels → data/parcels_vacant_reassessment.parquet', flush=True)
