"""PIN-level rebuild of the vacant-land reassessment from the Cook County open-data portal.

Used when LVT_COOK_DSN is unset and we need per-parcel identity (PIN) to name the biggest
movers. Same logic and category scheme as _build_vacant_reassessment.py (keep the two in sync),
sourcing from Socrata:
  uzyt-m557  Assessor - Assessed Values   (pin, class, board/certified/mailed bldg & tot)
  nj4t-kc8j  Assessor - Parcel Universe   (pin, tax_code, township, community area, municipality)

Models four scenarios — vacant land (x-00 classes below the 25% commercial rate) reassessed to
20% (partway) or 25% (the commercial maximum), each either revenue-neutral (rates re-struck) or
not (rates unchanged): rn20 / rz20 / rn25 / rz25. Uses chicago_params.vacant00_eav_factor (raises
toward the target, never lowers a parcel already at/above it). Writes
data/parcels_vacant_reassessment_pins.parquet and prints top-15 movers.
"""
import io
import os
import sys
import time
import numpy as np
import pandas as pd
import requests

sys.path.insert(0, '../..'); sys.path.insert(0, '../chicago')
from chicago_params import EQUALIZER, class_to_loa, classify, vacant00_eav_factor
from cook_rates import read_rate_xlsx

TAX_YEAR = 2024
TARGETS = {'20': 0.20, '25': 0.25}   # vacant land 10% -> 20% (partway) and 10% -> 25% (commercial max)
BASE = 'https://datacatalog.cookcountyil.gov/resource'
CACHE = 'data'   # Socrata pulls cached here (gitignored); stable across runs


def _get(dataset, select, where, order, off, page, tries=5):
    params = {'$select': select, '$where': where, '$order': order, '$limit': page, '$offset': off}
    for k in range(tries):
        try:
            r = requests.get(f'{BASE}/{dataset}.csv', params=params, timeout=120)
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text), dtype=str)
        except Exception as e:
            wait = 3 * (k + 1)
            print(f'    retry {dataset}@{off} ({k+1}/{tries}) after {e.__class__.__name__}; wait {wait}s', flush=True)
            time.sleep(wait)
    raise RuntimeError(f'{dataset} failed at offset {off}')


def fetch(dataset, select, where, order, page=50000, tag=None):
    cache = f'{CACHE}/portal_{tag or dataset}.parquet'
    if os.path.exists(cache):
        df = pd.read_parquet(cache)
        print(f'  {dataset}: loaded {len(df):,} from cache', flush=True)
        return df
    frames, off = [], 0
    while True:
        chunk = _get(dataset, select, where, order, off, page)
        frames.append(chunk)
        tot = sum(len(f) for f in frames)
        print(f'  {dataset}: +{len(chunk):,} (total {tot:,})', flush=True)
        if len(chunk) < page:
            break
        off += page
        time.sleep(0.15)
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(cache)
    return df


print('reading assessed values (uzyt-m557)...', flush=True)
av = fetch('uzyt-m557',
           'pin,class,board_bldg,board_tot,certified_bldg,certified_tot,mailed_bldg,mailed_tot',
           f"year='{TAX_YEAR}'", 'row_id', tag='av2024')
print('reading parcel universe (nj4t-kc8j)...', flush=True)
pu = fetch('nj4t-kc8j',
           'pin,tax_code,township_name,chicago_community_area_name,cook_municipality_name',
           f'year={TAX_YEAR}', 'row_id', page=20000, tag='pu2024')

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

# ---- Agency rates (real taxing bodies; drop TIF placeholders) ----
ar = read_rate_xlsx()
ar['AuthorityName'] = ar['AuthorityName'].astype(str)
ar = ar[~ar['AuthorityName'].str.upper().str.startswith('TIF')].drop_duplicates(['Code24', 'Agency'])
ar = ar[['Code24', 'Agency', 'AuthRate24']].rename(columns={'Code24': 'tax_code'})
comp = ar.groupby('tax_code')['AuthRate24'].sum().rename('composite_pct')

# taxable parcels only
keep = ~(df['class'].astype(str).str.upper().isin(['EX', 'RR'])
         | (df['assessed_tot'] <= 0) | df['loa'].isna()
         | ~df['tax_code'].isin(comp.index))
