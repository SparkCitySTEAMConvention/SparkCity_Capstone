// Dependency-free DOM smoke test; not a substitute for visual browser review.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor(tag='div') { this.tag=tag; this.children=[]; this._value=''; this.textContent=''; }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children=children; if(this.tag==='select')this._value=''; }
  setAttribute() {}
  get value() { return this._value || (this.tag==='select'&&this.children.length?this.children[0].value:''); }
  set value(v) { this._value=v; }
  click() {}
}
const ids = {};
for(const id of ['dataset','metric','start','end','reset','download','summary','chart','daily','alertSummary','alerts','stream','notify','lineage','provenance','health'])
  ids[id]=new Element(['dataset','metric'].includes(id)?'select':'div');
const context={document:{getElementById:id=>ids[id],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)},
 window:{},console,alert:()=>{},URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},Blob:class{},setTimeout:()=>{}};
const html=fs.readFileSync(process.argv[2],'utf8');
const script=html.split('<script>')[1].split('</script>')[0];
vm.createContext(context); vm.runInContext(script,context);
assert.equal(ids.dataset.children.length,6);
let metrics=0;
for(const option of [...ids.dataset.children]){
 ids.dataset.value=option.value;ids.dataset.onchange();
 for(const metric of [...ids.metric.children]){
  ids.metric.value=metric.value;ids.metric.onchange();metrics++;
  assert.ok(!ids.summary.textContent.startsWith('No observations'));
  assert.ok(ids.chart.children.length>0);
  assert.ok(ids.daily.children[0].children.length>1);
 }
}
assert.equal(metrics,20);
ids.start.value='2099-01-01';ids.start.onchange();
assert.equal(ids.summary.textContent,'No observations in this range.');
assert.equal(ids.chart.children.length,0);
ids.reset.onclick();assert.ok(!ids.summary.textContent.startsWith('No observations'));
ids.download.onclick();
assert.match(ids.health.textContent,/Offline/);
assert.match(ids.stream.textContent,/no live stream/);
console.log('Dashboard smoke passed: six datasets, 20 metrics, empty range, reset, download and offline status.');
