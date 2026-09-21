from pathlib import Path
from fractions import Fraction
from random import Random
import json
import sys
import unittest
from round_model import RoundModel,choose_golden
from book_export import BookExporter
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'wild-pickins/tools'))
from contract import validate

class RoundTests(unittest.TestCase):
    def test_all_accepted_fixture_transitions_and_export(self):
        count=0
        for path in sorted((ROOT/'wild-pickins/fixtures/v1').glob('*.json')):
            with self.subTest(book=path.name):
                b=json.loads(path.read_text()); model=RoundModel(
                    {i:p for i,p in enumerate(b['fixtureMath']['paths'],1)},
                    {(c,int(n)):v for c,vals in b['fixtureMath']['paytable'].items() for n,v in vals.items()},
                    b['roundCap'],b['spinBudget'],Fraction(0),Fraction(0),Random(0))
                exporter=BookExporter()
                for reveal in (e for e in b['events'] if e['type']=='reveal'):
                    t=reveal['goldenTarget']; target=(t['reel'],t['row']) if t is not None else None
                    result=model.spin(reveal['underlyingBoard'],fixture_target=target)
                    expected=next(e for e in b['events'] if e['type']=='wildPickinsSpinResult' and e['spinId']==reveal['spinId'])
                    for key in ('finalBoard','remaining','totalGranted','completedBonusSpins','grantedExtraSpins','nominalCollisionAward',
                                'nominalRetriggerAward','lineWin','harvestTopUp','spinWin','roundTotal','bonusTotal','endReason'):
                        self.assertEqual(result[key],expected[key],key)
                    exporter.append(result,finished=model.ended,win_level=1);count+=1
                self.assertTrue(model.ended);self.assertEqual(model.sticky,set())
                generated={**b,'events':exporter.events};validate(generated)
                with self.assertRaises(ValueError): model.spin(reveal['underlyingBoard'])
        self.assertEqual(count,612)
    def test_uniform_selection_has_one_slot_per_eligible_cell(self):
        class Controlled:
            def __init__(self,index):self.index=index;self.calls=0
            def randrange(self,n):
                self.calls+=1
                return 0 if self.calls==1 else self.index
        board=[['C01']*3 for _ in range(5)];board[0][0]='W';board[0][1]='S';sticky={(1,0)}
        eligible=[(r,y) for r in range(5) for y in range(3) if (r,y) not in sticky and board[r][y]=='C01']
        targets=[choose_golden(board,sticky,Fraction(1),Controlled(i)) for i in range(len(eligible))]
        self.assertEqual(targets,eligible)
    def test_zero_rate_and_no_eligible_target(self):
        self.assertIsNone(choose_golden([['C01']*3 for _ in range(5)],set(),Fraction(0),Random(0)))
        self.assertIsNone(choose_golden([['W']*3 for _ in range(5)],set(),Fraction(1),Random(0)))
    def test_seeded_selection_reproducible(self):
        board=[['C01']*3 for _ in range(5)]
        def sequence():
            rng=Random(42)
            return [choose_golden(board,set(),Fraction(1,3),rng) for _ in range(50)]
        self.assertEqual(sequence(),sequence())

if __name__=='__main__':unittest.main()