df = df[keep].copy()
df['current_tax'] = df['eav'] * df['tax_code'].map(comp).values / 100.0
comp_pp = df['tax_code'].map(comp)


def restrike(eav_v_col):
    """Revenue-neutral per-agency re-strike (identical to _build_vacant_reassessment.py)."""
    codesum = df.groupby('tax_code').agg(eav=('eav', 'sum'), eav_v=(eav_v_col, 'sum'))
    ag = ar.merge(codesum, on='tax_code', how='inner')
    ag['eav_w'] = ag['eav'] * ag['AuthRate24'] / 100.0
    agg = ag.groupby('Agency').agg(levy=('eav_w', 'sum'), eav_v=('eav_v', 'sum'))
    agg['rate_v'] = np.where(agg['eav_v'] > 0, agg['levy'] / agg['eav_v'] * 100.0, 0.0)
    ar2 = ar.merge(agg[['rate_v']], on='Agency', how='left')
    code_rate_v = df['tax_code'].map(ar2.groupby('tax_code')['rate_v'].sum())
    return df[eav_v_col] * code_rate_v.fillna(0) / 100.0


# ---- Four scenarios: {20,25}% target × {revenue-neutral, rates-unchanged} ----
for tag, target in TARGETS.items():
    ev = f'eav_v{tag}'
    df[ev] = df['eav'] * vacant00_eav_factor(df['class'], df['loa'], new_loa=target)
    df[f'rn{tag}_change'] = restrike(ev) - df['current_tax']
    df[f'rz{tag}_change'] = df[ev] * comp_pp.fillna(0).values / 100.0 - df['current_tax']
    for m in ('rn', 'rz'):
        ch = df[f'{m}{tag}_change']
        df[f'{m}{tag}_pct'] = np.where(df['current_tax'] > 0, ch / df['current_tax'] * 100, np.nan)

# ---- Category: same scheme as _build_vacant_reassessment.py (keep in sync) ----
c = df['class'].astype(str).str.strip().str.upper()
is_reassessed = c.str.endswith('00') & (c.str.len() >= 3) & (df['loa'] < 0.25)
cat = df['class'].map(classify)
cat = np.where(is_reassessed, 'Vacant land (reassessed)', cat)
cat = np.where(c == '241', 'Vacant land · adjacent to residence', cat)
cat = np.where(c == '190', 'Vacant land · minor improvement (1-90)', cat)
cat = np.where(cat == 'Vacant Land', 'Vacant land · already at commercial 25%', cat)
df['PROPERTY_CATEGORY'] = cat

cur = float(df['current_tax'].sum())
print(f'\nΣ current ${cur:,.0f}', flush=True)
for tag in TARGETS:
    rn = float(df[f'rn{tag}_change'].sum()); rz = float(df[f'rz{tag}_change'].sum())
    print(f'  target {tag}%  rev-neutral gap {rn/cur:+.5%}  |  not-neutral extra +${rz:,.0f} ({rz/cur:+.2%})', flush=True)
print(f'  parcels reassessed (x-00 vacant land < 25%): {int(is_reassessed.sum()):,}', flush=True)

df['loc'] = df['chicago_community_area_name'].fillna(df['cook_municipality_name']).fillna(df['township_name'])
cols = ['pin', 'class', 'PROPERTY_CATEGORY', 'township_name', 'loc', 'current_tax', 'rn20_change', 'rn20_pct']


def show(title, d):
    print(f"\n===== {title} =====")
    print(d[cols].to_string(index=False, float_format=lambda x: f'{x:,.0f}'))

show('TOP 15 PAY MORE (revenue-neutral, 20%, vs 2024)', df.nlargest(15, 'rn20_change'))
show('TOP 15 PAY LESS (revenue-neutral, 20%, vs 2024)', df.nsmallest(15, 'rn20_change'))

out_cols = ['pin', 'class', 'PROPERTY_CATEGORY', 'township_name', 'loc', 'tax_code', 'current_tax'] + \
           [f'{m}{tag}_{k}' for tag in TARGETS for m in ('rn', 'rz') for k in ('change', 'pct')]
out = df[out_cols].copy()
out.to_parquet('data/parcels_vacant_reassessment_pins.parquet')
print(f'\ncached {len(out):,} parcels → data/parcels_vacant_reassessment_pins.parquet', flush=True)
