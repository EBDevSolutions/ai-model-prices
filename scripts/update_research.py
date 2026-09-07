"""Import published Artificial Analysis model-page data; never execute page code.

The public model page embeds the dataset powering its charts. This adapter is
intentionally version-pinned: layout/schema/version changes retain last good data.
It does not call protected endpoints or require an API key in the public website.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from update_benchmarks import load_json, save_json_atomic

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://artificialanalysis.ai/models/gpt-6-astra'
METHODOLOGY = 'https://artificialanalysis.ai/methodology/intelligence-benchmarking'
VERSION = '4.3'
CREATORS = {'openai':'openai','anthropic':'anthropic','google':'google','xai':'xai','deepseek':'deepseek','alibaba':'alibaba','moonshot':'kimi'}

# Keep original units separate. No synthetic Coding/Agentic composite.
METRICS = {
    'terminalbench_v4': ('Terminal-Bench 4.0 · AA', 'terminalbenchV40', '%', '4.0', 'mini-SWE-agent 2.4.6; 66 tasks; pass@1, 3 repeats'),
    'terminalbench_v21': ('Terminal-Bench 2.1 · AA', 'terminalbenchV21', '%', '2.1', 'Terminus 2; 89 tasks; pass@1, 3 repeats'),
    'scicode': ('SciCode · AA', 'scicode', '%', '1.0.1', 'scientist background; subproblem pass@1; 300s grading'),
    'automationbench': ('AutomationBench · AA', 'automationBenchPartialScore', '%', '1.0.6', '657 held-out tasks; partial score, not all-pass; 50 turns'),
    'gpqa': ('GPQA Diamond · AA', 'gpqa', '%', 'AA current protocol', 'scientific reasoning'),
    'hle': ('Humanity’s Last Exam · AA', 'hle', '%', 'AA current protocol', 'AA HLE protocol; separate from other publishers'),
    'gdp_pdf': ('GDP.pdf all-pass · AA', 'gdpPdfAllPass', '%', 'AA current protocol', 'professional document reasoning; all-pass'),
    'critpt': ('CritPt · AA', 'critpt', '%', 'AA current protocol', 'physics reasoning'),
    'lcr': ('AA-LCR', 'lcr', '%', '1.1', 'long-context reasoning'),
    'ifbench': ('IFBench · AA', 'ifbench', '%', 'AA current protocol', 'instruction following'),
    'mmmu_pro': ('MMMU-Pro · AA', 'mmmuPro', '%', 'AA current protocol', 'visual reasoning; not MMLU-Pro'),
    'analyst_agent': ('AA-AnalystAgent', 'analystAgent', '%', 'AA current protocol', 'spreadsheets and documents'),
    'gdpval': ('GDPval-AA v2', 'gdpval', 'Elo', '2', 'Elo; not a percentage'),
    'intelligence': ('AA Intelligence Index 4.3', 'intelligenceIndex', 'pkt', '4.3', 'published composite; not BenchLM'),
    'omniscience': ('AA-Omniscience Index', 'omniscience', 'pkt', 'AA current protocol', 'may be negative; not a percentage'),
}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def extract_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    visible = soup.get_text(' ',strip=True)
    if not re.search(r'Intelligence Index v' + re.escape(VERSION) + r'\b',visible):
        raise ValueError('Unknown Intelligence Index version; review methodology before importing')
    chunks=[]
    for tag in soup.find_all('script'):
        match=re.fullmatch(r'\s*self\.__next_f\.push\((.*)\)\s*;?\s*',tag.get_text(),re.S)
        if match:
            try: frame=json.loads(match.group(1))
            except ValueError: continue
            if isinstance(frame,list) and len(frame)>1 and frame[0]==1 and isinstance(frame[1],str):
                chunks.append(frame[1])
    found={}
    def walk(value):
        if isinstance(value,dict):
            if all(key in value for key in ('id','slug','creator','release','intelligenceIndex','scicode','terminalbenchV40')):
                key=value['id']
                if key in found and found[key] != value:
                    raise ValueError('Conflicting duplicate AA model ID')
                found[key]=value
            else:
                for item in value.values():walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    for line in ''.join(chunks).splitlines():
        try: payload=json.loads(line.split(':',1)[1])
        except (ValueError,IndexError):continue
        walk(payload)
    if len(found)<100:
        raise ValueError(f'Incomplete public AA dataset: {len(found)} variants')
    return list(found.values())


def variant_record(item, observed):
    scores={}
    for key,(_,field,unit,_,_) in METRICS.items():
        value=item.get(field)
        if value is None:continue
        if not number(value) or (unit=='%' and not 0<=value<=1):
            raise ValueError(f'Invalid {field} for {item["slug"]}')
        scores[key]=round(value*100 if unit=='%' else value,6)
    task_cost=((item.get('intelligenceIndexCostPerTask') or {}).get('cost') or {}).get('total')
    if task_cost is not None and (not number(task_cost) or task_cost<0):
        raise ValueError('Invalid AA task cost')
    return {
        'id':item['id'],'slug':item['slug'],'name':item['name'],
        'effort':(item.get('effort') or {}).get('label'),
        'release_slug':(item.get('release') or {}).get('slug'),
        'is_reasoning':item.get('isReasoning'),
        'index_estimated':item.get('intelligenceIndexIsEstimated'),
        'source_url':'https://artificialanalysis.ai/models/'+item['slug'],
        'retrieved_at':observed,'evaluated_at':None,
        'scores':scores,'index_cost_per_task_usd':task_cost,
        'cost_scope':'AA Intelligence Index 4.3 weighted task cost; not cost of this selected benchmark or user workload',
        'speed_by_prompt':{k:{'tokens_per_second':v.get('medianOutputSpeed'),'first_answer_seconds':v.get('medianTimeToFirstAnswerToken')} for k,v in (item.get('performanceByPromptType') or {}).items()},
    }


def build_update(items, mapping, prices, observed, digest):
    by_slug={item['slug']:item for item in items}
    if len(by_slug)!=len(items):raise ValueError('Duplicate AA variant slug')
    models={}
    for model in prices['models']:
        rule=mapping['models'].get(model['id'])
        variants=[]
        missing=[]
        if rule:
            for slug in rule['variants']:
                item=by_slug.get(slug)
                if not item:
                    missing.append(slug);continue
                if (item.get('creator') or {}).get('slug')!=CREATORS.get(model['provider']):
                    raise ValueError(f'Creator mismatch for {model["id"]}')
                if (item.get('release') or {}).get('slug')!=rule['release_slug']:
                    raise ValueError(f'Release mismatch for {slug}')
                record=variant_record(item,observed)
                record['rank_compatible']=slug not in rule.get('display_only',[])
                variants.append(record)
        models[model['id']]={
            'status':'available' if any(v['scores'] for v in variants) else 'unmapped' if not rule else 'not_reported',
            'mapping_scope':'reviewed source release and variant; exact API snapshot not independently confirmed' if rule else None,
            'reason':rule.get('note') if rule else 'Brak zatwierdzonego mapowania AA; nie oznacza braku badań modelu.',
            'default_variant':rule.get('default_variant') if rule else None,
            'missing_source_variants':missing,'variants':variants,
        }
    active=[m for m in prices['models'] if m.get('active') and m.get('price_comparable') is not False]
    coverage={key:sum(any(key in v['scores'] for v in models[m['id']]['variants']) for m in active) for key in METRICS}
    return {
        'schema_version':1,
        'source':{'id':'artificial_analysis','name':'Artificial Analysis','source_url':SOURCE,'methodology_url':METHODOLOGY,'retrieved_at':observed,'last_checked_at':observed,'status':'ok','error':None,'sha256':digest,'index_version':VERSION,'source_variant_count':len(items),'adapter':'public model page serialized chart data; not authenticated Data API'},
        'metrics':{key:{'label':label,'unit':unit,'version':version,'conditions':conditions,'source_field':field,'higher_is_better':True,'methodology_url':METHODOLOGY,'comparison_group':f'aa:{key}:{version}'} for key,(label,field,unit,version,conditions) in METRICS.items()},
        'coverage':{'active_text_price_models':len(active),'with_any_aa_result':sum(models[m['id']]['status']=='available' for m in active),'by_metric':coverage},
        'models':models,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html',type=Path,help='Use a saved public page for reproducible offline validation')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    target=ROOT/'data/research.json'
    observed=now()
    try:
        if args.html:html=args.html.read_text(encoding='utf-8')
        else:
            response=requests.get(SOURCE,timeout=(10,60),headers={'User-Agent':'ai-model-prices/3.0 (public research attribution)'})
            response.raise_for_status();html=response.text
        items=extract_page(html)
        mapping=load_json(ROOT/'data/research-model-map.json')
        payload=build_update(items,mapping,load_json(ROOT/'data/prices.json'),observed,hashlib.sha256(html.encode()).hexdigest())
        if target.exists():
            previous=load_json(target)
            old_count=previous.get('source',{}).get('source_variant_count',0)
            if len(items)<old_count*.8:raise ValueError('Suspicious shrink of AA source catalogue')
        if not args.dry_run:save_json_atomic(target,payload)
        print(json.dumps(payload['coverage']))
        return 0
    except (requests.RequestException,ValueError,KeyError,TypeError,OSError) as error:
        if target.exists() and not args.dry_run:
            previous=load_json(target)
            previous['source'].update(status='error',last_checked_at=observed,error=f'{type(error).__name__}: {error}'[:400])
            save_json_atomic(target,previous)
        print(f'AA import failed; previous observations retained: {error}')
        return 1


if __name__=='__main__':raise SystemExit(main())
