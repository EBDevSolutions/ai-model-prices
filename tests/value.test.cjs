const {test} = require('node:test');
const assert = require('node:assert/strict');
const value = require('../assets/value.js');

test('cost uses disjoint million-token volumes; zero is valid, missing is not free', () => {
  const model = {input:2, cached_input:.2, output:10};
  assert.ok(Math.abs(value.cost(model,{input:.1,cached:.9,output:.02}) - .58) < 1e-12);
  assert.equal(value.cost(model,{input:0,cached:0,output:0}), 0);
  assert.equal(value.cost({...model,price_comparable:false},{input:1,cached:0,output:1}), null);
  assert.equal(value.cost(model,{input:Infinity,cached:0,output:1}), null);
});
test('quality never falls back to overall or an unrelated benchmark', () => {
  assert.equal(value.quality({scores:{gpqa_diamond:90,hle_no_tools:50},benchlm_summary:{overall:70,evidence_status:'supported'}},'coding'), null);
  const record = {benchlm_summary:{evidence_status:'estimated',categories:{coding:80,agentic:60}}};
  assert.equal(value.quality(record,'coding'), null);
  assert.equal(value.quality(record,'agentic',true), 60);
});
test('retired, limited, stale or failed-provider prices cannot rank', () => {
  const now=Date.parse('2026-09-07T12:00:00Z');
  const model={active:true,availability:'active',last_seen_at:'2026-09-07T10:00:00Z'};
  assert.equal(value.eligible(model,{status:'ok'},now),true);
  for(const patch of [{active:false},{availability:'limited'},{last_seen_at:'2026-09-01T00:00:00Z'},{last_seen_at:'2026-09-08T00:00:00Z'}]) assert.equal(value.eligible({...model,...patch},{status:'ok'},now),false);
  assert.equal(value.eligible(model,{status:'error'},now),false);
});
test('Pareto preserves tradeoffs and equal rows, removes only strict dominance', () => {
  const rows=[{id:'cheap',cost:1,quality:60},{id:'better',cost:2,quality:90},{id:'worse',cost:3,quality:70},{id:'equal',cost:2,quality:90}];
  assert.deepEqual(value.frontier(rows).map(r=>r.dominated),[false,false,true,false]);
});
