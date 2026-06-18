"""Interactive Cook County full-composite LVT report, by assessment township.

Reads data/parcels_modeled_c2.parquet (built by _build_data.py) and renders a single
self-contained HTML: dropdown of the 38 townships + "All Cook County", a split-rate /
abatement toggle, summary cards, and a category table with diverging CSS bars. Scratch.
"""
import json
from pathlib import Path
import pandas as pd

BG, INK, BLUE, MUTED, GRID = '#F4F3EF', '#26235C', '#5C6FE3', '#8C8B87', '#DEDDD7'
ARTICLE = 'https://progressandpoverty.substack.com/p/you-can-now-vibe-code-land-value'
CLE = 'https://landeconomics.org/lvtshift'
CLERK = 'https://www.cookcountyclerkil.gov/property-taxes/tax-extension-and-rates'

gs = pd.read_parquet('data/parcels_modeled_c2.parquet')
gs['township'] = gs['township'].fillna('(unknown)')


def aggregate(df):
    cats = []
    for cat, d in df.groupby('PROPERTY_CATEGORY'):
        cats.append({
            'cat': cat, 'n': int(len(d)),
            'split': None if d['tax_change_pct'].isna().all() else round(float(d['tax_change_pct'].median()), 1),
            'abate': None if d['abate_pct'].isna().all() else round(float(d['abate_pct'].median()), 1),
            'net_split': int(d['tax_change'].sum()),
            'net_abate': int(d['abate_change'].sum()),
        })
    cats.sort(key=lambda r: (r['split'] if r['split'] is not None else -999), reverse=True)
    return {'n': int(len(df)),
            'med_split': round(float(df['tax_change_pct'].median()), 1),
            'med_abate': round(float(df['abate_pct'].median()), 1),
            'net_split': int(df['tax_change'].sum()),
            'net_abate': int(df['abate_change'].sum()),
            'cats': cats}

by_area = {'All Cook County': aggregate(gs)}
for area, d in gs.groupby('township'):
    by_area[str(area).title()] = aggregate(d)
areas = ['All Cook County'] + sorted(a for a in by_area if a != 'All Cook County')
DATA = {'areas': areas, 'byArea': by_area}
print(f'{len(areas)-1} townships + All Cook County')

html = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Cook County LVT by township</title><style>
 body{background:__BG__;color:__INK__;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;margin:0;padding:0 0 80px}
 .wrap{max-width:1000px;margin:0 auto;padding:0 26px}
 header{padding:40px 0 4px} h1{font-size:26px;margin:0 0 6px}
 .lede{color:#55546f;font-size:13.5px;max-width:820px;line-height:1.55}
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
<p style="font-size:12.5px;color:#8C8B87;margin:6px 0 4px">Cook County variants: <a href="cook-c1.html" style="color:#5C6FE3;text-decoration:none">C1 · single county-wide rate</a> &nbsp;·&nbsp; <b>C2-MV · per-district (market value)</b> &nbsp;·&nbsp; <a href="cook-c2-cp.html" style="color:#5C6FE3;text-decoration:none">C2-CP · per-district (classification-preserved)</a></p>
<header><h1>Cook County: per-taxing-district land value tax — market-value base (C2-MV)</h1>
<p class='lede'>Each of Cook County's ~900 taxing bodies — school, library, park, municipal, and county
districts — shifts its own levy from total value onto land, within its own boundary and keeping its own
revenue. A parcel's new bill is the sum, across the districts that cover it, of its land value times each
district's land rate.</p>
<p class='lede'>Because each district funds itself, this isolates the pure land shift. (The single
county-wide rate, C1, instead pools the whole county's tax base together.) Results are grouped by
assessment township just for navigation — the township is not the tax unit.</p>
<p class='lede'>Two reforms are shown: a 2.5:1 split-rate (land taxed 2.5× buildings, the Illinois
classification cap) and a 100% building abatement (a pure land tax). This version uses market values, so
it also unwinds Cook County's 10%/25% classification (the C2-CP variant keeps it). Positive means the
parcel pays more.</p></header>
<div style="background:#fff;border:1px solid __GRID__;border-left:4px solid __BLUE__;border-radius:8px;padding:14px 18px;margin:16px 0;font-size:13.5px;color:#45446a;line-height:1.55">
<b>How to read this.</b> A land shift taxes land at a higher rate than buildings, set so total revenue is unchanged. Because the total is unchanged, it's a <b>redistribution: whoever is land-heavy pays more, whoever is building-heavy pays less.</b>
<ul style="margin:8px 0 0;padding-left:20px">
<li>A <b>vacant lot</b> is 100% land &rarr; taxed entirely at the high land rate &rarr; <b>pays more</b>.</li>
<li>A <b>high-rise condo</b> is ~90% building &rarr; most of its value is taxed at the low building rate &rarr; <b>pays less</b>.</li>
<li>A typical <b>single-family home</b> (~25% land) &rarr; modestly less.</li>
</ul></div>
<div class='controls'>
  <div><label>Township</label><select id='area'></select></div>
  <div class='toggle'><label>Reform</label>
    <button data-r='split' class='active'>2.5:1 split-rate</button><button data-r='abate'>100% abatement</button></div>
</div>
<div class='cards' id='cards'></div>
<table><thead><tr><th>Category</th><th>Median % change</th><th class='num'>Median %</th><th class='num'>Net change ($)</th><th class='num'>Parcels</th></tr></thead><tbody id='rows'></tbody></table>
<footer>Built with <a href='__CLE__'>LVTShift</a>, a product of the Center for Land Economics
(<a href='__CLE__'>landeconomics.org/lvtshift</a>). Composite rates: Cook County Clerk
<a href='__CLERK__'>Tax Extension &amp; Rates</a> (TY2024 Tax Code Agency Rate file). Analysis by Chicago
Cityscape. Each of ~900 real taxing bodies (TIF districts excluded) is shifted to land within its own
footprint, revenue-neutral per district. <b>Limitation:</b> current tax uses gross equalized value
(homeowner/senior exemptions and TIF not removed), so dollar levels run ~8% above the official ~$19.2B
extension; the revenue-neutral distribution is unaffected. Background:
<a href='__ARTICLE__'>progressandpoverty.substack.com</a>.</footer>
</div>
<script>
const DATA = __DATA__;
let reform='split'; const sel=document.getElementById('area');
DATA.areas.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a+' ('+DATA.byArea[a].n.toLocaleString()+')';sel.appendChild(o);});
function money(x){const s=x<0?'-':'';return s+'$'+Math.abs(x).toLocaleString();}
function pct(x){return x===null?'—':(x>=0?'+':'')+x.toFixed(1)+'%';}
function render(){
  const a=DATA.byArea[sel.value], pk=reform==='split'?'split':'abate', nk='net_'+pk;
  const medAll=reform==='split'?a.med_split:a.med_abate, netAll=reform==='split'?a.net_split:a.net_abate;
  document.getElementById('cards').innerHTML=
    "<div class='sc'><h4>Overall median change</h4><div class='big "+(medAll>=0?'up':'down')+"'>"+pct(medAll)+"</div><div class='sub'>"+(reform==='split'?'2.5:1 split-rate':'100% abatement')+"</div></div>"+
    "<div class='sc'><h4>Aggregate net change</h4><div class='big'>"+money(netAll)+"</div><div class='sub'>sum across "+a.n.toLocaleString()+" parcels</div></div>"+
    "<div class='sc'><h4>Modeled parcels</h4><div class='big'>"+a.n.toLocaleString()+"</div><div class='sub'>non-exempt, "+sel.value+"</div></div>";
  const rows=a.cats.slice().sort((x,y)=>((y[pk]??-999)-(x[pk]??-999)));
  const scale=Math.max(1,...rows.map(r=>Math.abs(r[pk]??0)));
  document.getElementById('rows').innerHTML=rows.map(r=>{
    const v=r[pk], w=v===null?0:Math.abs(v)/scale*50;
    const bar=v===null?'':("<div class='bar "+(v>=0?'pos':'neg')+"' style='"+(v>=0?'left:50%;width:'+w+'%':'right:50%;width:'+w+'%')+"'></div>");
    return "<tr><td class='cat'>"+r.cat+"</td><td class='barcell'><div class='barwrap'><div class='axis'></div>"+bar+"</div></td>"+
      "<td class='num "+(v>=0?'up':'down')+"'>"+pct(v)+"</td><td class='num'>"+money(r[nk])+"</td><td class='num muted'>"+r.n.toLocaleString()+"</td></tr>";
  }).join('');
}
sel.addEventListener('change',render);
document.querySelectorAll('.toggle button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.toggle button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');reform=b.dataset.r;render();}));
render();
</script></body></html>"""
for k, v in {'__BG__':BG,'__INK__':INK,'__BLUE__':BLUE,'__MUTED__':MUTED,'__GRID__':GRID,
             '__ARTICLE__':ARTICLE,'__CLE__':CLE,'__CLERK__':CLERK}.items():
    html = html.replace(k, v)
html = html.replace('__DATA__', json.dumps(DATA))
Path('cook_report_c2_bytownship.html').write_text(html)
print('Wrote cook_report_c2_bytownship.html (%d KB)' % (len(html)//1024))
