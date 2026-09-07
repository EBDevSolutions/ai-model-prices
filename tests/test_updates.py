import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_prices as prices
import update_benchmarks as benchmarks

FIXTURES = Path(__file__).parent / 'fixtures'


class PriceTests(unittest.TestCase):
    def page(self, name):
        html = (FIXTURES / f'{name}.html').read_text(encoding='utf-8')
        return prices.Page(html, prices.normalized_text(html))

    def test_anthropic_sentence_case_and_cache_column(self):
        result = prices.parse_anthropic(self.page('anthropic'))
        self.assertEqual(len(result), 17)
        self.assertEqual(result['anthropic:claude-sonnet-5']['input'], 2)
        self.assertEqual(result['anthropic:claude-fable-5.1']['cached_input'], .25)
        self.assertEqual(result['anthropic:claude-opus-4.1']['active'], False)

    def test_deepseek_rowspan_peak_not_off_peak(self):
        result = prices.parse_deepseek(self.page('deepseek'))
        self.assertEqual(len(result), 3)
        pro = result['deepseek:deepseek-v4-pro']
        self.assertEqual((pro['input'], pro['cached_input'], pro['output']), (1.32, .044, 3.96))
        self.assertEqual(pro['tier'], 'peak')

    def test_legacy_deepseek_standard_matrix(self):
        html = '<table><tr><th>MODEL</th><th>deepseek-chat</th></tr><tr><td>INPUT TOKENS (CACHE HIT)</td><td>$0.1</td></tr><tr><td>INPUT TOKENS (CACHE MISS)</td><td>$1</td></tr><tr><td>OUTPUT TOKENS</td><td>$2</td></tr></table>'
        item = prices.parse_deepseek(prices.Page(html, ''))['deepseek:deepseek-chat']
        self.assertEqual(item['input'], 1)
        self.assertEqual(item['tier'], 'standard')

    def test_google_audio_output_is_not_text_comparable(self):
        html = '<h2>Gemini TTS</h2><code>gemini-2.5-flash-preview-tts</code><table><tr><td>Input price</td><td>$0.50 (text)</td></tr><tr><td>Output price</td><td>$10 (audio)</td></tr></table>'
        record = next(iter(prices.parse_google(prices.Page(html, '')).values()))
        self.assertFalse(record['price_comparable'])

    def test_rejected_snapshot_retains_whole_provider_and_history(self):
        good_id, good = prices.model_record('test', 'good', 'Good', 1, .1, 2, 'standard', '')
        bad_id, bad = prices.model_record('test', 'bad', 'Bad', 1, .1, 2, 'standard', '')
        old = {'providers':[{'id':'test','model_count':2}], 'models':[good, bad]}
        incoming = copy.deepcopy({good_id:good, bad_id:bad})
        incoming[good_id]['input'] = 2
        incoming[bad_id]['output'] = float('nan')
        spec = prices.ProviderSpec('test', 'https://example.com', 2, lambda _: incoming)
        with tempfile.TemporaryDirectory() as directory:
            pp, hp = Path(directory)/'prices.json', Path(directory)/'history.json'
            pp.write_text(json.dumps(old)); hp.write_text('{"events":[]}')
            with patch.object(prices, 'PRICES_PATH', pp), patch.object(prices, 'HISTORY_PATH', hp), patch.object(prices, 'SPECS', [spec]), patch.object(prices, 'fetch', return_value=prices.Page('', '')):
                self.assertEqual(prices.update(), 1)
            self.assertEqual({m['id']:m for m in json.loads(pp.read_text())['models']}, {m['id']:m for m in old['models']})
            self.assertEqual(json.loads(hp.read_text())['events'], [])


class BenchmarkTests(unittest.TestCase):
    def fixture(self):
        model = {'slug':'model', 'canonicalModelKey':'model', 'model':'Model', 'creator':'OpenAI', 'url':'https://benchlm.ai/models/model', 'evidenceStatus':'supported', 'coverage':{'verifiedBenchmarkCount':1,'generatedBenchmarkCount':0}, 'benchmarks':{'coding':{'sweVerified':70}}, 'scores':{'verifiedDisplayScore':62, 'verifiedDisplayCategoryScores':{'coding':70}}, 'displayScore':71,'scoreInterval90':{'lower':68,'upper':74}}
        return {'items':[model]+[{} for _ in range(99)]}

    def test_no_generic_gpqa_alias_or_invalid_percentage(self):
        self.assertIsNone(benchmarks.raw_score({'benchmarks':{'knowledge':{'gpqa':90}}}, benchmarks.RAW_SCORE_PATHS['gpqa_diamond']))
        for value in [True, float('nan'), float('inf'), -1, 101]:
            self.assertIsNone(benchmarks.raw_score({'benchmarks':{'knowledge':{'gpqaDiamond':value}}}, benchmarks.RAW_SCORE_PATHS['gpqa_diamond']))

    def test_display_name_is_not_identity(self):
        self.assertIsNone(benchmarks.find_bench_model({'provider':'openai','model_id':'different','name':'Model'}, {'model': self.fixture()['items'][0]}))

    def test_interval_is_not_attached_to_verified_score(self):
        data = benchmarks.build_update({'models':[{'id':'openai:model','model_id':'model','provider':'openai'}]}, {'benchmarks':[{'id':'swe_bench_verified','label':'SWE'}]}, self.fixture())
        summary = data['models']['openai:model']['benchlm_summary']
        self.assertEqual(summary['overall'], 62)
        self.assertIsNone(summary['interval_90'])
        self.assertEqual(summary['source_display_score'], 71)

    def test_retracted_cells_and_summary_removed_vendor_preserved(self):
        old = {'models':{'openai:model':{'scores':{'swe_bench_verified':70,'gpqa_diamond':80},'score_sources':{'swe_bench_verified':{'source_url':'https://benchlm.ai/models/model'}},'benchlm_summary':{'overall':62},'source_url':'https://vendor.example/report'}}}
        data = benchmarks.build_update({'models':[]}, old, {'items':[{} for _ in range(100)]})
        record = data['models']['openai:model']
        self.assertIsNone(record['scores']['swe_bench_verified'])
        self.assertEqual(record['scores']['gpqa_diamond'], 80)
        self.assertNotIn('benchlm_summary', record)
        self.assertEqual(old['models']['openai:model']['scores']['swe_bench_verified'], 70)

    def test_incomplete_dataset_is_rejected(self):
        with self.assertRaises(RuntimeError):
            benchmarks.build_update({}, {}, {'items':[]})


if __name__ == '__main__':
    unittest.main()
