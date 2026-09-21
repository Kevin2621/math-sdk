import copy,json
from pathlib import Path
from fractions import Fraction
from random import Random
import unittest
from round_model import RoundModel
from generate_experimental import generate_round
from contract import validate

CONFIG=json.loads((Path(__file__).parent/'experiments/wp25-separate-bonus.json').read_text())
class SeparateBonusTests(unittest.TestCase):
 def model(self):
  fm=CONFIG['fixtureMath']
  def table(t):return {(c,int(n)):v for c,vs in t.items() for n,v in vs.items()}
  return RoundModel(dict(enumerate(fm['paths'],1)),table(fm['paytable']),500000,30,Fraction(0),Fraction(0),Random(1),bonus_paytable=table(fm['bonusPaytable']))
 def test_mode_specific_pays_and_full_harvest_cap(self):
  m=self.model();base=m.spin([['C01']*3 for _ in range(5)])
  self.assertEqual(base['lineWin'],5000)
  m=self.model();m.spin([['S','C01','C02'] for _ in range(5)])
  bonus=m.spin([['C01']*3 for _ in range(5)]);self.assertEqual(bonus['lineWin'],3000)
  prior=m.total
  full=m.spin([['W']*3 for _ in range(5)])
  self.assertEqual(full['roundTotal'],500000);self.assertEqual(full['endReason'],'fullHarvest')
  self.assertEqual(full['harvestTopUp'],500000-prior-full['lineWin'])
 def test_base_unchanged_and_validator_requires_versioned_table(self):
  old=json.loads((Path(__file__).parent/'experiments/wp25-ldw-quarter-w54.json').read_text())
  bonuses=0
  for i in range(100):
   b,e=generate_round(CONFIG,58,i);o,_=generate_round(old,58,i)
   base=lambda x:next(v for v in x['events'] if v['type']=='wildPickinsSpinResult')
   self.assertEqual(base(b),base(o))
   if any(v['type']=='freeSpinTrigger' for v in b['events']):
    bonuses+=1
    wrong=copy.deepcopy(e);wrong['fixtureMath']['bonusPaytable']=wrong['fixtureMath']['paytable']
    with self.assertRaises(ValueError):validate(wrong)
   bad=copy.deepcopy(e);bad['schemaVersion']=1
   with self.assertRaises(ValueError):validate(bad)
  self.assertGreater(bonuses,0)
