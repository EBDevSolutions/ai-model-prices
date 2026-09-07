(function (root) {
  'use strict';
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const validRate = value => finite(value) && value >= 0;
  function cost(model, tokens) {
    const amounts = [tokens.input, tokens.cached, tokens.output];
    const rates = [model.input, model.cached_input, model.output];
    if (model.price_comparable === false || !rates.every(validRate) || !amounts.every(validRate)) return null;
    const value = amounts.reduce((sum, amount, i) => sum + amount * rates[i], 0);
    return finite(value) ? value : null;
  }
  function quality(record, category, includeEstimated = false) {
    const summary = record?.benchlm_summary;
    if (!summary || !['supported', 'estimated'].includes(summary.evidence_status)) return null;
    if (summary.evidence_status === 'estimated' && !includeEstimated) return null;
    const value = summary.categories?.[category];
    return finite(value) && value >= 0 && value <= 100 ? value : null;
  }
  function eligible(model, provider, now = Date.now()) {
    const checked = Date.parse(model.last_seen_at);
    return model.active !== false && model.availability === 'active' && provider?.status === 'ok'
      && Number.isFinite(checked) && checked <= now && now - checked <= 48 * 60 * 60 * 1000;
  }
  function frontier(rows) {
    return rows.map(row => ({...row, dominated: rows.some(other =>
      other.id !== row.id && other.cost <= row.cost && other.quality >= row.quality
      && (other.cost < row.cost || other.quality > row.quality))}));
  }
  const api = {cost, quality, eligible, frontier};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ValueAnalysis = api;
})(globalThis);
