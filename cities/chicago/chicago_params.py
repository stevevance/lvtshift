"""Single source of truth for the Chicago LVT model.

Imported by the model notebook (cities/chicago/model.ipynb) AND the report/analysis
pipeline (_build_data.py, _report*.py, _compare_areas.py), so the parameters and the
class→category / class→level-of-assessment logic cannot drift between them.

Change a parameter or a mapping here, re-run the notebook (or _build_data.py), and every
downstream report picks it up.
"""

# ---- City / data identifiers ----
CITY_NAME   = 'chicago'
STATE_FIPS  = '17'       # Illinois
COUNTY_FIPS = '031'      # Cook County
TAX_YEAR    = 2024
# The 8 Cook County assessment townships coterminous with the City of Chicago
CHICAGO_TOWNSHIPS = ['70', '71', '72', '73', '74', '75', '76', '77']

# ---- Reform ----
MODEL_TYPE = 'split_rate:2.5'
LAND_IMPROVEMENT_RATIO = 2.5     # capped at 2.5:1 per the Illinois classification limit (Art. IX §4(b))

# ---- Cook County / City of Chicago parameters (TY2024) ----
EQUALIZER           = 3.0355          # IDOR Cook County final multiplier, TY2024
CITY_LEVY           = 1_642_587_611   # City of Chicago Corporate extension (Cook County Clerk 2024 Tax Rate Report)
PUBLISHED_CITY_RATE = 0.0149578       # City of Chicago Corporate agency rate (1.495780%)

_SFR_SUB = {'02', '03', '04', '05', '06', '07', '08', '09', '34', '78'}


def class_to_loa(c):
    """Cook County level of assessment by major class (assessed = market × this)."""
    c = str(c).strip().upper()
    if c in ('EX', 'RR') or c[:1] in ('0', ''):
        return float('nan')          # exempt / railroad — excluded
    d = c[0]
    if d in ('1', '2', '3', '9'):
        return 0.10                  # vacant, residential, multi-family, class-3 incentive
    if d == '4':
        return 0.20                  # not-for-profit
    if d == '5':
        return 0.25                  # commercial / industrial
    if d in ('6', '7', '8'):
        return 0.10                  # incentive, active phase (documented approximation)
    return 0.10


def classify(c):
    """Cook County 3-char class code → standard LVTShift property category."""
    c = str(c).strip().upper()
    if c in ('EX', 'RR'):
        return 'Exempt'
    if len(c) < 3:
        return 'Other'
    mj, sub = c[0], c[1:]
    # Transportation - Parking: automotive improvements (5-22/7-22/8-22, 7-52), gasoline
    # stations (x-23), and minor improvements (x-90, incl. 1-90 and surface parking lots).
    # Checked first so it wins over the major-class buckets below.
    if sub in ('90', '23') or c in ('522', '722', '822', '752'):
        return 'Transportation - Parking'
    if sub == '00' or c == '241':           # 2-41 vacant land under common ownership w/ residence
        return 'Vacant Land'
    if mj == '1':
        return 'Vacant Land'
    if mj == '2':
        if sub in _SFR_SUB:                 return 'Single Family Residential'
        if c in ('210', '295'):             return 'Townhome / Rowhouse'
        if c in ('299', '297'):             return 'Condominium'
        if c == '211':                      return 'Small Multi-Family (2-4 units)'
        if c == '212':                      return 'Mixed Use'
        if c == '225':                      return 'Large Multi-Family (5+ units)'   # SRO
        if c in ('224', '239', '240'):      return 'Agricultural'
        return 'Other Residential'          # 201 garage, 213 co-op, 218/219 B&B, 236, 288
    if mj in ('3', '9'):                    # multi-family (and class-3 incentive)
        if c in ('318', '918'):             return 'Mixed Use'
        if c in ('399', '959'):             return 'Condominium'
        return 'Large Multi-Family (5+ units)'
    if mj == '4':
        return 'Other'                      # not-for-profit (taxable at 20%)
    if mj in ('5', '6', '7', '8'):          # commercial / industrial / incentive
        if mj == '6':                       return 'Industrial'                      # class 6 = industrial incentive
        if c in ('550', '580', '581', '583', '587', '589', '593'): return 'Industrial'   # 5B industrial
        if mj == '8' and c in ('880', '881', '893'):               return 'Industrial'
        if c in ('591', '791', '891', '774'):                      return 'Office / Commercial Condo'
        if c in ('599', '798', '799', '899', '689'):               return 'Office / Commercial Condo'
        if sub in ('16', '29', '46', '48'): return 'Hotel'
        if sub == '92':                     return 'Mixed Use'
        if sub in ('17', '26', '27', '28', '30', '31', '32', '35', '01', '53', '60', '61', '65'):
            return 'Retail / General Commercial'
        return 'Other Commercial'
    return 'Other'
