"""Cook County class 1-00 reassessed at 25% — an independent PTAXSIM analysis.

Standalone. This script imports nothing from LVTShift; its only inputs are the Cook County
Assessor's Office `ptaxsim` database and the bill algorithm published in that package
(ccao-data/ptaxsim, R/tax_bill.R and R/lookup.R). It exists to give a second, independently
derived answer to the same question the LVTShift Cook County model answers, so the two can be
compared without sharing code, parameters or class mappings.

The question: what is the aggregate change in property taxes, by class, if Cook class 1-00
(vacant land) — today assessed at 10% of market value — were instead assessed at 25%, the
commercial level of assessment, with every other class left alone?

Two rate modes are reported:

  revenue-neutral   Each taxing agency holds its TY2024 extension fixed and re-strikes its
                    rate over the larger EAV base. District revenue is preserved exactly;
                    every other class's bill falls slightly. TIF districts collect a little
                    more, reported separately, because a TIF captures the increment inside
                    its own boundary.

  fixed-rate        TY2024 rates are left exactly as struck. Only class 1-00's bills move;
                    every other class is unchanged in dollars and total collections rise.

This is a reassessment of one class inside the existing classified system. It is not a land
value tax: there is no split rate, no building abatement, and no shift of tax onto land.

Bill algorithm, transcribed from ptaxsim::tax_bill:

    eav          = round(av_clerk * eq_factor_final)        (class 239 farmland: eav = av)
    exe_total    = sum of the twelve exe_* columns
    taxable_eav  = max(eav - exe_total, 0), and 0 when eav - exe_total < 150
    agency_rate  = agency.total_ext / agency.cty_cook_eav
    bill         = taxable_eav * sum(agency_rate over the agencies of the pin's tax code)

The TIF share (pin_tif_distribution.pin_distribution_pct, PIN-level for 2024+) decides where
a bill's dollars go, not what the taxpayer owes, so it does not enter the bill. It does enter
the re-strike: EAV a TIF captures never reaches a taxing district's base.

Database (~9.4 GB uncompressed), fetched once:

    curl -L -o data/ptaxsim-2024.0.0.db.bz2 \
      https://ccao-data-public-us-east-1.s3.amazonaws.com/ptaxsim/ptaxsim-2024.0.0.db.bz2
    bunzip2 data/ptaxsim-2024.0.0.db.bz2

Writes by_major_class.csv, by_class.csv, by_agency_type.csv and parcels.parquet into data/.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

TAX_YEAR = 2024
TARGET_CLASS = '100'          # Cook class 1-00, vacant land
OLD_LOA, NEW_LOA = 0.10, 0.25
AV_FACTOR = NEW_LOA / OLD_LOA

HERE = Path(__file__).resolve().parent
DB = HERE / 'data' / f'ptaxsim-{TAX_YEAR}.0.0.db'
OUT = HERE / 'data'

EXE_COLS = ['exe_homeowner', 'exe_senior', 'exe_freeze', 'exe_longtime_homeowner',
            'exe_disabled', 'exe_vet_returning', 'exe_vet_dis_lt50', 'exe_vet_dis_50_69',
            'exe_vet_dis_ge70', 'exe_vet_dis_100', 'exe_wwii', 'exe_abate']

# Cook County's own major-class taxonomy (CCAO class dictionary), not an LVTShift mapping
MAJOR_CLASS_NAME = {
    '0': 'Class 0 — Exempt / no assessment',
    '1': 'Class 1 — Vacant land',
    '2': 'Class 2 — Residential, 1-6 units',
    '3': 'Class 3 — Multifamily rental, 7+ units',
    '4': 'Class 4 — Not-for-profit',
    '5': 'Class 5 — Commercial & industrial',
    '6': 'Class 6 — Industrial incentive',
    '7': 'Class 7 — Commercial incentive',
    '8': 'Class 8 — Commercial/industrial incentive',
    '9': 'Class 9 — Multifamily incentive',
    'EX': 'Exempt',
    'RR': 'Railroad',
}


def taxable_eav(eav: pd.Series, exe_total: pd.Series) -> np.ndarray:
    """ptaxsim's post-exemption taxable EAV: floored at zero, and zeroed below the $150 threshold."""
    net = eav - exe_total
    return np.where(net < 150, 0.0, net.clip(lower=0))


def summarize(pin: pd.DataFrame, key: str) -> pd.DataFrame:
    """Aggregate current and both scenario bills over `key`, with dollar and percent changes."""
    g = pin.groupby(key).agg(
        parcels=('pin', 'size'),
        av=('av', 'sum'),
        av_new=('av_new', 'sum'),
        current_tax=('current_tax', 'sum'),
        neutral_tax=('neutral_tax', 'sum'),
        fixed_tax=('fixed_tax', 'sum'),
    )
    for mode in ('neutral', 'fixed'):
        g[f'{mode}_change'] = g[f'{mode}_tax'] - g['current_tax']
        g[f'{mode}_pct'] = np.where(g['current_tax'] > 0,
                                    g[f'{mode}_change'] / g['current_tax'] * 100, np.nan)
    return g.sort_values('current_tax', ascending=False)


