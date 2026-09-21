import json
from pathlib import Path
import unittest
from fractions import Fraction
from sweep_frequencies import candidates
from reel_source import ReelSource


class FrequencyTests(unittest.TestCase):
    def test_only_requested_inputs_change_and_scatter_density_is_preserved(self):
        baseline = json.loads((Path(__file__).parent/'experiments/plumbing.json').read_text())
        original = json.dumps(baseline, sort_keys=True)
        for name, config in candidates(baseline):
            self.assertEqual(config['reels']['basegame'], baseline['reels']['basegame'])
            self.assertEqual(config['goldenRates']['basegame'], baseline['goldenRates']['basegame'])
            for key in ('fixtureMath', 'spinBudget', 'roundCap'):
                self.assertEqual(config[key], baseline[key])
            ReelSource(config['reels']['freegame'])
            for old, new in zip(baseline['reels']['freegame'], config['reels']['freegame']):
                self.assertEqual(Fraction(old.count('S'), len(old)), Fraction(new.count('S'), len(new)))
                ratio = 2 if name in ('wild-half', 'both-half') else 1
                self.assertEqual(Fraction(old.count('W'), len(old))/ratio, Fraction(new.count('W'), len(new)))
            golden_ratio = 2 if name in ('golden-half', 'both-half') else 1
            self.assertEqual(Fraction(*config['goldenRates']['freegame']),
                             Fraction(*baseline['goldenRates']['freegame'])/golden_ratio)
        self.assertEqual(json.dumps(baseline, sort_keys=True), original)
