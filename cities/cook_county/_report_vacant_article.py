"""Companion page for the article "Land value tax (LVT) in Cook County".

A long-form evidence page that maps each number in the article to its source. It reuses the
interactive reassessment table from _report_vacant_reassessment.py (same parquet, same
aggregation), defaulting to 25% / revenue-neutral because that is the scenario the article cites.
Writes cook_vacant_article.html (publish as vacant-land-article.html) plus an assets folder.
"""
import json
import re
import shutil
from pathlib import Path
import pandas as pd

BG, INK, BLUE, MUTED, GRID = '#F4F3EF', '#26235C', '#5C6FE3', '#8C8B87', '#DEDDD7'
CLE = 'https://landeconomics.org/lvtshift'
CLERK_REPORT = 'https://www.cookcountyclerkil.gov/sites/default/files/pdfs/2024-tax-rate-report.pdf'
CLASS_DEFS = 'https://prodassets.cookcountyassessoril.gov/s3fs-public/form_documents/Class_codes_definitions_12.16.24.pdf'
# Set to the published article's URL; while empty, the title renders without a link
ARTICLE_URL = ''
ARTICLE_TITLE = 'Land value tax (LVT) in Cook County'

SCEN = ['rn20', 'rz20', 'rn25', 'rz25']
RESEARCH = Path('../../analysis/research')
ASSETS = Path('vacant-land-article-assets')

# Step 1: Copy chart images next to the page
ASSETS.mkdir(exist_ok=True)
IMAGES = {
    'halsted': RESEARCH / '6300_s_halsted' / '6300-s-halsted-chart.png',
    'growth': RESEARCH / 'vacant-built-tax-growth.png',
    'split': RESEARCH / 'split-rate-explainer.png',
}
for src in IMAGES.values():
    shutil.copy(src, ASSETS / src.name)

# Step 2: Interactive reassessment table (same aggregation as the existing vacant-land page)
gs = pd.read_parquet('data/parcels_vacant_reassessment.parquet')
gs['township'] = gs['township'].fillna('(unknown)')


def aggregate(df):
    cats = []
    for cat, d in df.groupby('PROPERTY_CATEGORY'):
        row = {'cat': cat, 'n': int(len(d))}
        for s in SCEN:
            pc, ch = d[f'{s}_pct'], d[f'{s}_change']
            row[f'{s}_pct'] = None if pc.isna().all() else round(float(pc.median()), 1)
            row[f'{s}_medd'] = int(round(float(ch.median())))
            row[f'{s}_net'] = int(ch.sum())
        cats.append(row)
    top = {'n': int(len(df)), 'cats': cats}
    for s in SCEN:
        top[f'{s}_med'] = round(float(df[f'{s}_pct'].median()), 1)
        top[f'{s}_net'] = int(df[f'{s}_change'].sum())
    return top


by_area = {'All Cook County': aggregate(gs)}
for area, d in gs.groupby('township'):
    by_area[str(area).title()] = aggregate(d)
areas = ['All Cook County'] + sorted(a for a in by_area if a != 'All Cook County')
DATA = {'areas': areas, 'byArea': by_area}

allck = by_area['All Cook County']
cat25 = {c['cat']: c for c in allck['cats']}
VAC = cat25['Vacant land (reassessed)']
SFH = cat25['Single Family Residential']
LMF = cat25['Large Multi-Family (5+ units)']
RES_CATS = ['Single Family Residential', 'Condominium', 'Small Multi-Family (2-4 units)',
            'Townhome / Rowhouse', 'Large Multi-Family (5+ units)', 'Other Residential']
res_share = sum(-cat25[c]['rn25_net'] for c in RES_CATS) / VAC['rn25_net']

# Step 3: Redeveloped-lots evidence (TY2023 1-00 lots in a class 2/3/5 building class in TY2024)
EVIDENCE_CSV = 'vacant-land-redeveloped-2023-2024.csv'
rd = pd.read_csv('data/vacant_redeveloped_2023_2024.csv', dtype={'pin': str})
rd.to_csv(EVIDENCE_CSV, index=False)
MAJOR = {'2': 'Residential (class 2)', '3': 'Apartments, 7+ units (class 3)', '5': 'Commercial / industrial (class 5)'}


def evidence_row(label, d, total=False):
    av = d.dropna(subset=['av_2023_board', 'av_2024_board'])
    bl = d.dropna(subset=['tax_bill_2023', 'tax_bill_2024'])
    av23, av24 = av['av_2023_board'].sum(), av['av_2024_board'].sum()
    b23, b24 = bl['tax_bill_2023'].sum(), bl['tax_bill_2024'].sum()
    cls = " class='total'" if total else ''
    return (f"<tr{cls}><td class='cat'>{label}</td><td class='num muted'>{len(d):,}</td>"
            f"<td class='num'>${av23/1e6:,.1f}M</td><td class='num'>${av24/1e6:,.1f}M</td>"
            f"<td class='num up'>+{(av24/av23-1)*100:,.0f}%</td>"
            f"<td class='num'>${b23/1e6:,.1f}M</td><td class='num'>${b24/1e6:,.1f}M</td>"
            f"<td class='num up'>+${(b24-b23)/1e6:,.1f}M</td></tr>")


