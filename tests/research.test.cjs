const {test}=require('node:test');
const assert=require('node:assert/strict');
const research=require('../assets/research.js');
const now=Date.parse('2026-09-08T12:00:00Z');
const data={source:{status:'ok',retrieved_at:'2026-09-08T00:00:00Z'},models:{astra:{default_variant:'max',variants:[{slug:'max',rank_compatible:true,index_estimated:true,scores:{terminalbench_v4:59,intelligence:53}},{slug:'low',rank_compatible:true,index_estimated:false,scores:{terminalbench_v4:0}}]}}};
test('raw reported result remains available when composite is estimated',()=>{
  assert.equal(research.score(data,'astra',null,'terminalbench_v4',false,now),59);
  assert.equal(research.score(data,'astra',null,'intelligence',false,now),null);
  assert.equal(research.score(data,'astra',null,'intelligence',true,now),53);
});
test('variant selection preserves zero and never chooses best result automatically',()=>{
  assert.equal(research.score(data,'astra','low','terminalbench_v4',false,now),0);
  assert.equal(research.variant(data,'astra','removed'),null);
});
test('failed or old source still has visible observations but cannot rank',()=>{
  const failed=structuredClone(data);failed.source.status='error';
  assert.equal(research.variant(failed,'astra').scores.terminalbench_v4,59);
  assert.equal(research.score(failed,'astra',null,'terminalbench_v4',false,now),null);
  assert.equal(research.score(data,'astra',null,'terminalbench_v4',false,now+8*86400000),null);
});
test('display-only identity never gets price ranking',()=>{
  const incompatible=structuredClone(data);incompatible.models.astra.variants[0].rank_compatible=false;
  assert.equal(research.score(incompatible,'astra',null,'terminalbench_v4',false,now),null);
});
