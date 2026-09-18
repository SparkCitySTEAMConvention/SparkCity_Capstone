"""Self-contained snapshot dashboard, also usable with a polling database API."""
import json


def render_dashboard(bundle, live=False):
    payload = json.dumps(bundle, allow_nan=False).replace("<", "\\u003c")
    return HTML.replace("__PAYLOAD__", payload).replace("__LIVE__", "true" if live else "false")


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SparkCity · City operations</title>
<style>
body{margin:0;background:#edf2f5;color:#173149;font:16px system-ui}main{max-width:1200px;margin:auto;padding:28px}
h1{margin-bottom:4px}section{background:white;padding:20px;margin:18px 0;border-radius:12px}
label{display:inline-block;margin:8px}select,input,button{font:inherit;padding:8px;max-width:100%}
.notice{border-left:5px solid #c58124;padding:12px;background:#fff6e4}.muted{color:#526677;font-size:14px}
.scroll{overflow:auto;max-height:380px}table{border-collapse:collapse;width:100%;font-size:14px}
td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:white}
svg{width:100%;height:auto}#health{font-weight:600}button{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><main>
<h1>SparkCity · City operations</h1><p>Day 5 | Integration, monitoring and fiscal evidence</p>
<p class="notice">Synthetic historical observations. Means are not city totals. Units and source timezone remain unconfirmed.
This dashboard does not identify or recommend a convention date.</p>
<p id="health" role="status"></p><p id="lineage" class="muted"></p>
<section><h2>Explore all six datasets</h2>
<label>Dataset <select id="dataset"></select></label><label>Measurement <select id="metric"></select></label>
<label>From <input type="date" id="start"></label><label>Through <input type="date" id="end"></label>
<button id="reset">Full date range</button><button id="download">Download filtered data</button>
<p id="summary"></p><svg id="chart" viewBox="0 0 1000 300" role="img" aria-label="Daily observation means"></svg>
<p class="muted">Line segments connect consecutive calendar days only. Different sensors may contribute on different days.</p>
<details><summary>Daily drill-down: values and coverage</summary><div class="scroll" id="daily"></div></details></section>
<section><h2>Alert review</h2><p>Day 4 held-out test alerts only, filtered by dataset and dates. No labels establish detection accuracy.</p>
<p id="alertSummary"></p><div class="scroll" id="alerts"></div>
<p id="stream" class="muted"></p><button id="notify">Enable browser review notifications</button>
<p class="muted">Optional browser notices require permission and an open page; they are not email/SMS delivery.</p></section>
<section><h2>Next: fiscal date investigation</h2><p>Compare revenue, expense and their paired difference per observation.
Check recurring calendar patterns, changing sensor coverage and candidate multi-day windows before comparing dates.
A high-revenue day is not proof that the convention occurred then, nor proof it is the best future date.</p>
<p>Attendance: approximately 15,000. Theme: Science, Technology, Engineering, Arts and Mathematics.
The 27 convention scenarios remain assumption-based alternatives, not inferred calendar dates.</p></section>
<details><summary>Snapshot provenance</summary><pre id="provenance"></pre></details>
</main><script>
let data=__PAYLOAD__; const LIVE=__LIVE__;
const el=id=>document.getElementById(id); let shown=[], lastRun=null, lastPending=null;
function table(target,rows,columns){const t=document.createElement('table'),head=document.createElement('tr');
 for(const c of columns){const th=document.createElement('th');th.textContent=c;head.appendChild(th)}t.appendChild(head);
 for(const r of rows){const tr=document.createElement('tr');for(const c of columns){const td=document.createElement('td');
 td.textContent=typeof r[c]==='number'&&!Number.isInteger(r[c])?r[c].toFixed(4):r[c];tr.appendChild(td)}t.appendChild(tr)}
 el(target).replaceChildren(t)}
function options(id,values){const previous=el(id).value;el(id).replaceChildren();for(const v of values){
 const o=document.createElement('option');o.value=v;o.textContent=v;el(id).appendChild(o)}if(values.includes(previous))el(id).value=previous}
function metrics(){options('metric',[...new Set(data.daily.filter(r=>r.dataset===el('dataset').value).map(r=>r.metric))]);render()}
function render(){const kind=el('dataset').value,metric=el('metric').value,start=el('start').value,end=el('end').value;
 shown=data.daily.filter(r=>r.dataset===kind&&r.metric===metric&&(!start||r.day>=start)&&(!end||r.day<=end)).sort((a,b)=>a.day.localeCompare(b.day));
 const n=shown.reduce((s,r)=>s+r.observations,0),mean=n?shown.reduce((s,r)=>s+r.mean*r.observations,0)/n:null;
 el('summary').textContent=shown.length?`${shown.length} observed days · ${n.toLocaleString()} observations · weighted mean ${mean.toFixed(3)} (source units)`:'No observations in this range.';
 table('daily',shown,['day','observations','sensors','mean','minimum','maximum']);
 const svg=el('chart');svg.replaceChildren();const ns='http://www.w3.org/2000/svg';
 function node(tag,attrs,text){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.appendChild(n);return n}
 if(shown.length){const times=shown.map(r=>Date.parse(r.day)),values=shown.map(r=>r.mean),min=Math.min(...values),max=Math.max(...values);
 const x=i=>80+850*(times[i]-times[0])/(times.at(-1)-times[0]||1),y=i=>245-210*(values[i]-min)/(max-min||1);
 node('text',{x:5,y:30},max.toFixed(2));node('text',{x:5,y:245},min.toFixed(2));
 node('text',{x:80,y:280},shown[0].day);node('text',{x:820,y:280},shown.at(-1).day);
 for(let i=0;i<shown.length;i++){if(i&&times[i]-times[i-1]===86400000)node('line',{x1:x(i-1),y1:y(i-1),x2:x(i),y2:y(i),stroke:'#087e8b','stroke-width':2});
 const dot=node('circle',{cx:x(i),cy:y(i),r:3,fill:'#087e8b'}),title=document.createElementNS(ns,'title');title.textContent=`${shown[i].day}: ${values[i]}`;dot.appendChild(title)}}
 const alerts=data.alerts.filter(r=>r.dataset===kind&&(!start||r.observed_at.slice(0,10)>=start)&&(!end||r.observed_at.slice(0,10)<=end));
 el('alertSummary').textContent=`${alerts.length} review alerts; not confirmed incidents.`;
 table('alerts',alerts,['observed_at','sensor_id','reasons','severity','model_id']);
 el('stream').textContent=LIVE?`Historical replay: ${data.replayed_alerts||0} unique streamed alerts; ${data.pending_notifications||0} pending outbox records. Snapshot charts change only after batch publication.`:'Offline snapshot: no live stream, database polling or outbound notifications.';
 el('lineage').textContent=`Day 5 ${data.run_id} ← Day 4 ${data.provenance.day4_run}. Generated ${data.provenance.created_at}. Data coverage is historical, not current city conditions.`;
 el('provenance').textContent=JSON.stringify(data.provenance,null,2)}
function refresh(){options('dataset',[...new Set(data.daily.map(r=>r.dataset))]);metrics()}
el('dataset').onchange=metrics;for(const id of ['metric','start','end'])el(id).onchange=render;
el('reset').onclick=()=>{el('start').value='';el('end').value='';render()};
el('download').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(shown,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='sparkcity-filtered-daily.json';a.click();URL.revokeObjectURL(url)};
el('notify').onclick=async()=>{if(!LIVE){alert('Browser notifications require the local dashboard server.');return}
 if('Notification' in window)await Notification.requestPermission();else alert('Browser notifications unavailable.')};
async function poll(){try{const response=await fetch('/api/snapshot',{cache:'no-store',signal:AbortSignal.timeout(20000)});
 if(!response.ok)throw new Error('unavailable');const next=await response.json();
 if(lastRun!==null&&(lastRun!==next.run_id||(lastPending!==null&&next.pending_notifications>lastPending))&&'Notification' in window&&Notification.permission==='granted')new Notification('SparkCity review update',{body:'A new snapshot or replay alert batch is available for review.'});
 lastRun=next.run_id;lastPending=next.pending_notifications;data=next;refresh();
 el('health').textContent='Database connected · checked '+new Date().toLocaleTimeString()+' · refresh every 15s';
 }catch(e){el('health').textContent='STALE: database refresh failed. Showing last successful snapshot; do not assume it is current.'}
 finally{setTimeout(poll,15000)}}
refresh();el('health').textContent=LIVE?'Connecting to database…':'Offline, completed batch snapshot';if(LIVE)poll();
</script></body></html>'''
