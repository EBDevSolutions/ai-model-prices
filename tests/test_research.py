import copy
import json
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_research as research

FIXTURE=Path(__file__).parent/'fixtures/aa-models.json'

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.items=json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.astra=next(x for x in self.items if x['slug']=='gpt-6-astra')

    def test_raw_units_zero_and_index_are_distinct(self):
        result=research.variant_record(self.astra,'2026-09-08T00:00:00Z')
        self.assertAlmostEqual(result['scores']['terminalbench_v4'],59.090909)
        self.assertAlmostEqual(result['scores']['scicode'],56.481481)
        self.assertAlmostEqual(result['scores']['intelligence'],52.814069)
        zero=copy.deepcopy(self.astra);zero['terminalbenchV40']=0
        self.assertEqual(research.variant_record(zero,'now')['scores']['terminalbench_v4'],0)
        self.assertNotIn('ifbench',result['scores'])

    def test_invalid_percent_does_not_silently_scale(self):
        for value in [True,float('nan'),-1,59.0]:
            broken=copy.deepcopy(self.astra);broken['terminalbenchV40']=value
            with self.assertRaises(ValueError):research.variant_record(broken,'now')

    def test_chunked_page_parser_and_version_guard(self):
        items=[]
        for i in range(100):
            item=copy.deepcopy(self.astra);item['id']=str(i);item['slug']=f'model-{i}';items.append(item)
        payload='1:'+json.dumps({'models':items})+'\n'
        half=len(payload)//2
        html='<p>Artificial Analysis Intelligence Index v4.3</p>'+''.join('<script>self.__next_f.push('+json.dumps([1,chunk])+')</script>' for chunk in [payload[:half],payload[half:]])
        self.assertEqual(len(research.extract_page(html)),100)
        with self.assertRaises(ValueError):research.extract_page(html.replace('v4.3','v4.4'))
        with self.assertRaises(ValueError):research.extract_page('<p>Intelligence Index v4.3</p>')

    def test_explicit_mapping_rejects_wrong_creator(self):
        mapping={'models':{'openai:gpt-6-astra':{'variants':['gpt-6-astra'],'release_slug':'gpt-6-astra','default_variant':'gpt-6-astra'}}}
        prices={'models':[{'id':'openai:gpt-6-astra','provider':'openai','active':True}]}
        result=research.build_update(self.items,mapping,prices,'now','hash')
        self.assertEqual(result['coverage']['with_any_aa_result'],1)
        altered=copy.deepcopy(self.items)
        next(x for x in altered if x['slug']=='gpt-6-astra')['creator']['slug']='anthropic'
        with self.assertRaises(ValueError):research.build_update(altered,mapping,prices,'now','hash')

    def test_no_cross_model_fill_and_retraction(self):
        mapping={'models':{'openai:gpt-6-astra':{'variants':['absent'],'release_slug':'gpt-6-astra'}}}
        prices={'models':[{'id':'openai:gpt-6-astra','provider':'openai','active':True}]}
        result=research.build_update(self.items,mapping,prices,'now','hash')
        self.assertEqual(result['models']['openai:gpt-6-astra']['variants'],[])
        self.assertEqual(result['models']['openai:gpt-6-astra']['status'],'not_reported')
        self.assertEqual(result['coverage']['with_any_aa_result'],0)

    def test_source_failure_preserves_previous_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir()
            target=root/'data/research.json'
            original={'source':{'status':'ok','retrieved_at':'2026-09-07T12:00:00Z'},'models':{'test':{'variants':[{'scores':{'scicode':50}}]}}}
            target.write_text(json.dumps(original),encoding='utf-8')
            with patch.object(research,'ROOT',root),patch.object(sys,'argv',['update_research.py']),patch.object(research.requests,'get',side_effect=research.requests.Timeout('test timeout')):
                self.assertEqual(research.main(),1)
            retained=json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(retained['models'],original['models'])
            self.assertEqual(retained['source']['retrieved_at'],original['source']['retrieved_at'])
            self.assertEqual(retained['source']['status'],'error')

if __name__=='__main__':unittest.main()