rd['major'] = rd['class_2024'].str[0]
EV_ROWS = ''.join(evidence_row(MAJOR[m], d) for m, d in rd.groupby('major'))
EV_ROWS += evidence_row('All redeveloped lots', rd, total=True)
ev_av = rd.dropna(subset=['av_2023_board', 'av_2024_board'])
ev_bl = rd.dropna(subset=['tax_bill_2023', 'tax_bill_2024'])
av23, av24 = ev_av['av_2023_board'].sum(), ev_av['av_2024_board'].sum()
b23, b24 = ev_bl['tax_bill_2023'].sum(), ev_bl['tax_bill_2024'].sum()

# Step 4: Class 1-00 parcel counts by year (Socrata nj4t-kc8j; see
# analysis/research/cook_vacant_1_00_counts_by_year.md)
COUNTS = {1999: 89285, 2000: 87741, 2001: 84926, 2002: 81360, 2003: 77660, 2004: 74502,
          2005: 71191, 2006: 69775, 2007: 68528, 2008: 67710, 2009: 66222, 2010: 63929,
          2011: 62770, 2012: 60766, 2013: 60957, 2014: 60783, 2015: 59935, 2016: 60582,
          2017: 60838, 2018: 60591, 2019: 60669, 2020: 61649, 2021: 60923, 2022: 60308,
          2023: 60361, 2024: 59146, 2025: 58428, 2026: 58865}


def counts_svg():
    """Small inline bar chart of class 1-00 parcels by year, with a hover title per bar."""
    w, h, pad_l, pad_b, pad_t = 640, 170, 44, 22, 10
    ymax = 100_000
    years = list(COUNTS)
    bw = (w - pad_l) / len(years)
    out = [f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Class 1-00 parcels by year, 1999 to 2026' "
           f"style='width:100%;height:auto;display:block'>"]
    for t in (0, 25_000, 50_000, 75_000, 100_000):
        y = pad_t + (h - pad_b - pad_t) * (1 - t / ymax)
        out.append(f"<line x1='{pad_l}' x2='{w}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID}'/>")
        out.append(f"<text x='{pad_l-6}' y='{y+3.5:.1f}' text-anchor='end' font-size='10' fill='{MUTED}'>{t//1000}k</text>")
    for i, yr in enumerate(years):
        v = COUNTS[yr]
        bh = (h - pad_b - pad_t) * v / ymax
        x = pad_l + i * bw + 1.5
        col = BLUE if yr == 2026 else '#A9B3EE'
        out.append(f"<rect x='{x:.1f}' y='{h-pad_b-bh:.1f}' width='{bw-3:.1f}' height='{bh:.1f}' rx='2' fill='{col}'>"
                   f"<title>{yr}: {v:,} parcels</title></rect>")
        if yr in (1999, 2008, 2012, 2026):
            out.append(f"<text x='{x+(bw-3)/2:.1f}' y='{h-6}' text-anchor='middle' font-size='10' fill='{MUTED}'>{yr}</text>")
    out.append(f"<text x='{pad_l+1.5+(bw-3)/2:.1f}' y='{h-pad_b-(h-pad_b-pad_t)*COUNTS[1999]/ymax-5:.1f}' "
               f"text-anchor='start' font-size='10.5' fill='{INK}'>89,285</text>")
    xl = pad_l + (len(years) - 1) * bw + 1.5 + (bw - 3)
    out.append(f"<text x='{xl:.1f}' y='{h-pad_b-(h-pad_b-pad_t)*COUNTS[2026]/ymax-5:.1f}' "
               f"text-anchor='end' font-size='10.5' font-weight='bold' fill='{INK}'>58,865</text>")
    out.append('</svg>')
    return ''.join(out)


COUNT_ROWS = ''.join(f"<tr><td>{y}</td><td class='num'>{v:,}</td></tr>" for y, v in COUNTS.items())

# Step 5: 6300 S Halsted case-study table (analysis/research/6300_s_halsted.md)
HALSTED = [
    (2011, '5-92 commercial', '25%', 16670, 79705, 66680, 15617, 2701, 12916),
    (2012, '5-92 commercial', '25%', 23918, 56616, 95672, 14452, 4292, 10160),
    (2013, '5-92 commercial', '25%', 23918, 41325, 95672, 11866, 4350, 7516),
    (2014, '5-92 commercial', '25%', 23918, 66533, 95672, 16782, 4438, 12344),
    None,
    (2015, '1-00 vacant land', '10%', 9567, 0, 95670, 1753, 1753, 0),
    (2016, '1-00 vacant land', '10%', 9567, 0, 95670, 1916, 1916, 0),
    (2025, '1-00 vacant land', '10%', 10437, 0, 104370, 2680, 2680, 0),
]


