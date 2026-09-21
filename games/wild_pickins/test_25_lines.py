import copy
import json
from pathlib import Path
import unittest
from generate_experimental import generate_round
from line_model import evaluate_lines
from contract import validate

HERE=Path(__file__).resolve().parent

def config(name='golden20'):
    return json.loads((HERE/f'experiments/wp25-{name}.json').read_text())

class Experiment25Tests(unittest.TestCase):
    def test_controlled_inputs_and_symmetric_unique_map(self):
        first=config()
        paths={tuple(p) for p in first['fixtureMath']['paths']}
        self.assertEqual(len(paths),25)
        self.assertEqual(paths,{tuple(2-y for y in p) for p in paths})
        for name,rate in [('golden10',[1,10]),('golden05',[1,20])]:
            other=config(name)
            self.assertEqual(other['goldenRates']['freegame'],rate)
            for c in (first,other):
                c.pop('description',None)
                c['goldenRates'].pop('freegame',None)
            self.assertEqual(first,other)

    def test_award_scaling_and_cap_bound(self):
        c=config(); fm=c['fixtureMath']
        pays={(s,int(n)):v for s,vs in fm['paytable'].items() for n,v in vs.items()}
        win=evaluate_lines([['W']*3 for _ in range(5)],dict(enumerate(fm['paths'],1)),pays)
        self.assertEqual(win.total,5000)  # 50x total bet, 25 lines each paying 2x.
        self.assertLess(win.total*(c['spinBudget']+1),c['roundCap'])
        for vs in fm['paytable'].values():
            self.assertLess(vs['3'],vs['4']);self.assertLess(vs['4'],vs['5'])

    def test_new_version_validates_but_mutated_map_fails(self):
        _,envelope=generate_round(config(),47,0)
        validate(envelope)
        bad=copy.deepcopy(envelope)
        bad['fixtureMath']['paths'][-1]=[1,0,2,0,1]
        with self.assertRaises(ValueError):validate(bad)

class DistributionShapeTests(unittest.TestCase):
    def test_known_distribution_and_weighted_input_rejection(self):
        import tempfile
        import zstandard
        from summarize_25_lines import summarize
        from test_evaluation import book
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            (run/'experiment-config.json').write_text(json.dumps(config()))
            books=[book(0,0),book(1,200)]
            for b in books:
                for e in b['events']:
                    if e['type']=='wildPickinsSpinResult': e.setdefault('endReason',None)
            data=''.join(json.dumps(b)+'\n' for b in books).encode()
            (run/'books_base.jsonl.zst').write_bytes(zstandard.ZstdCompressor().compress(data))
            (run/'lookUpTable_base.csv').write_text('0,1,0\n1,1,200\n')
            report=summarize([run])
            self.assertEqual(report['observedReturn'],1)
            self.assertEqual(report['positiveRate'],.5)
            self.assertEqual(report['profitRate'],.5)
            self.assertEqual(report['payoutQuantiles']['0.5'],0)
            self.assertEqual(report['payoutBandCounts'],{'zero':1,'1to5x':1})
            (run/'lookUpTable_base.csv').write_text('0,2,0\n1,1,200\n')
            with self.assertRaises(ValueError):summarize([run])
