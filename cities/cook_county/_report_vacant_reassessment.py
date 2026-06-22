"""Standalone page: 'What if vacant land in Cook County was taxed more like commercial property?'

Renders data/parcels_vacant_reassessment.parquet (built by _build_vacant_reassessment.py) as a
single self-contained HTML page: a township dropdown, summary cards, and a category table with
diverging bars. ONE reform only — vacant land reassessed 10% -> 20% within the existing tax — and
the page states emphatically that this is NOT a land value tax. Published as vacant-land.html.
"""
import json
from pathlib import Path
import pandas as pd

BG, INK, BLUE, MUTED, GRID = '#F4F3EF', '#26235C', '#5C6FE3', '#8C8B87', '#DEDDD7'
ARTICLE = 'https://progressandpoverty.substack.com/p/you-can-now-vibe-code-land-value'
CLE = 'https://landeconomics.org/lvtshift'
CLERK = 'https://www.cookcountyclerkil.gov/property-taxes/tax-extension-and-rates'

gs = pd.read_parquet('data/parcels_vacant_reassessment.parquet')
gs['township'] = gs['township'].fillna('(unknown)')


def aggregate(df):
    cats = []
    for cat, d in df.groupby('PROPERTY_CATEGORY'):
        cats.append({
            'cat': cat, 'n': int(len(d)),
            'pct_rn': None if d['vac_pct'].isna().all() else round(float(d['vac_pct'].median()), 1),
            'medd_rn': int(round(float(d['vac_change'].median()))),
            'net_rn': int(d['vac_change'].sum()),
            'pct_raise': None if d['raise_pct'].isna().all() else round(float(d['raise_pct'].median()), 1),
            'medd_raise': int(round(float(d['raise_change'].median()))),
            'net_raise': int(d['raise_change'].sum()),
        })
    cats.sort(key=lambda r: (r['pct_rn'] if r['pct_rn'] is not None else -999), reverse=True)
    return {'n': int(len(df)),
            'med_rn': round(float(df['vac_pct'].median()), 1),
            'net_rn': int(df['vac_change'].sum()),
            'med_raise': round(float(df['raise_pct'].median()), 1),
            'net_raise': int(df['raise_change'].sum()),
            'cats': cats}

by_area = {'All Cook County': aggregate(gs)}
for area, d in gs.groupby('township'):
    by_area[str(area).title()] = aggregate(d)
areas = ['All Cook County'] + sorted(a for a in by_area if a != 'All Cook County')
DATA = {'areas': areas, 'byArea': by_area}
print(f'{len(areas)-1} townships + All Cook County')

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
narrow question: what if vacant land were assessed at <b>20%</b> instead — partway toward the commercial
rate — to nudge owners to build rather than sit on it?</p>
<p class='lede'>Two versions are shown — use the toggle to switch:</p>
<ul class='lede'>
<li><b>Revenue-neutral</b>: each of Cook County's ~900 taxing bodies keeps its exact levy and re-strikes its
rate over the slightly larger tax base, so vacant land's bill goes up and every other property's goes down
by a small amount (the county collects the same total).</li>
<li><b>Not revenue-neutral</b>: today's rates are left unchanged, so <b>only vacant land pays more</b> — every
other property is untouched — and the county simply collects the extra (about <b>$125&nbsp;million</b> more
county-wide).</li>
</ul>
<p class='lede'>Results are grouped by assessment township; positive means the parcel pays more.</p></header>
<div class='notlvt'><b>This is not a land value tax.</b> Nothing here shifts tax off buildings and onto land,
and there is no split rate or building abatement. The split-rate and abatement models elsewhere on this site
are a different, larger reform. This page changes <b>one thing only</b> — the assessment ratio on vacant
(class&nbsp;&ldquo;-00&rdquo;) land — and leaves the rest of the property tax exactly as it is today.</div>
<div class='controls'>
  <div><label>Township</label><select id='area'></select></div>
  <div class='toggle'><label>Mode</label>
    <button data-r='rn' class='active'>Revenue-neutral</button><button data-r='raise'>Not revenue-neutral</button></div>
</div>
<div class='cards' id='cards'></div>
<table><thead><tr><th>Category</th><th>Median % change</th><th class='num'>Median %</th><th class='num'>Median $</th><th class='num'>Net change ($)</th><th class='num'>Parcels</th></tr></thead><tbody id='rows'></tbody></table>
<footer>Built with <a href='__CLE__'>LVTShift</a>, a product of the Center for Land Economics
(<a href='__CLE__'>landeconomics.org/lvtshift</a>). Assessment ratios and class definitions: Cook County
Assessor. Levies/rates: Cook County Clerk <a href='__CLERK__'>Tax Extension &amp; Rates</a> (TY2024 Tax Code
Agency Rate file); each of ~900 real taxing bodies (TIF districts excluded) re-strikes its own rate over the
reassessed base, revenue-neutral per district. Analysis by Chicago Cityscape. <b>Limitation:</b> current tax
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
let mode='rn';
function render(){
  const a=DATA.byArea[sel.value];
  const rn=mode==='rn';
  const med=rn?a.med_rn:a.med_raise, net=rn?a.net_rn:a.net_raise;
  const netSub=rn?'≈$0 county-wide (revenue-neutral)':'extra revenue raised (a tax increase)';
  const medSub=rn?'vacant 20%, rates re-struck (not an LVT)':'vacant 20%, rates unchanged (not an LVT)';
  document.getElementById('cards').innerHTML=
    "<div class='sc'><h4>Overall median change</h4><div class='big "+(med>=0?'up':'down')+"'>"+pct(med)+"</div><div class='sub'>"+medSub+"</div></div>"+
    "<div class='sc'><h4>Aggregate net change</h4><div class='big'>"+moneyS(net)+"</div><div class='sub'>"+netSub+"</div></div>"+
    "<div class='sc'><h4>Modeled parcels</h4><div class='big'>"+a.n.toLocaleString()+"</div><div class='sub'>non-exempt, "+sel.value+"</div></div>";
  const kp=rn?'pct_rn':'pct_raise', km=rn?'medd_rn':'medd_raise', kn=rn?'net_rn':'net_raise';
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
  document.querySelectorAll('.toggle button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');mode=b.dataset.r;render();}));
render();
</script></body></html>"""
for k, v in {'__BG__':BG,'__INK__':INK,'__BLUE__':BLUE,'__MUTED__':MUTED,'__GRID__':GRID,
             '__ARTICLE__':ARTICLE,'__CLE__':CLE,'__CLERK__':CLERK}.items():
    html = html.replace(k, v)
html = html.replace('__DATA__', json.dumps(DATA))
Path('cook_vacant_reassessment.html').write_text(html)
print('Wrote cook_vacant_reassessment.html (%d KB)' % (len(html)//1024))