def main() -> None:
    if not DB.exists():
        raise SystemExit(f'PTAXSIM database not found at {DB} — see the module docstring.')
    con = sqlite3.connect(DB)

    # Step 1: equalizer — read from the database rather than hardcoded
    eq_factor = float(pd.read_sql(
        f'SELECT eq_factor_final FROM eq_factor WHERE year = {TAX_YEAR}', con).iloc[0, 0])
    print(f'equalizer (final, TY{TAX_YEAR}): {eq_factor}', flush=True)

    # Step 2: parcels — Clerk-stage AV, class, tax code, exemptions, and the real billed total
    print('reading pin table...', flush=True)
    pin = pd.read_sql(
        f"SELECT pin, class, tax_code_num, tax_bill_total, av_clerk, {', '.join(EXE_COLS)} "
        f'FROM pin WHERE year = {TAX_YEAR}', con)
    pin['class'] = pin['class'].astype(str).str.strip().str.upper()
    pin['av'] = pin['av_clerk'].fillna(0).clip(lower=0)
    pin['exe_total'] = pin[EXE_COLS].fillna(0).sum(axis=1)
    pin['eav'] = np.round(pin['av'] * eq_factor, 0)
    pin.loc[pin['class'] == '239', 'eav'] = pin.loc[pin['class'] == '239', 'av']  # farmland on AV
    pin['taxable_eav'] = taxable_eav(pin['eav'], pin['exe_total'])

    # Step 3: agency rates (extension over county-portion EAV base) and tax-code composites
    tax_code = pd.read_sql(
        f'SELECT tax_code_num, agency_num FROM tax_code WHERE year = {TAX_YEAR}', con)
    agency = pd.read_sql(
        'SELECT a.agency_num, a.cty_cook_eav, a.total_ext, ai.major_type '
        'FROM agency a LEFT JOIN agency_info ai ON a.agency_num = ai.agency_num '
        f'WHERE a.year = {TAX_YEAR} AND a.cty_cook_eav IS NOT NULL', con)
    agency['cty_cook_eav'] = agency['cty_cook_eav'].astype(float)
    agency['rate'] = agency['total_ext'] / agency['cty_cook_eav']
    code_agency = tax_code.merge(agency, on='agency_num', how='inner')
    composite = code_agency.groupby('tax_code_num')['rate'].sum().rename('composite')
    print(f'{len(agency):,} taxing agencies, {len(composite):,} tax codes, '
          f'mean composite rate {composite.mean() * 100:.3f}%', flush=True)

    # Step 4: TIF share — PIN-level for 2024+, exactly one row per PIN
    pin_tif = pd.read_sql(
        'SELECT pin, pin_distribution_pct / 100.0 AS tif_share '
        f'FROM pin_tif_distribution WHERE year = {TAX_YEAR}', con)
    con.close()
    pin = pin.merge(pin_tif, on='pin', how='left')
    pin['tif_share'] = pin['tif_share'].fillna(0.0)

    # Step 5: current bill, validated against the billed totals carried in the database
    pin = pin.merge(composite, left_on='tax_code_num', right_index=True, how='left')
    pin['composite'] = pin['composite'].fillna(0.0)
    pin['current_tax'] = pin['taxable_eav'] * pin['composite']
    billed, modeled = pin['tax_bill_total'].sum(), pin['current_tax'].sum()
    print(f'baseline: modeled ${modeled / 1e9:.4f}B vs billed ${billed / 1e9:.4f}B '
          f'({modeled / billed - 1:+.4%})', flush=True)

    # Step 6: reassess class 1-00 from 10% to 25% of market value
    is_target = pin['class'] == TARGET_CLASS
    pin['av_new'] = np.where(is_target, pin['av'] * AV_FACTOR, pin['av'])
    pin['eav_new'] = np.where(pin['class'] == '239', pin['av_new'],
                              np.round(pin['av_new'] * eq_factor, 0))
    pin['taxable_eav_new'] = taxable_eav(pin['eav_new'], pin['exe_total'])
    print(f'reassessed {int(is_target.sum()):,} class {TARGET_CLASS} parcels: AV '
          f'${pin.loc[is_target, "av"].sum() / 1e9:.3f}B -> '
          f'${pin.loc[is_target, "av_new"].sum() / 1e9:.3f}B', flush=True)

    # Step 7: re-strike each agency's rate over the larger base, holding its extension fixed.
    # Only the non-TIF share of a parcel's added taxable EAV reaches a district's base.
    pin['base_delta'] = (pin['taxable_eav_new'] - pin['taxable_eav']) * (1 - pin['tif_share'])
    code_delta = pin.groupby('tax_code_num')['base_delta'].sum().rename('base_delta')
    agency_delta = (code_agency[['tax_code_num', 'agency_num']]
                    .merge(code_delta, left_on='tax_code_num', right_index=True, how='left')
                    .groupby('agency_num')['base_delta'].sum())
    agency = agency.join(agency_delta, on='agency_num')
    agency['base_delta'] = agency['base_delta'].fillna(0.0)
    agency['base_new'] = agency['cty_cook_eav'] + agency['base_delta']
    agency['rate_new'] = np.where(agency['base_new'] > 0,
                                  agency['total_ext'] / agency['base_new'], 0.0)
    composite_new = (tax_code.merge(agency, on='agency_num', how='inner')
                     .groupby('tax_code_num')['rate_new'].sum().rename('composite_new'))
    pin = pin.merge(composite_new, left_on='tax_code_num', right_index=True, how='left')
    pin['composite_new'] = pin['composite_new'].fillna(0.0)

    pin['neutral_tax'] = pin['taxable_eav_new'] * pin['composite_new']   # districts hold levies
    pin['fixed_tax'] = pin['taxable_eav_new'] * pin['composite']         # rates unchanged
    for mode in ('neutral', 'fixed'):
        pin[f'{mode}_change'] = pin[f'{mode}_tax'] - pin['current_tax']
        pin[f'{mode}_pct'] = np.where(pin['current_tax'] > 0,
                                      pin[f'{mode}_change'] / pin['current_tax'] * 100, np.nan)

    # Step 8: validate the re-strike — district revenue must come back unchanged
    to_dist = lambda col: float((pin[col] * (1 - pin['tif_share'])).sum())
    to_tif = lambda col: float((pin[col] * pin['tif_share']).sum())
    print(f"neutral: to districts ${to_dist('neutral_tax') / 1e9:.4f}B vs "
          f"${to_dist('current_tax') / 1e9:.4f}B today "
          f"({to_dist('neutral_tax') / to_dist('current_tax') - 1:+.5%})", flush=True)
    print(f"neutral: to TIFs      ${to_tif('neutral_tax') / 1e9:.4f}B vs "
          f"${to_tif('current_tax') / 1e9:.4f}B today "
          f"(+${(to_tif('neutral_tax') - to_tif('current_tax')) / 1e6:,.1f}M)", flush=True)
    print(f"fixed:   total        ${pin['fixed_tax'].sum() / 1e9:.4f}B "
          f"(+${(pin['fixed_tax'].sum() - modeled) / 1e6:,.1f}M, "
          f"{pin['fixed_tax'].sum() / modeled - 1:+.4%})", flush=True)

    # Step 9: aggregate by class
    first = pin['class'].str[0]
    pin['major_class'] = np.where(first.str.isdigit(), first, pin['class'])
    pin['major_class_name'] = pin['major_class'].map(MAJOR_CLASS_NAME).fillna('Other')

    by_major = summarize(pin, 'major_class')
    by_major.insert(0, 'name', by_major.index.map(MAJOR_CLASS_NAME).fillna('Other'))
    by_class = summarize(pin, 'class')

    # Collapse to tax codes first (4.5K rows) so the agency join stays small, then split each
    # code's bills across its agencies in proportion to their rates.
    code_tax = pin.groupby('tax_code_num')[['current_tax', 'neutral_tax', 'fixed_tax']].sum()
    ca = code_agency.merge(code_tax, left_on='tax_code_num', right_index=True, how='inner')
    ca = ca.merge(composite, left_on='tax_code_num', right_index=True, how='left')
    ca = ca.merge(agency[['agency_num', 'rate_new']], on='agency_num', how='left')
    ca['share'] = np.where(ca['composite'] > 0, ca['rate'] / ca['composite'], 0.0)
    by_agency_type = pd.DataFrame({
        'current_tax': ca['current_tax'] * ca['share'],
        'neutral_tax': ca['neutral_tax'] * ca['share'],
        'fixed_tax': ca['fixed_tax'] * ca['share'],
        'major_type': ca['major_type'].fillna('UNKNOWN'),
    }).groupby('major_type').sum().sort_values('current_tax', ascending=False)

    OUT.mkdir(exist_ok=True)
    by_major.to_csv(OUT / 'by_major_class.csv')
    by_class.to_csv(OUT / 'by_class.csv')
    by_agency_type.to_csv(OUT / 'by_agency_type.csv')
    pin[['pin', 'class', 'major_class', 'tax_code_num', 'av', 'av_new', 'taxable_eav',
         'taxable_eav_new', 'tif_share', 'current_tax', 'neutral_tax', 'neutral_change',
         'neutral_pct', 'fixed_tax', 'fixed_change', 'fixed_pct']
        ].to_parquet(OUT / 'parcels.parquet', index=False)

    pd.set_option('display.width', 220)
    pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
    print('\n--- aggregate change by major class ---')
    print(by_major[['name', 'parcels', 'current_tax', 'neutral_change', 'neutral_pct',
                    'fixed_change', 'fixed_pct']].to_string())
    print('\n--- class 1 detail ---')
    print(by_class.loc[by_class.index.str.startswith('1'),
                       ['parcels', 'av', 'av_new', 'current_tax', 'neutral_change',
                        'neutral_pct']].to_string())
    print(f'\ncached {len(pin):,} parcels -> data/parcels.parquet')


if __name__ == '__main__':
    main()
