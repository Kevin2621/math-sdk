"""Paired-input, order-independence and evidence regressions for Step 2."""
import copy
import hashlib
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from experiment_random import ExperimentRandom,SCHEME
from experiment_evidence import archive_inputs,finish_evidence,digest
from generate_experimental import generate_round
from balance_multiplier_wilds import measure
from reel_source import ReelSource

HERE=Path(__file__).parent
CONFIG=json.loads((HERE/'experiments/wp25-comparison-picks-off.json').read_text())

def reveals(book):
    return {(e['gameType'],e['spinId']): (e['underlyingBoard'],e['paddingPositions']) for e in book['events'] if e['type']=='reveal'}

class IndexedRandomTests(unittest.TestCase):
    def busy(self):
        c=copy.deepcopy(CONFIG)
        # Artificial small strips provide frequent bonuses and cap terminations.
        c['reels']={mode:[['S','C01','W','C02','C03','W'] for _ in range(5)] for mode in ('basegame','freegame')}
        return c

    def test_profile_locks_rules_and_disables_picks_only_for_comparison(self):
        original=json.loads((HERE/'experiments/wp25-multiplier-wilds.json').read_text())
        for key in ('fixtureMath','reels','roundCap','spinBudget','lineSetId','schemaVersion'):
            self.assertEqual(CONFIG[key],original[key])
        self.assertEqual(CONFIG['rngScheme'],SCHEME)
        self.assertEqual(CONFIG['goldenRates'],{'basegame':[0,1],'freegame':[0,1]})
        self.assertNotEqual(original['goldenRates'],CONFIG['goldenRates'])

    def test_same_uniform_quantile_and_proportional_weights(self):
        for i in range(100):
            r=ExperimentRandom(42,i)
            low=r.weighted_value([85,12,3],'freegame',4,2)
            high=r.weighted_value([1,1,1],'freegame',4,2)
            self.assertLessEqual(low,high)
            self.assertEqual(high,r.weighted_value([100,100,100],'freegame',4,2))
        for bad in ([0,0,0],[1,-1,2],[True,1,1]):
            with self.assertRaises(ValueError):ExperimentRandom(1,1).weighted_value(bad,'basegame',0,0)

    def test_unrelated_consumption_cannot_shift_reels_or_later_rounds(self):
        inputs=ExperimentRandom(42,9);source=ReelSource(CONFIG['reels']['basegame'])
        def draw():return source.draw(Random(1),experiment_random=inputs,mode='basegame',spin_index=0)
        before=draw()
        for _ in range(50):inputs.stream('basegame',0,'golden-target').random()
        inputs.weighted_value([1,1,1],'basegame',0,1)
        self.assertEqual(before,draw())
        self.assertNotEqual(inputs.stream('basegame',0,'reel-stop',0).getstate(),inputs.stream('basegame',0,'wild-value',0).getstate())

    def test_candidate_order_and_round_order_do_not_change_books(self):
        a=self.busy();b=copy.deepcopy(a);b['fixtureMath']['wildMultiplierWeights']=[1,1,1]
        candidates=[a,b];expected={}
        for c_id,c in enumerate(candidates):
            for round_id in range(12):expected[c_id,round_id]=generate_round(c,32,round_id)
        for round_id in reversed(range(12)):
            for c_id in (1,0):self.assertEqual(generate_round(candidates[c_id],32,round_id),expected[c_id,round_id])

    def test_changed_values_preserve_reels_and_allow_real_cap_divergence(self):
        a=self.busy();b=copy.deepcopy(a)
        a['fixtureMath']['wildMultiplierWeights']=[1,0,0];b['fixtureMath']['wildMultiplierWeights']=[0,0,1]
        divergences=0;bonus_spins=0
        for i in range(40):
            _,x=generate_round(a,33,i);_,y=generate_round(b,33,i)
            rx,ry=reveals(x),reveals(y)
            for key in rx.keys()&ry.keys():
                self.assertEqual(rx[key],ry[key]);bonus_spins+=key[0]=='freegame'
            if len(rx)!=len(ry):
                divergences+=1
                short=x if len(rx)<len(ry) else y
                self.assertEqual(next(e for e in reversed(short['events']) if e['type']=='wildPickinsSpinResult')['endReason'],'roundCap')
            for book in (x,y):self.assertFalse(any(e['type']=='goldenCropPick' for e in book['events']))
        self.assertGreater(bonus_spins,0);self.assertGreater(divergences,0)

    def test_enabling_picks_does_not_shift_underlying_reels(self):
        off=self.busy();on=copy.deepcopy(off);on['goldenRates']={m:[1,1] for m in ('basegame','freegame')}
        picks=0
        for i in range(20):
            _,x=generate_round(off,34,i);_,y=generate_round(on,34,i)
            rx,ry=reveals(x),reveals(y)
            for key in rx.keys()&ry.keys():self.assertEqual(rx[key],ry[key])
            picks+=sum(e['type']=='goldenCropPick' for e in y['events'])
        self.assertGreater(picks,0)

    def test_diagnostic_and_export_use_identical_indexed_rounds(self):
        c=self.busy();summary=measure(c,35,40)
        books=[generate_round(c,35,i)[0] for i in range(40)]
        self.assertAlmostEqual(summary['observedReturn'],sum(b['payoutMultiplier'] for b in books)/4000)
        base=sum(next(e for e in b['events'] if e['type']=='wildPickinsSpinResult')['spinWin'] for b in books)
        self.assertAlmostEqual(summary['baseContribution'],base/4000)

    def test_legacy_explicit_and_implicit_streams_match(self):
        c=json.loads((HERE/'experiments/wp25-separate-bonus.json').read_text());explicit=copy.deepcopy(c);explicit['rngScheme']='legacy'
        for i in range(10):self.assertEqual(generate_round(c,58,i),generate_round(explicit,58,i))
        explicit['rngScheme']='typo'
        with self.assertRaises(ValueError):generate_round(explicit,58,0)

    def test_archived_inputs_and_output_hashes_match_bytes(self):
        raw=json.dumps(CONFIG).encode()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);m=archive_inputs(raw,output,42,10,'test')
            self.assertEqual(m['configSha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual((output/'experiment-config.json').read_bytes(),raw)
            for name,expected in m['sourceHashes'].items():self.assertEqual(digest(output/'source-snapshot'/name),expected)
            (output/'result.txt').write_text('example');finish_evidence(output,m)
            self.assertEqual(m['artifactHashes']['result.txt'],digest(output/'result.txt'))

if __name__=='__main__':unittest.main()
