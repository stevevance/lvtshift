"""Standalone page: 'What if vacant land in Cook County was taxed more like commercial property?'

Renders data/parcels_vacant_reassessment.parquet (built by _build_vacant_reassessment.py) as a
single self-contained HTML page: a township dropdown, two toggles, summary cards, and a category
table with diverging bars. FOUR scenarios — vacant land reassessed to 20% (partway) or 25% (the
commercial maximum), each either revenue-neutral (rates re-struck) or not (rates unchanged, the
county collects the extra). The page states emphatically that this is NOT a land value tax.
Published as vacant-land.html.
"""
import json
from pathlib import Path
import pandas as pd

BG, INK, BLUE, MUTED, GRID = '#F4F3EF', '#26235C', '#5C6FE3', '#8C8B87', '#DEDDD7'
ARTICLE = 'https://progressandpoverty.substack.com/p/you-can-now-vibe-code-land-value'
CLE = 'https://landeconomics.org/lvtshift'
CLERK = 'https://www.cookcountyclerkil.gov/property-taxes/tax-extension-and-rates'

SCEN = ['rn20', 'rz20', 'rn25', 'rz25']

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
print(f'{len(areas)-1} townships + All Cook County')

# County-wide "extra revenue" figures for the lede (not-revenue-neutral mode)
allck = by_area['All Cook County']
RZ20M = f"{round(allck['rz20_net']/1e6):,}"
RZ25M = f"{round(allck['rz25_net']/1e6):,}"

# Evidence section: TY2023 class 1-00 lots that had a building by TY2024 (see
# analysis/research/cook_vacant_redevelopment_2023_2024.md). AV is the Board of Review value in
# both years and only parcels with it in both years are summed; bills likewise need both years.
EVIDENCE_CSV = 'vacant-land-redeveloped-2023-2024.csv'
rd = pd.read_csv('data/vacant_redeveloped_2023_2024.csv', dtype={'pin': str})
rd.to_csv(EVIDENCE_CSV, index=False)
MAJOR = {'2': 'Residential (class 2)', '3': 'Apartments, 7+ units (class 3)', '5': 'Commercial / industrial (class 5)'}


def evidence_row(label, d):
    av = d.dropna(subset=['av_2023_board', 'av_2024_board'])
    bl = d.dropna(subset=['tax_bill_2023', 'tax_bill_2024'])
    av23, av24 = av['av_2023_board'].sum(), av['av_2024_board'].sum()
    b23, b24 = bl['tax_bill_2023'].sum(), bl['tax_bill_2024'].sum()
    return (f"<tr><td class='cat'>{label}</td><td class='num muted'>{len(d):,}</td>"
            f"<td class='num'>${av23/1e6:,.1f}M</td><td class='num'>${av24/1e6:,.1f}M</td>"
            f"<td class='num up'>+{(av24/av23-1)*100:,.0f}%</td>"
            f"<td class='num'>${b23/1e6:,.1f}M</td><td class='num'>${b24/1e6:,.1f}M</td>"
            f"<td class='num up'>+${(b24-b23)/1e6:,.1f}M</td></tr>")


rd['major'] = rd['class_2024'].str[0]
EV_ROWS = ''.join(evidence_row(MAJOR[m], d) for m, d in rd.groupby('major'))
EV_ROWS += evidence_row('<b>All redeveloped lots</b>', rd).replace("<td ", "<td style='border-top:2px solid #26235C' ")
ev_av = rd.dropna(subset=['av_2023_board', 'av_2024_board'])
ev_bl = rd.dropna(subset=['tax_bill_2023', 'tax_bill_2024'])
EV = {
    '__EV_N__': f"{len(rd):,}",
    '__EV_AVN__': f"{len(ev_av):,}",
    '__EV_BLN__': f"{len(ev_bl):,}",
    '__EV_AV23__': f"{ev_av['av_2023_board'].sum()/1e6:,.1f}",
    '__EV_AV24__': f"{ev_av['av_2024_board'].sum()/1e6:,.1f}",
    '__EV_AVPCT__': f"{(ev_av['av_2024_board'].sum()/ev_av['av_2023_board'].sum()-1)*100:,.0f}",
    '__EV_B23__': f"{ev_bl['tax_bill_2023'].sum()/1e6:,.1f}",
    '__EV_B24__': f"{ev_bl['tax_bill_2024'].sum()/1e6:,.1f}",
    '__EV_BDIFF__': f"{(ev_bl['tax_bill_2024'].sum()-ev_bl['tax_bill_2023'].sum())/1e6:,.0f}",
    '__EV_ROWS__': EV_ROWS,
    '__EV_CSV__': EVIDENCE_CSV,
}

html = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Taxing Cook County vacant land more like commercial property</title><style>
 body{background:__BG__;color:__INK__;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;margin:0;padding:0 0 80px}
 .wrap{max-width:1000px;margin:0 auto;padding:0 26px}
 header{padding:40px 0 4px} h1{font-size:26px;margin:0 0 6px;max-width:880px;line-height:1.25}
 .lede{color:#55546f;font-size:13.5px;line-height:1.55}
 ul.lede{margin:6px 0;padding-left:20px} ul.lede li{margin:5px 0}
 .notlvt{background:#FBEED9;border:1px solid #E3C77A;border-radius:8px;padding:12px 18px;margin:18px 0 0;
   font-size:13.5px;color:#6b5a2a;line-height:1.5}
 .controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:22px 0 8px;
   position:sticky;top:0;background:__BG__;padding:12px 0;border-bottom:1px solid __GRID__;z-index:5}
 select{font-size:15px;padding:7px 10px;border:1px solid __GRID__;border-radius:6px;background:#fff;color:__INK__}
 label{font-size:12px;color:__MUTED__;letter-spacing:.3px;margin-right:6px}
 .toggle button{font-size:13px;padding:7px 12px;border:1px solid __GRID__;background:#fff;color:__INK__;cursor:pointer}
 .toggle button:first-child{border-radius:6px 0 0 6px} .toggle button:last-child{border-radius:0 6px 6px 0;border-left:0}
 .toggle button.active{background:__INK__;color:#fff}
 .cards{display:flex;gap:14px;margin:18px 0} .sc{flex:1;background:#fff;border:1px solid __GRID__;border-radius:8px;padding:14px}
 .sc h4{margin:0 0 6px;font-size:12px;color:__MUTED__} .sc .big{font-size:26px;font-weight:bold} .sc .sub{font-size:11.5px;color:__MUTED__;margin-top:3px}
 table{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
 th,td{padding:7px 9px;border-bottom:1px solid __GRID__} th{color:__MUTED__;font-size:11.5px;text-align:left}
 td.cat{font-weight:bold;width:230px} td.barcell{width:46%}
 .barwrap{position:relative;height:18px} .axis{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:__INK__}
 .bar{position:absolute;top:2px;height:14px;border-radius:2px} .pos{background:__BLUE__} .neg{background:__INK__;opacity:.82}
 .num{text-align:right;font-variant-numeric:tabular-nums} .up{color:__BLUE__;font-weight:bold} .down{color:__INK__;font-weight:bold}
 .muted{color:__MUTED__} footer{color:__MUTED__;font-size:11.5px;border-top:1px solid __GRID__;margin-top:30px;padding-top:14px}
</style></head><body><div class='wrap'>
<p style="margin:22px 0 0"><a href="index.html" style="color:#5C6FE3;font-size:13px;text-decoration:none">&larr; All LVT reports</a></p>
<header><h1>What if vacant land in Cook County was taxed more like commercial property?</h1>
<p class='lede'>Cook County assesses property by use. Homes and <b>vacant land</b> are assessed at <b>10%</b> of
their market value; commercial and industrial property at <b>25%</b>. Because vacant land is assessed at the
low residential rate, holding an empty lot is cheap — even on a busy commercial street. This page asks a
narrow question: what if vacant land were assessed <b>higher</b> — to nudge owners to build rather than sit on
it? Use the toggles to choose <b>how high</b> and <b>how the money is handled</b>:</p>
<ul class='lede'>
<li><b>Target 20% or 25%.</b> <b>20%</b> is partway to the commercial rate; <b>25%</b> is the commercial /
industrial maximum — the legal ceiling under Illinois' classification limit.</li>
<li><b>Revenue-neutral</b>: each of Cook County's ~900 taxing bodies keeps its exact levy and re-strikes its
rate over the slightly larger tax base, so vacant land's bill goes up and every other property's goes down by
a small amount (the county collects the same total).</li>
<li><b>Not revenue-neutral</b>: today's rates are left unchanged, so <b>only vacant land pays more</b> — every
other property is untouched — and the county simply collects the extra (about <b>$__RZ20M__&nbsp;million</b>
more county-wide at 20%, or <b>$__RZ25M__&nbsp;million</b> at 25%).</li>
</ul>
<p class='lede'>Results are grouped by assessment township; positive means the parcel pays more.</p></header>
<div class='notlvt'><b>This is not a land value tax.</b> Nothing here shifts tax off buildings and onto land,
and there is no split rate or building abatement. The split-rate and abatement models elsewhere on this site
are a different, larger reform. This page changes <b>one thing only</b> — the assessment ratio on vacant
land — and leaves the rest of the property tax exactly as it is today.</div>
<div class='controls'>
  <div><label>Township</label><select id='area'></select></div>
  <div class='toggle'><label>Assess vacant land at</label>
    <button data-t='20' class='active'>20%</button><button data-t='25'>25% (max)</button></div>
  <div class='toggle'><label>Mode</label>
    <button data-m='rn' class='active'>Revenue-neutral</button><button data-m='rz'>Not revenue-neutral</button></div>
</div>
<div class='cards' id='cards'></div>
<p class='lede' style='margin:16px 0 0'>Categories below use the assessor's standard property groupings, except
that the reassessed vacant lots are pulled into their own <b>&ldquo;Vacant land (reassessed)&rdquo;</b> row so it
matches the parcels actually being reassessed. Every other row is <b>not</b> reassessed: under
&ldquo;revenue-neutral&rdquo; it sees a small decrease; under &ldquo;not revenue-neutral&rdquo; it is unchanged.</p>
<table><thead><tr><th>Category</th><th>Median % change</th><th class='num'>Median %</th><th class='num'>Median $</th><th class='num'>Net change ($)</th><th class='num'>Parcels</th></tr></thead><tbody id='rows'></tbody></table>
<div class='notlvt'><b>Exactly which parcels are reassessed.</b> Only the <b>x-00 vacant-land classes currently
assessed below the 25% commercial rate</b> — overwhelmingly class <b>1-00 &ldquo;Vacant Land&rdquo;</b> (about
59,000 parcels), plus a few dozen 2-00/3-00/8-00 vacant codes. Those parcels — and <b>only</b> those — make up
the <b>&ldquo;Vacant land (reassessed)&rdquo;</b> row in the table above, so the bar you see is exactly the set
being reassessed. Two related classes are vacant land but are <b>left untouched</b>, and are broken out as their
own rows so nothing is hidden: <b>class 2-41</b> (&ldquo;vacant land under common ownership with an adjacent
residence&rdquo; — homeowner side-lots), and the handful of <b>5-00</b> parcels already assessed at the 25%
commercial rate. The reform only ever <b>raises</b> toward the target and never lowers.</div>
<div class='notlvt'><b>Why class 1-90 is excluded.</b> The assessor also has class <b>1-90, &ldquo;Minor
Improvement on Vacant Land&rdquo;</b> (about 2,600 parcels), which it files alongside vacant land. We looked
at a sample across the county and found it is <b>too mixed to reassess as one class</b>: some are genuinely
empty lots that arguably belong in 1-00; some are <b>surface parking lots</b> that belong in the commercial
5-90 class; and some are truly undevelopable — land <b>under high-tension power lines</b> or <b>beneath the
CTA &ldquo;L&rdquo; tracks</b> — that correctly stays 1-90. Rather than double the assessment on all of them,
we <b>exclude 1-90</b> here and flag it as a class ripe for parcel-by-parcel <b>reclassification</b>.</div>
<h2 id='redeveloped' style='font-size:19px;margin:34px 0 6px'>Evidence: what happens when a vacant lot gets built on</h2>
<p class='lede'>Of the 60,361 Cook County parcels classed <b>1-00 &ldquo;Vacant Land&rdquo;</b> in tax year 2023,
<b>__EV_N__</b> had a building by tax year 2024 (they moved to a residential, apartment or commercial class).
Their combined assessed value rose from <b>$__EV_AV23__&nbsp;million to $__EV_AV24__&nbsp;million (+__EV_AVPCT__%)</b>,
and their combined tax bills rose from <b>$__EV_B23__&nbsp;million to $__EV_B24__&nbsp;million</b> &mdash; about
<b>$__EV_BDIFF__&nbsp;million more billed in a single year</b>, compared with when the same parcels were empty lots.</p>
<div style='overflow-x:auto'><table><thead><tr><th>Became</th><th class='num'>Parcels</th><th class='num'>Assessed value, 2023</th>
<th class='num'>Assessed value, 2024</th><th class='num'>Change</th><th class='num'>Tax bills, 2023</th>
<th class='num'>Tax bills, 2024</th><th class='num'>Change</th></tr></thead><tbody>__EV_ROWS__</tbody></table></div>
<p class='lede' style='font-size:12px'><b>Method.</b> Parcels are those classed 1-00 in tax year 2023 and in a
class 2, 3 or 5 building class in tax year 2024. Assessed values are the <b>Board of Review</b> (final) values in
both years; __EV_AVN__ parcels have one in both years. Tax bills are the billed amounts for tax years 2023 and 2024
(the 2024 bills were paid in 2025); __EV_BLN__ parcels have a bill on file for both years. The bill change also includes any change in tax rates between the two years, which is
small next to a roughly tenfold jump in assessed value. Lots that went to an exempt or incentive class are not
included. Sources: Cook County Assessor; Cook County Treasurer tax bills via Chicago Cityscape.
<a href='__EV_CSV__' style='color:#5C6FE3'>Download the parcel-level data (CSV)</a>.</p>
<footer>Built with <a href='__CLE__'>LVTShift</a>, a product of the Center for Land Economics
(<a href='__CLE__'>landeconomics.org/lvtshift</a>). Assessment ratios and class definitions: Cook County
Assessor. Levies/rates: Cook County Clerk <a href='__CLERK__'>Tax Extension &amp; Rates</a> (TY2024 Tax Code
Agency Rate file); each of ~900 real taxing bodies (TIF districts excluded) re-strikes its own rate over the
reassessed base, revenue-neutral per district. Analysis by Steven Vance. <b>Limitation:</b> current tax
uses gross equalized value (homeowner/senior exemptions and TIF not removed), so dollar levels run ~8% above
the official ~$19.2B extension; the revenue-neutral distribution is unaffected. Background:
<a href='__ARTICLE__'>progressandpoverty.substack.com</a>.</footer>
</div>
<script>
const DATA = __DATA__;
const sel=document.getElementById('area');
DATA.areas.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a+' ('+DATA.byArea[a].n.toLocaleString()+')';sel.appendChild(o);});
function money(x){const s=x<0?'-':'';return s+'$'+Math.abs(x).toLocaleString();}
function moneyS(x){return (x>0?'+':'')+money(x);}
function pct(x){return x===null?'—':(x>=0?'+':'')+x.toFixed(1)+'%';}
let tgt='20', mode='rn';
function render(){
  const a=DATA.byArea[sel.value];
  const rn=mode==='rn';
  const med=a[mode+tgt+'_med'], net=a[mode+tgt+'_net'];
  const netSub=rn?'≈$0 county-wide (revenue-neutral)':'extra revenue raised (a tax increase)';
  const medSub='vacant '+tgt+'%, '+(rn?'rates re-struck':'rates unchanged')+' (not an LVT)';
  document.getElementById('cards').innerHTML=
    "<div class='sc'><h4>Overall median change</h4><div class='big "+(med>=0?'up':'down')+"'>"+pct(med)+"</div><div class='sub'>"+medSub+"</div></div>"+
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
  const grp=b.parentElement;
  grp.querySelectorAll('button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  if(b.dataset.t)tgt=b.dataset.t; if(b.dataset.m)mode=b.dataset.m;
  render();}));
render();
</script></body></html>"""
for k, v in {'__BG__': BG, '__INK__': INK, '__BLUE__': BLUE, '__MUTED__': MUTED, '__GRID__': GRID,
             '__ARTICLE__': ARTICLE, '__CLE__': CLE, '__CLERK__': CLERK,
             '__RZ20M__': RZ20M, '__RZ25M__': RZ25M, **EV}.items():
    html = html.replace(k, v)
html = html.replace('__DATA__', json.dumps(DATA))
Path('cook_vacant_reassessment.html').write_text(html)
print('Wrote cook_vacant_reassessment.html (%d KB)' % (len(html) // 1024))