def halsted_rows():
    out = []
    for r in HALSTED:
        if r is None:
            out.append("<tr class='event'><td colspan='9'>September 2014: building demolished under a City "
                       "emergency wrecking permit after a fire</td></tr>")
            continue
        y, cls, lvl, lav, bav, lmv, bill, tl, tb = r
        out.append(f"<tr><td>{y}</td><td>{cls}</td><td class='num'>{lvl}</td><td class='num'>${lav:,}</td>"
                   f"<td class='num'>${bav:,}</td><td class='num'>${lmv:,}</td><td class='num'><b>${bill:,}</b></td>"
                   f"<td class='num'>${tl:,}</td><td class='num'>${tb:,}</td></tr>")
    return ''.join(out)


def m(x):
    return f"${x/1e6:,.0f} million"


FILL = {
    '__BG__': BG, '__INK__': INK, '__BLUE__': BLUE, '__MUTED__': MUTED, '__GRID__': GRID,
    '__CLE__': CLE, '__CLERK__': CLERK_REPORT, '__CLASSDEFS__': CLASS_DEFS,
    '__ARTICLE_URL__': ARTICLE_URL, '__ARTICLE_TITLE__': ARTICLE_TITLE,
    '__SHIFT__': m(VAC['rn25_net']), '__VACMED__': f"+${VAC['rn25_medd']:,}",
    '__SFHMED__': f"−${-SFH['rn25_medd']:,}", '__LMFMED__': f"−${-LMF['rn25_medd']:,}",
    '__RESSHARE__': f"{res_share*100:.0f}%", '__VACN__': f"{VAC['n']:,}",
    '__RZ25__': m(allck['rz25_net']),
    '__COUNTS_SVG__': counts_svg(), '__COUNT_ROWS__': COUNT_ROWS,
    '__HALSTED_ROWS__': halsted_rows(),
    '__IMG_HALSTED__': f"{ASSETS}/{IMAGES['halsted'].name}",
    '__IMG_GROWTH__': f"{ASSETS}/{IMAGES['growth'].name}",
    '__IMG_SPLIT__': f"{ASSETS}/{IMAGES['split'].name}",
    '__EV_N__': f"{len(rd):,}", '__EV_AVN__': f"{len(ev_av):,}", '__EV_BLN__': f"{len(ev_bl):,}",
    '__EV_AV23__': f"{av23/1e6:,.1f}", '__EV_AV24__': f"{av24/1e6:,.1f}",
    '__EV_AVPCT__': f"{(av24/av23-1)*100:,.0f}", '__EV_BLPCT__': f"{(b24/b23-1)*100:,.0f}",
    '__EV_B23__': f"{b23/1e6:,.1f}", '__EV_B24__': f"{b24/1e6:,.1f}",
    '__EV_BDIFF__': f"{(b24-b23)/1e6:,.0f}", '__EV_ROWS__': EV_ROWS, '__EV_CSV__': EVIDENCE_CSV,
}

html = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Vacant land in Cook County: the evidence</title><style>
 *{box-sizing:border-box}
 body{background:__BG__;color:__INK__;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;margin:0;padding:0 0 80px;
   font-size:16px;line-height:1.6}
 .col{max-width:720px;margin:0 auto;padding:0 20px}
 .wide{max-width:1000px;margin:0 auto;padding:0 20px}
 a{color:__BLUE__}
 .kicker{font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:__MUTED__;margin:34px 0 8px}
 .kicker a{text-decoration:none}
 h1{font-size:30px;line-height:1.2;margin:0 0 12px}
 .dek{font-size:18px;color:#55546f;margin:0 0 18px;line-height:1.5}
 .companion{background:#fff;border:1px solid __GRID__;border-left:4px solid __BLUE__;border-radius:8px;padding:14px 18px;font-size:14.5px}
 nav.toc{font-size:14px;margin:22px 0 0} nav.toc ol{margin:6px 0 0;padding-left:22px} nav.toc li{margin:3px 0}
 h2{font-size:22px;line-height:1.3;margin:52px 0 10px;padding-top:18px;border-top:1px solid __GRID__}
 h2 .n{color:__BLUE__;margin-right:8px}
 h3{font-size:16px;margin:26px 0 6px}
 p{margin:0 0 14px}
 .small{font-size:13px;color:#55546f;line-height:1.55}
 figure{margin:18px 0 24px} figure img{width:100%;height:auto;border:1px solid __GRID__;border-radius:6px;background:#fcfcfb}
 figcaption{font-size:12.5px;color:__MUTED__;margin-top:6px;line-height:1.5}
 .scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0 14px}
 table{border-collapse:collapse;width:100%;font-size:13.5px}
 th,td{padding:7px 9px;border-bottom:1px solid __GRID__;vertical-align:top} th{color:__MUTED__;font-size:11.5px;text-align:left;font-weight:normal}
 .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap} .muted{color:__MUTED__}
 .up{color:__BLUE__;font-weight:bold} .down{color:__INK__;font-weight:bold}
 tr.total td{border-top:2px solid __INK__;font-weight:bold}
 tr.event td{background:#FBEED9;color:#6b5a2a;font-style:italic;font-size:12.5px}
 table.claims td:first-child{width:46%} table.claims td{font-size:14px}
 table.claims .fig{font-weight:bold;white-space:nowrap}
 .notlvt{background:#FBEED9;border:1px solid #E3C77A;border-radius:8px;padding:12px 16px;margin:16px 0;
   font-size:14px;color:#6b5a2a;line-height:1.55}
 .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0 18px}
 .stat{background:#fff;border:1px solid __GRID__;border-radius:8px;padding:12px 14px}
 .stat .big{font-size:24px;font-weight:bold;line-height:1.2} .stat .lab{font-size:12px;color:__MUTED__;margin-top:3px;line-height:1.35}
 details{margin:6px 0 14px;font-size:14px} summary{cursor:pointer;color:__BLUE__}
 .yrs{columns:3;column-gap:18px;max-width:520px} .yrs table{font-size:12.5px} .yrs td{padding:3px 6px}
 /* interactive tool */
 .tool{background:#fff;border:1px solid __GRID__;border-radius:10px;padding:4px 18px 14px;margin:18px 0}
 .controls{display:flex;gap:14px 18px;align-items:center;flex-wrap:wrap;margin:10px 0 6px;
   position:sticky;top:0;background:#fff;padding:10px 0;border-bottom:1px solid __GRID__;z-index:5}
 select{font-size:15px;padding:7px 10px;border:1px solid __GRID__;border-radius:6px;background:#fff;color:__INK__;max-width:100%}
 label{font-size:12px;color:__MUTED__;letter-spacing:.3px;margin-right:6px}
 .toggle{white-space:nowrap}
 .toggle button{font-size:13px;padding:7px 12px;border:1px solid __GRID__;background:#fff;color:__INK__;cursor:pointer}
 .toggle button:first-of-type{border-radius:6px 0 0 6px} .toggle button:last-of-type{border-radius:0 6px 6px 0;border-left:0}
 .toggle button.active{background:__INK__;color:#fff}
 .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:14px 0}
 .sc{background:__BG__;border:1px solid __GRID__;border-radius:8px;padding:12px}
 .sc h4{margin:0 0 4px;font-size:12px;color:__MUTED__;font-weight:normal} .sc .big{font-size:24px;font-weight:bold} .sc .sub{font-size:11.5px;color:__MUTED__;margin-top:3px}
 td.cat{font-weight:bold;min-width:170px} td.barcell{width:40%;min-width:140px}
 .barwrap{position:relative;height:18px} .axis{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:__INK__}
 .bar{position:absolute;top:2px;height:14px;border-radius:2px} .pos{background:__BLUE__} .neg{background:__INK__;opacity:.82}
 footer{color:__MUTED__;font-size:12.5px;border-top:1px solid __GRID__;margin-top:40px;padding-top:14px;line-height:1.55}
 ol.sources{padding-left:20px;font-size:13.5px} ol.sources li{margin:5px 0}
 @media (max-width:560px){h1{font-size:24px}.dek{font-size:16px}h2{font-size:19px}.yrs{columns:2}
   .controls{position:static}}
</style></head><body>

<div class='col'>
<p class='kicker'><a href='index.html'>&larr; LVTShift reports</a> &nbsp;·&nbsp; Article companion</p>
<h1>Vacant land in Cook County: the evidence</h1>
<p class='dek'>Data, methods and caveats behind every number in the article.</p>
<div class='companion'>This page is the evidence companion to <b><a href='__ARTICLE_URL__'>&ldquo;__ARTICLE_TITLE__&rdquo;</a></b>.
Each section below matches a claim in the article and shows where the number comes from. Read the article first,
then use this page to check our work or explore your own township.</div>

<nav class='toc'><b>Contents</b><ol>
<li><a href='#claims'>Where each number comes from</a></li>
<li><a href='#parcels'>How many vacant parcels there are</a></li>
<li><a href='#halsted'>Case study: 6300 S Halsted St</a></li>
<li><a href='#model'>What happens if vacant land is assessed at 25%</a></li>
<li><a href='#redeveloped'>What happens when a vacant lot gets built on</a></li>
<li><a href='#splitrate'>Why this isn&rsquo;t a split-rate land value tax</a></li>
<li><a href='#sources'>Sources</a></li>
</ol></nav>

<h2 id='claims'><span class='n'>1</span>Where each number comes from</h2>
<div class='scroll'><table class='claims'><thead><tr><th>The article says</th><th>Evidence</th></tr></thead><tbody>
<tr><td>Nearly <span class='fig'>59,000</span> vacant land parcels are assessed at 10%</td><td>58,865 class 1-00 parcels in tax year 2026. <a href='#parcels'>Section 2</a></td></tr>
<tr><td>The tax on the land at 6300 S Halsted fell <span class='fig'>60%</span>, from $4,438 to $1,753</td><td>Assessor values and tax bills, 2011–2025. <a href='#halsted'>Section 3</a></td></tr>
<tr><td><span class='fig'>__SHIFT__</span> shifts to vacant land owners at 25%</td><td>Revenue-neutral model, all of Cook County. <a href='#model'>Section 4</a></td></tr>
<tr><td>Median vacant parcel pays <span class='fig'>__VACMED__</span>; single-family home <span class='fig'>__SFHMED__</span>; large multifamily <span class='fig'>__LMFMED__</span></td><td>Same model, median change per parcel. <a href='#model'>Section 4</a></td></tr>
<tr><td><span class='fig'>__EV_N__</span> vacant lots were built on between 2023 and 2024</td><td>Class 1-00 in TY2023, building class in TY2024. <a href='#redeveloped'>Section 5</a></td></tr>
<tr><td>Their assessed value rose <span class='fig'>__EV_AVPCT__%</span>; their bills rose <span class='fig'>$__EV_BDIFF__ million</span></td><td>Board of Review values and actual bills. <a href='#redeveloped'>Section 5</a></td></tr>
<tr><td>Total tax billed in Cook County rose <span class='fig'>4.7%</span> in 2024</td><td>Cook County Clerk, 2024 Tax Rate Report. <a href='#redeveloped'>Section 5</a></td></tr>
</tbody></table></div>

<h2 id='parcels'><span class='n'>2</span>How many vacant parcels there are</h2>
<p>Cook County&rsquo;s classification system assesses vacant land (class 1-00) at <b>10%</b> of market value, the same
assessment level as homes. Commercial and industrial property is assessed at <b>25%</b>. In tax year 2026 there are
<b>58,865</b> class 1-00 parcels. The count fell by about a third between 1999 and 2012 and has stayed near 60,000 since.</p>
<figure>__COUNTS_SVG__<figcaption>Class 1-00 &ldquo;Vacant Land&rdquo; parcels by tax year. 2026 is still being assessed and may change.
Source: Cook County Assessor, <a href='https://datacatalog.cookcountyil.gov/d/nj4t-kc8j'>Parcel Universe</a> on the Cook County Open Data portal (nj4t-kc8j); <a href='https://datacatalog.cookcountyil.gov/resource/nj4t-kc8j.json?$select=year,count(*)&amp;$where=class=%27100%27&amp;$group=year&amp;$order=year'>see the counts query</a>.</figcaption></figure>
<details><summary>Show the counts for every year</summary><div class='yrs'><table>__COUNT_ROWS__</table></div></details>
<p class='small'>Two other classes are also vacant land assessed at 10%: <b>1-90</b> (minor improvement on vacant land,
2,423 parcels in 2026) and <b>2-41</b> (vacant land under common ownership with an adjacent home, 25,050). Counting
them, about 86,000 parcels are vacant land at the 10% level. The article uses the 1-00 count alone. Vacant lots owned by
governments are usually exempt and are not in these counts.</p>

<h2 id='halsted'><span class='n'>3</span>Case study: 6300 S Halsted St</h2>
<p>The corner of 63rd and Halsted in Englewood (PIN 20-20-207-015) held a commercial building until September 2014,
when the City demolished it under an emergency wrecking permit after a fire. The land&rsquo;s value didn&rsquo;t change.
Its classification did: from <b>5-92 commercial</b> (25% assessment level) to <b>1-00 vacant land</b> (10%).</p>
<figure><a href='__IMG_HALSTED__'><img src='__IMG_HALSTED__' alt='Line chart, 2009 to 2025: the land market value at 6300 S Halsted stayed about $95,700 before and after the September 2014 demolition, while the property tax bill fell from $16,782 in 2014 to $1,753 in 2015.'></a>
<figcaption>Land market value = land assessed value ÷ assessment level.</figcaption></figure>
</div>
<div class='wide'><div class='scroll'><table>
<thead><tr><th>Tax year</th><th>Class</th><th class='num'>Assessment level</th><th class='num'>Land AV</th><th class='num'>Building AV</th>
<th class='num'>Land market value</th><th class='num'>Tax bill</th><th class='num'>Tax on land</th><th class='num'>Tax on building</th></tr></thead>
<tbody>__HALSTED_ROWS__</tbody></table></div></div>
<div class='col'>
<p>The tax on the same land fell <b>60%</b>, from $4,438 (2014) to $1,753 (2015), and the total bill fell about
$15,000 a year.</p>
<p class='small'>Land and building shares of each bill are split in proportion to their assessed values. Tax year 2014
bills were paid in 2015. Sources: Cook County Assessor (Board of Review final values); Cook County tax bills via Chicago
Cityscape; City of Chicago building permit 100558613.</p>

<h2 id='model'><span class='n'>4</span>What happens if vacant land is assessed at 25%</h2>
<p>The model raises the assessment level on class 1-00 vacant land from 10% to <b>25%</b>, the commercial level and the
maximum Cook County&rsquo;s classification rules allow. Nothing else changes. In the <b>revenue-neutral</b> version,
each taxing body collects the same total as in tax year 2024, so its rate is recalculated over the larger tax base.
Vacant land pays <b>__SHIFT__</b> more, and every other kind of property pays a little less; about __RESSHARE__ of
that relief goes to residential property.</p>
<div class='stats'>
<div class='stat'><div class='big up'>__VACMED__</div><div class='lab'>median vacant parcel (__VACN__ parcels)</div></div>
<div class='stat'><div class='big'>__SFHMED__</div><div class='lab'>median single-family home</div></div>
<div class='stat'><div class='big'>__LMFMED__</div><div class='lab'>median large multifamily (5+ units)</div></div>
<div class='stat'><div class='big'>__SHIFT__</div><div class='lab'>shifted to vacant land, county-wide</div></div>
</div>
<div class='notlvt'><b>This is not a land value tax.</b> Nothing here shifts tax off buildings and onto land, and there is
no split rate or building abatement. The model changes <b>one thing only</b>, the assessment level on vacant land, and
leaves the rest of the property tax exactly as it is today.</div>
<p>Use the tool to see the result for your township, at 20% or 25%, with or without revenue neutrality. In the
<b>not revenue-neutral</b> version, rates stay the same, so only vacant land pays more and the county collects the extra
(__RZ25__ at 25%).</p>
</div>

<div class='wide'><div class='tool'>
<div class='controls'>
  <div><label for='area'>Township</label><select id='area'></select></div>
  <div class='toggle'><label>Assess vacant land at</label><button data-t='20'>20%</button><button data-t='25' class='active'>25% (max)</button></div>
  <div class='toggle'><label>Mode</label><button data-m='rn' class='active'>Revenue-neutral</button><button data-m='rz'>Not revenue-neutral</button></div>
</div>
<div class='cards' id='cards'></div>
<div class='scroll'><table><thead><tr><th>Category</th><th>Median % change</th><th class='num'>Median %</th><th class='num'>Median $</th><th class='num'>Net change ($)</th><th class='num'>Parcels</th></tr></thead><tbody id='rows'></tbody></table></div>
<p class='small' style='margin-top:10px'>Categories use the Assessor&rsquo;s standard groupings, except that the reassessed vacant lots get
their own <b>&ldquo;Vacant land (reassessed)&rdquo;</b> row. Every other row is <b>not</b> reassessed: under
&ldquo;revenue-neutral&rdquo; it sees a small decrease; under &ldquo;not revenue-neutral&rdquo; it is unchanged.
Positive means the parcel pays more.</p>
</div></div>

<div class='col'>
<div class='notlvt'><b>Exactly which parcels are reassessed.</b> Only the <b>x-00 vacant-land classes currently
assessed below the 25% commercial level</b>: overwhelmingly class <b>1-00 &ldquo;Vacant Land&rdquo;</b> (about
59,000 parcels), plus a few dozen 2-00/3-00/8-00 vacant codes. Those parcels, and <b>only</b> those, make up the
<b>&ldquo;Vacant land (reassessed)&rdquo;</b> row. Two related classes are vacant land but are <b>left untouched</b>,
and are broken out as their own rows so nothing is hidden: <b>class 2-41</b> (&ldquo;vacant land under common ownership
with an adjacent residence,&rdquo; homeowner side lots), and the handful of <b>5-00</b> parcels already assessed at the
25% commercial level. The reform only ever <b>raises</b> toward the target and never lowers.</div>
<div class='notlvt'><b>Why class 1-90 is excluded.</b> The Assessor also has class <b>1-90, &ldquo;Minor Improvement on
Vacant Land&rdquo;</b> (about 2,600 parcels), which it files alongside vacant land. A sample across the county shows it is
<b>too mixed to reassess as one class</b>: some are genuinely empty lots that arguably belong in 1-00; some are
<b>surface parking lots</b> that belong in the commercial 5-90 class; and some are truly undevelopable, like land
<b>under high-tension power lines</b> or <b>beneath the CTA &ldquo;L&rdquo; tracks</b>, that correctly stays 1-90.
Rather than raise the assessment on all of them, we <b>exclude 1-90</b> and flag it for parcel-by-parcel
<b>reclassification</b>.</div>
<p class='small'><b>Model limitation:</b> current tax uses gross equalized value (homeowner and senior exemptions and TIF
are not removed), so dollar levels run about 8% above the official $19.2 billion extension. The revenue-neutral
distribution is unaffected. Levies and rates: Cook County Clerk, tax year 2024 tax code agency rate file; each of about
900 taxing bodies (TIF districts excluded) recalculates its own rate.</p>

<h2 id='redeveloped'><span class='n'>5</span>What happens when a vacant lot gets built on</h2>
<p>Of the 60,361 parcels classed 1-00 in tax year 2023, <b>__EV_N__</b> had a building by tax year 2024 (they moved
to a residential, apartment or commercial class). Their combined assessed value rose from <b>$__EV_AV23__ million to
$__EV_AV24__ million (+__EV_AVPCT__%)</b>, and their combined tax bills rose __EV_BLPCT__%, from <b>$__EV_B23__ million to
$__EV_B24__ million</b>: about <b>$__EV_BDIFF__ million more billed in a single year</b>.</p>
<figure><a href='__IMG_GROWTH__'><img src='__IMG_GROWTH__' alt='Bar chart: tax bills on vacant lots that got a building rose 882% from tax year 2023 to 2024, compared with 6.3% in Chicago, 4.7% in all of Cook County, 3.7% in the north suburbs and 3.0% in the south suburbs.'></a>
<figcaption>Cook County, Chicago and suburban totals: Cook County Clerk, <a href='__CLERK__'>2024 Tax Rate Report</a>.</figcaption></figure>
</div>
<div class='wide'><div class='scroll'><table><thead><tr><th>Became</th><th class='num'>Parcels</th><th class='num'>Assessed value, 2023</th>
<th class='num'>Assessed value, 2024</th><th class='num'>Change</th><th class='num'>Tax bills, 2023</th>
<th class='num'>Tax bills, 2024</th><th class='num'>Change</th></tr></thead><tbody>__EV_ROWS__</tbody></table></div></div>
<div class='col'>
<p class='small'><b>Method.</b> Parcels classed 1-00 in tax year 2023 and in a class 2, 3 or 5 building class in tax
year 2024. Assessed values are the <b>Board of Review</b> (final) values in both years; __EV_AVN__ parcels have one in
both years. Tax bills are the billed amounts for tax years 2023 and 2024 (2024 bills were paid in 2025); __EV_BLN__ parcels
have a bill on file for both years. The bill change also includes any change in tax rates between the two years. Lots
that went to an exempt or incentive class (about 500) are not included, and a class change can occasionally reflect the
Assessor catching up on an existing building. <a href='__EV_CSV__'>Download the parcel-level data (CSV)</a>.</p>
<p class='small'><b>New revenue or relief?</b> For taxing bodies under the state&rsquo;s tax cap (PTELL), new construction
raises the levy they may collect, so it is new revenue. For bodies that set their levy regardless of the tax base, the
new value instead lowers everyone else&rsquo;s rate a little. Cook County has both kinds.</p>

<h2 id='splitrate'><span class='n'>6</span>Why this isn&rsquo;t a split-rate land value tax</h2>
<p>A <b>split-rate land value tax</b>, used by Harrisburg, Allentown and other Pennsylvania cities, taxes land at a
higher rate than buildings. Cook County&rsquo;s <b>classification</b> system is different: it assesses property at
different levels depending on its use, and every parcel in a tax code pays the same rate.</p>
<figure><a href='__IMG_SPLIT__'><img src='__IMG_SPLIT__' alt='Illustrative example: under one tax rate, a house pays $5,000 and a vacant lot pays $1,000; under a split-rate land value tax with 1% on buildings and 4% on land, the house pays $4,000 and the lot pays $2,000, for the same $6,000 total.'></a>
<figcaption>Illustrative example with round numbers.</figcaption></figure>
<p>The Illinois Constitution (Art. IX, §4) lets Cook County classify property by use, as long as the highest assessment
level is no more than 2.5 times the lowest. It does not provide for taxing land and buildings differently, so a
split-rate land value tax would need action in Springfield. Raising vacant land from 10% to 25% fits within the existing
limit and needs only a vote of the Cook County Board of Commissioners.</p>

<h2 id='sources'><span class='n'>7</span>Sources</h2>
<ol class='sources'>
<li>Cook County Assessor, parcel universe (<a href='https://datacatalog.cookcountyil.gov/d/nj4t-kc8j'>nj4t-kc8j</a>) and assessed values (<a href='https://datacatalog.cookcountyil.gov/d/uzyt-m557'>uzyt-m557</a>), Cook County Open Data.</li>
<li>Cook County Assessor, <a href='__CLASSDEFS__'>Definitions for the Classifications of Real Property</a> (rev. 12/16/24).</li>
<li>Cook County Clerk, <a href='__CLERK__'>2024 Tax Rate Report</a>, and tax year 2024 tax code agency rate file.</li>
<li>Cook County Treasurer tax bills, via Chicago Cityscape.</li>
<li>City of Chicago building permits and violations, via Chicago Cityscape.</li>
</ol>
<footer>Built with <a href='__CLE__'>LVTShift</a>, a product of the Center for Land Economics
(<a href='__CLE__'>landeconomics.org/lvtshift</a>). Analysis by Steven Vance.
Companion to <a href='__ARTICLE_URL__'>&ldquo;__ARTICLE_TITLE__&rdquo;</a>.</footer>
</div>

<script>
const DATA = __DATA__;
const sel=document.getElementById('area');
DATA.areas.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a+' ('+DATA.byArea[a].n.toLocaleString()+')';sel.appendChild(o);});
function money(x){const s=x<0?'-':'';return s+'$'+Math.abs(x).toLocaleString();}
function moneyS(x){return (x>0?'+':'')+money(x);}
function pct(x){return x===null?'—':(x>=0?'+':'')+x.toFixed(1)+'%';}
let tgt='25', mode='rn';
function render(){
  const a=DATA.byArea[sel.value];
  const rn=mode==='rn';
  const med=a[mode+tgt+'_med'], net=a[mode+tgt+'_net'];
  const vac=a.cats.find(c=>c.cat==='Vacant land (reassessed)');
  const netSub=rn?'≈$0 overall (revenue-neutral)':'extra revenue raised (a tax increase)';
  document.getElementById('cards').innerHTML=
    "<div class='sc'><h4>Shifted to vacant land</h4><div class='big up'>"+(vac?moneyS(vac[mode+tgt+'_net']):'—')+"</div><div class='sub'>vacant at "+tgt+"%, "+(rn?'rates recalculated':'rates unchanged')+"</div></div>"+
    "<div class='sc'><h4>Aggregate net change</h4><div class='big'>"+moneyS(net)+"</div><div class='sub'>"+netSub+"</div></div>"+
    "<div class='sc'><h4>Modeled parcels</h4><div class='big'>"+a.n.toLocaleString()+"</div><div class='sub'>non-exempt, "+sel.value+"</div></div>";
  const kp=mode+tgt+'_pct', km=mode+tgt+'_medd', kn=mode+tgt+'_net';
  const rows=a.cats.slice().sort((x,y)=>((y[kp]??-999)-(x[kp]??-999)));
  const scale=Math.max(1,...rows.map(r=>Math.abs(r[kp]??0)));
  document.getElementById('rows').innerHTML=rows.map(r=>{
    const v=r[kp], w=v===null?0:Math.abs(v)/scale*50;
    const bar=v===null?'':("<div class='bar "+(v>=0?'pos':'neg')+"' style='"+(v>=0?'left:50%;width:'+w+'%':'right:50%;width:'+w+'%')+"'></div>");
    return "<tr><td class='cat'>"+r.cat+"</td><td class='barcell'><div class='barwrap'><div class='axis'></div>"+bar+"</div></td>"+
      "<td class='num "+(v>=0?'up':'down')+"'>"+pct(v)+"</td><td class='num "+(r[km]>=0?'up':'down')+"'>"+moneyS(r[km])+"</td><td class='num'>"+moneyS(r[kn])+"</td><td class='num muted'>"+r.n.toLocaleString()+"</td></tr>";
  }).join('');
}
sel.addEventListener('change',render);
document.querySelectorAll('.toggle button').forEach(b=>b.addEventListener('click',()=>{
  b.parentElement.querySelectorAll('button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  if(b.dataset.t)tgt=b.dataset.t; if(b.dataset.m)mode=b.dataset.m;
  render();}));
render();
</script></body></html>"""

for k in sorted(FILL, key=len, reverse=True):
    html = html.replace(k, FILL[k])
if not ARTICLE_URL:
    html = re.sub(r"<a href=''>(&ldquo;.*?&rdquo;)</a>", r'\1', html)
html = html.replace('__DATA__', json.dumps(DATA))
assert '__' not in html.split('<script>')[0].replace('__ARTICLE', ''), 'unfilled placeholder'
Path('cook_vacant_article.html').write_text(html)
print('Wrote cook_vacant_article.html (%d KB)' % (len(html) // 1024))
