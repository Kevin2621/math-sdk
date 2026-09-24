"""Multiplier payout, persistence, serialization and tamper regression coverage."""
import copy
import json
from pathlib import Path
from fractions import Fraction
from random import Random
import unittest
from line_model import CROPS, evaluate_lines
from round_model import RoundModel
from generate_experimental import generate_round
from contract import validate

BASE=json.loads((Path(__file__).parent/'experiments/wp25-separate-bonus.json').read_text())

class MultiplierTests(unittest.TestCase):
    def setUp(self):
        self.pay={(c,n):v for c in CROPS for n,v in ((3,100),(4,200),(5,500))}

    def line(self,seq,values):
        b=[[s,'C07','C08'] for s in seq]
        return evaluate_lines(b,{1:[0]*5},self.pay,{(r,0):v for r,v in values.items()})

    def test_addition_and_only_wilds_in_winning_prefix(self):
        result=self.line(['C01','W','W','C02','W'],{1:2,2:3,4:3})
        self.assertEqual((result.total,result.awards[0].base_amount,result.awards[0].multiplier),(500,100,5))
        self.assertEqual(self.line(['W','W','C01','C02','C03'],{0:1,1:1}).total,200)
        self.assertEqual(self.line(['C01']*5,{}).total,500)

    def test_all_five_reels_and_all_wilds(self):
        self.assertEqual(self.line(['W']*5,{r:3 for r in range(5)}).total,7500)
        self.assertEqual(self.line(['W','C01','C01','C01','W'],{0:2,4:3}).total,2500)
        self.assertEqual(self.line(['C02','W','C01','C01','W'],{1:2,4:3}).total,0)
        self.assertEqual(self.line(['W','S','C01','C01','W'],{0:2,4:3}).total,0)

    def test_missing_or_invalid_multiplier_rejected(self):
        for values in ({},{0:0},{0:4},{0:True},{0:2,1:2}):
            with self.assertRaises(ValueError): self.line(['W']+['C01']*4,values)

    def model(self,weights=(0,1,0)):
        return RoundModel({1:[0]*5},self.pay,500000,30,Fraction(0),Fraction(0),Random(1),wild_multiplier_weights=weights)

    def test_entry_schedule_and_sticky_values_survive_collisions(self):
        for scatters,spins in ((3,10),(4,15),(5,20)):
            m=self.model()
            b=[['S' if r<scatters else 'C03','C04','C05'] for r in range(5)]
            self.assertEqual(m.spin(b)['entryAward'],spins)
            b=[['C01','C02','C03'] for _ in range(5)]; b[0][0]='W'; b[0][1]='W'
            first=m.spin(b,fixture_target=(4,0))
            self.assertEqual(first['wildMultipliers'],{(0,0):2,(0,1):2,(4,0):2})
            m.wild_multiplier_weights=(0,0,1)
            b[2][0]='W'
            second=m.spin(b)
            self.assertEqual(second['wildMultipliers'][(0,0)],2)
            self.assertEqual(second['wildMultipliers'][(4,0)],2)
            self.assertEqual(second['wildMultipliers'][(2,0)],3)
            self.assertEqual(second['grantedExtraSpins'],1)
            full=m.spin([['W']*3 for _ in range(5)])
            self.assertEqual(full['roundTotal'],500000)
            self.assertEqual(full['lineWin']+full['harvestTopUp'],full['spinWin'])
            self.assertEqual(m.sticky_multipliers,{})

    def test_generated_books_validate_and_reject_tampering(self):
        config=copy.deepcopy(BASE);config['schemaVersion']=3
        config['fixtureMath'].update(wildMultiplierWeights=[6,3,1],bonusScatterPays={'3':200,'4':500,'5':1000},collisionSpinsPerHit=True)
        seen=False
        for i in range(40):
            sdk,book=generate_round(config,90,i)
            self.assertEqual(validate(book)['roundTotal'],sdk['payoutMultiplier'])
            for event in book['events']:
                if event['type']=='winInfo':
                    bad=copy.deepcopy(book)
                    bad['events'][event['index']]['wins'][0]['meta']['lineMultiplier']+=1
                    with self.assertRaises(ValueError): validate(bad)
                if event['type']=='wildPickinsSpinResult' and event['wildMultipliers']:
                    seen=True;bad=copy.deepcopy(book)
                    bad['events'][event['index']]['wildMultipliers'][0]['multiplier']=4
                    with self.assertRaises(ValueError): validate(bad)
        self.assertTrue(seen)

    def test_bonus_scatter_cash_replaces_retrigger_and_collision_still_adds_one(self):
        for count,award in ((3,200),(4,500),(5,1000)):
            m=self.model();m.bonus_scatter_pays={3:200,4:500,5:1000}
            board=[['S','C04','C05'] for _ in range(5)]
            first=m.spin(board)
            self.assertEqual(first['scatterWin'],0)
            board=[['C01','C02','C03'] for _ in range(5)];board[0][0]='W'
            m.spin(board)
            for r in range(count):board[r][1]='S'
            result=m.spin(board)
            self.assertEqual(result['scatterWin'],award)
            self.assertEqual(result['nominalRetriggerAward'],0)
            self.assertEqual(result['nominalCollisionAward'],1)
            self.assertEqual(result['grantedExtraSpins'],1)
            self.assertEqual(result['spinWin'],result['lineWin']+award)

    def test_scatter_cash_is_clipped_after_lines_and_stops_extra_spins(self):
        m=self.model();m.bonus_scatter_pays={3:200,4:500,5:1000}
        m.spin([['S','C04','C05'] for _ in range(5)])
        m.paytable={k:0 for k in self.pay};m.total=m.cap-50
        result=m.spin([['S','C01','C02'] for _ in range(5)])
        self.assertEqual((result['nominalScatterWin'],result['scatterWin']),(1000,50))
        self.assertEqual((result['roundTotal'],result['grantedExtraSpins'],result['endReason']),(m.cap,0,'roundCap'))

    def test_scatters_covered_by_sticky_wilds_do_not_pay(self):
        m=self.model();m.bonus_scatter_pays={3:200,4:500,5:1000}
        m.spin([['S','C04','C05'] for _ in range(5)])
        m.spin([['W' if r<3 else 'C01','C02','C03'] for r in range(5)])
        result=m.spin([['S','C04','C05'] for _ in range(5)])
        self.assertEqual(len(result['scatterPositions']),2)
        self.assertEqual(result['scatterWin'],0)

    def test_each_collision_grants_one_until_lifetime_budget_is_exhausted(self):
        m=self.model();m.collision_spins_per_hit=True
        m.spin([['S','C04','C05'] for _ in range(5)])
        board=[['W' if r<3 else 'C01','C02','C03'] for r in range(5)]
        first=m.spin(board)
        self.assertEqual(first['nominalCollisionAward'],0)
        second=m.spin(board)
        self.assertEqual((second['nominalCollisionAward'],second['grantedExtraSpins']),(3,3))
        self.assertTrue(all(v==2 for v in second['wildMultipliers'].values()))
        m.granted=28;m.completed=27;m.remaining=1
        clipped=m.spin(board)
        self.assertEqual((clipped['nominalCollisionAward'],clipped['grantedExtraSpins'],clipped['totalGranted'],clipped['remaining']),(3,2,30,2))
        next_spin=m.spin(board)
        self.assertEqual((next_spin['grantedExtraSpins'],next_spin['remaining']),(0,1))
        final=m.spin(board)
        self.assertEqual((final['grantedExtraSpins'],final['endReason']),(0,'spinsExhausted'))

if __name__=='__main__': unittest.main()
