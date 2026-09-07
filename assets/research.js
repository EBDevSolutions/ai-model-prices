(function(root){
  'use strict';
  function variant(data,id,selected){
    const record=data?.models?.[id];
    if(!record)return null;
    const slug=selected || record.default_variant;
    return record.variants.find(v=>v.slug===slug) || null;
  }
  function score(data,id,selected,metric,includeEstimated=false,now=Date.now()){
    const record=variant(data,id,selected);
    if(!record || record.rank_compatible===false)return null;
    const age=now-Date.parse(data?.source?.retrieved_at);
    if(data?.source?.status!=='ok' || !Number.isFinite(age) || age<0 || age>7*86400000)return null;
    // Composite uncertainty does not invalidate independently reported raw tests.
    if(metric==='intelligence' && record.index_estimated!==false && !includeEstimated)return null;
    const value=record.scores?.[metric];
    return Number.isFinite(value)?value:null;
  }
  const api={variant,score};
  if(typeof module!=='undefined' && module.exports)module.exports=api;
  else root.Research=api;
})(globalThis);
