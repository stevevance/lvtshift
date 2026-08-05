"""PIN-level rebuild of the vacant-land reassessment from the Cook County open-data portal.

Used when LVT_COOK_DSN is unset and we need per-parcel identity (PIN) to name the biggest
movers. Same logic as _build_vacant_reassessment.py, sourcing from Socrata:
  uzyt-m557  Assessor - Assessed Values   (pin, class, board/certified/mailed bldg & tot)
  nj4t-kc8j  Assessor - Parcel Universe   (pin, tax_code, township, community area, municipality)
Uses the fixed chicago_params.vacant00_eav_factor (raises toward 20%, never lowers 5-00).
Writes data/parcels_vacant_reassessment_pins.parquet and prints top-15 movers both modes.
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
NEW_LOA = 0.20
BASE = 'https://datacatalog.cookcountyil.gov/resource'
CACHE = '/private/tmp/claude-502/-Users-stevevance-Sites-LVTShift/de15c077-4003-4c18-a61a-9bc36ead8f4c/scratchpad'


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
for c in ['board_bldg','board_tot','certified_bldg','certified_tot','mailed_bldg','mailed_tot']:
    df[c] = pd.to_numeric(df[c], errors='coerce')

def coalesce(*cols):
    out = df[cols[0]].copy()
    for c in cols[1:]: out = out.where(out > 0, df[c])
    return out.fillna(0).clip(lower=0)
df['assessed_bldg'] = coalesce('board_bldg','certified_bldg','mailed_bldg')
df['assessed_tot']  = coalesce('board_tot','certified_tot','mailed_tot')
df['loa'] = df['class'].map(class_to_loa)
df['PROPERTY_CATEGORY'] = df['class'].map(classify)
df.loc[(df['assessed_bldg'] <= 0) & (df['PROPERTY_CATEGORY'] != 'Transportation - Parking'),
       'PROPERTY_CATEGORY'] = 'Vacant Land'

df['eav'] = df['assessed_tot'] * EQUALIZER
df['eav_v'] = df['eav'] * vacant00_eav_factor(df['class'], df['loa'], new_loa=NEW_LOA)

ar = read_rate_xlsx()
ar['AuthorityName'] = ar['AuthorityName'].astype(str)
ar = ar[~ar['AuthorityName'].str.upper().str.startswith('TIF')].drop_duplicates(['Code24','Agency'])
ar = ar[['Code24','Agency','AuthRate24']].rename(columns={'Code24':'tax_code'})
comp = ar.groupby('tax_code')['AuthRate24'].sum().rename('composite_pct')

df['full_exmp'] = (df['class'].astype(str).str.upper().isin(['EX','RR'])
                   | (df['assessed_tot'] <= 0) | df['loa'].isna()
                   | ~df['tax_code'].isin(comp.index)).astype(int)
tax = df['full_exmp'] == 0
df['current_tax'] = 0.0
df.loc[tax, 'current_tax'] = df.loc[tax, 'eav'] * df.loc[tax, 'tax_code'].map(comp).values / 100.0

# per-agency revenue-neutral re-strike
codesum = df[tax].groupby('tax_code').agg(eav=('eav','sum'), eav_v=('eav_v','sum'))
ag = ar.merge(codesum, on='tax_code', how='inner')
ag['eav_w'] = ag['eav'] * ag['AuthRate24'] / 100.0
agg = ag.groupby('Agency').agg(levy=('eav_w','sum'), eav_v=('eav_v','sum'))
agg['rate_v'] = np.where(agg['eav_v'] > 0, agg['levy'] / agg['eav_v'] * 100.0, 0.0)
ar2 = ar.merge(agg[['rate_v']], on='Agency', how='left')
coderates = ar2.groupby('tax_code').agg(code_rate_v=('rate_v','sum'))

df = df.merge(coderates, on='tax_code', how='left')
df['vac_new'] = np.where(tax, df['eav_v'] * df['code_rate_v'].fillna(0) / 100.0, 0.0)
df['vac_change'] = np.where(tax, df['vac_new'] - df['current_tax'], 0.0)
df['vac_pct'] = np.where(tax & (df['current_tax'] > 0), df['vac_change'] / df['current_tax'] * 100, np.nan)

comp_pp = df['tax_code'].map(comp)
df['raise_new'] = np.where(tax, df['eav_v'] * comp_pp.fillna(0).values / 100.0, 0.0)
df['raise_change'] = np.where(tax, df['raise_new'] - df['current_tax'], 0.0)
df['raise_pct'] = np.where(tax & (df['current_tax'] > 0), df['raise_change'] / df['current_tax'] * 100, np.nan)

cur = float(df.loc[tax, 'current_tax'].sum())
print(f"\nΣ current ${cur:,.0f} | rev-neutral gap {df.loc[tax,'vac_new'].sum()/cur-1:+.5%} "
      f"| extra raised ${df.loc[tax,'raise_change'].sum():,.0f} "
      f"| parcels moved DOWN {(df.loc[tax,'raise_change']<-1).sum()} (want 0)", flush=True)

t = df[tax].copy()
t['loc'] = t['chicago_community_area_name'].fillna(t['cook_municipality_name']).fillna(t['township_name'])
t['new_rn'] = t['current_tax'] + t['vac_change']
cols = ['pin','class','PROPERTY_CATEGORY','township_name','loc','current_tax','new_rn','vac_change','vac_pct']

def show(title, d):
    print(f"\n===== {title} =====")
    print(d[cols].to_string(index=False, float_format=lambda x: f'{x:,.0f}'))

show('TOP 15 PAY MORE (revenue-neutral, vs 2024)', t.nlargest(15, 'vac_change'))
show('TOP 15 PAY LESS (revenue-neutral, vs 2024)', t.nsmallest(15, 'vac_change'))

out = t[['pin','class','PROPERTY_CATEGORY','township_name','loc','tax_code','current_tax',
         'vac_change','vac_pct','raise_change','raise_pct']].copy()
out.to_parquet('data/parcels_vacant_reassessment_pins.parquet')
print(f'\ncached {len(out):,} parcels → data/parcels_vacant_reassessment_pins.parquet', flush=True)
