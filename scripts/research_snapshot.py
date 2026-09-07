"""Reproduce the dated scenario cost table without calling any model API."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    'openai:gpt-5.6-luna', 'openai:gpt-5.6-terra', 'openai:gpt-5.6-sol',
    'anthropic:claude-sonnet-5', 'anthropic:claude-opus-5', 'anthropic:claude-fable-5.1',
    'deepseek:deepseek-v4-flash', 'deepseek:deepseek-v4-pro',
    'google:gemini-3.1-flash-lite', 'google:gemini-3.8-flash', 'moonshot:kimi-k3',
]
SCENARIOS = {
    'patch': {'input': .1, 'cached_input': 0, 'output': .02},
    'agent_cache_reads': {'input': .4, 'cached_input': .6, 'output': .08},
    'output_heavy': {'input': .1, 'cached_input': 0, 'output': .1},
}


def main():
    prices = json.loads((ROOT/'data/prices.json').read_text(encoding='utf-8'))
    benchmarks = json.loads((ROOT/'data/benchmarks.json').read_text(encoding='utf-8'))
    by_id = {model['id']:model for model in prices['models']}
    rows = []
    for model_id in MODELS:
        model = by_id[model_id]
        if model.get('price_comparable') is False:
            raise ValueError(f'Not text-price comparable: {model_id}')
        summary = benchmarks['models'].get(model_id, {}).get('benchlm_summary') or {}
        rows.append({
            'id':model_id, 'name':model['name'],
            'rates_usd_per_million':{key:model[key] for key in ('input','cached_input','output')},
            'source_url':model['source_url'], 'last_seen_at':model['last_seen_at'], 'tier':model['tier'],
            'scenario_cost_usd':{name:round(sum(tokens[key]*model[key] for key in tokens),6) for name,tokens in SCENARIOS.items()},
            'benchlm_categories':summary.get('categories'),
            'benchlm_evidence_status':summary.get('evidence_status'),
            'benchmark_source_url':summary.get('source_url'),
        })
    payload = {'price_snapshot_checked_at':prices['last_checked_at'], 'benchlm_generated_at':benchmarks.get('benchlm',{}).get('generated_at'), 'unit':'USD; token volumes in millions', 'scope':'Arithmetic scenarios, not measured task costs. Short-context standard/DeepSeek PEAK. Cache reads only; no write/storage, tools, retries, tax or subscription fees. Output includes billable reasoning.', 'scenarios':SCENARIOS, 'models':rows}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
