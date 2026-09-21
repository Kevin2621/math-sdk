import json
from pathlib import Path
import unittest
from investigate_bonus import variants
from line_model import evaluate_lines
from reel_source import ReelSource

class BonusInvestigationTests(unittest.TestCase):
 def setUp(self):
  self.source=json.loads((Path(__file__).parent/'experiments/wp25-ldw-quarter-w54.json').read_text())
  self.variants=dict(variants(self.source))
 def test_base_and_rule_inputs_are_unchanged(self):
  for c in self.variants.values():
   for key in ('fixtureMath','spinBudget','roundCap','lineSetId'):self.assertEqual(c[key],self.source[key])
   self.assertEqual(c['reels']['basegame'],self.source['reels']['basegame'])
   self.assertEqual(c['goldenRates']['basegame'],self.source['goldenRates']['basegame'])
   ReelSource(c['reels']['freegame'])
 def test_scatter_arm_preserves_wild_density_and_halves_scatter_density(self):
  for before,after in zip(self.source['reels']['freegame'],self.variants['scatter_half']['reels']['freegame']):
   self.assertEqual(len(after),2*len(before))
   self.assertEqual(after.count('W'),2*before.count('W'))
   self.assertEqual(after.count('S'),before.count('S'))
 def test_repricing_is_exact_and_cannot_introduce_cap_termination(self):
  fm=self.source['fixtureMath'];paths=dict(enumerate(fm['paths'],1))
  pays={(c,int(n)):v for c,vs in fm['paytable'].items() for n,v in vs.items()}
  self.assertTrue(all(v*3%5==0 for v in pays.values()))
  scaled={k:v*3//5 for k,v in pays.items()}
  for board in ([['W']*3 for _ in range(5)],[['C01','C02','S'] for _ in range(5)]):
   self.assertEqual(evaluate_lines(board,paths,scaled).total*5,evaluate_lines(board,paths,pays).total*3)
  self.assertLess(max(pays.values())*25*31,self.source['roundCap'])
