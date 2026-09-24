import copy
from collections import Counter
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from balance_metrics import BalanceMetrics,mean_stats,rate_stats,distribution
from balance_multiplier_wilds import measure
from generate_experimental import generate_round

CONFIG=json.loads((Path(__file__).parent/'experiments/wp25-comparison-picks-off.json').read_text())

def event(mode,win,total,entry=0,sticky=(),before=(),collisions=(),grant=0,granted=10,completed=1):
    board=[['C01']*3 for _ in range(5)]
    values={p:2 for p in sticky}
    for r,y in sticky:board[r][y]='W'
    return dict(gameType=mode,spinWin=win,roundTotal=total,entryAward=entry,scatterWin=0,
        underlyingBoard=board,finalBoard=board,lines=SimpleNamespace(awards=[]),wildMultipliers=values,
        stickyBefore=list(before),stickyAfter=list(sticky),collisionPositions=list(collisions),
        nominalCollisionAward=len(collisions),grantedExtraSpins=grant,totalGranted=granted,endReason=None,
        completedBonusSpins=completed)

class BalanceMetricsTests(unittest.TestCase):
    def known(self):
        m=BalanceMetrics(CONFIG)
        for base in (20,100):
            m.begin_round();m.spin(event('basegame',base,base));m.end_round()
        m.begin_round();m.spin(event('basegame',0,0,entry=10))
        m.spin(event('freegame',200,200,sticky=((0,0),(0,1))))
        m.spin(event('freegame',400,600,sticky=((0,0),(0,1),(1,0)),before=((0,0),(0,1)),collisions=((0,0),(0,1)),grant=1,granted=30,completed=2));m.end_round()
        m.begin_round();m.spin(event('basegame',0,0,entry=15));m.spin(event('freegame',0,0,granted=15));m.end_round()
        return m.report()

    def test_known_return_denominators_and_conditional_reconciliations(self):
        r=self.known()
        self.assertAlmostEqual(r['returns']['totalReturn']['mean'],1.8)
        self.assertAlmostEqual(r['returns']['baseReturn']['mean'],.3)
        self.assertAlmostEqual(r['returns']['bonusReturn']['mean'],1.5)
        self.assertAlmostEqual(r['shares']['base'],1/6)
        self.assertEqual(r['base']['rates']['positive']['rate'],.5)
        self.assertAlmostEqual(r['base']['positivePayout']['mean'],.6)
        self.assertEqual(r['bonus']['entryRate']['rate'],.5)
        self.assertEqual(r['bonus']['payoutX']['mean'],3)
        self.assertEqual(r['bonus']['zeroRate']['rate'],.5)
        self.assertEqual(r['bonus']['weakRate']['rate'],.5)
        self.assertEqual(r['bonus']['startingSpinCounts'],{10:1,15:1})

    def test_round_uncertainty_does_not_treat_free_spins_as_independent(self):
        r=self.known();values=[.2,1,6,0];mean=sum(values)/4
        expected=math.sqrt(sum((v-mean)**2 for v in values)/3/4)
        self.assertAlmostEqual(r['returns']['totalReturn']['standardError'],expected)
        self.assertEqual(r['returns']['totalReturn']['count'],4)
        self.assertEqual(sum(x['count'] for x in r['sufficientStatistics']['jointBaseBonus']),4)

    def test_progress_assignment_units_and_repeated_sticky_values(self):
        r=self.known();s=r['symbolObservations']['freegame']
        self.assertEqual(s['assignedReels']['denominator'],2)
        self.assertEqual(s['assignedCells']['denominator'],3)
        self.assertEqual(s['visibleWildValues']['denominator'],5)
        self.assertEqual(s['underlying']['denominator'],45)
        self.assertEqual(r['progressByBonusSpin'][1]['observations'],1)
        self.assertEqual(r['progressByBonusSpin'][1]['meanNewSticky'],1)
        self.assertEqual(r['bonus']['collisions']['mean'],1)
        self.assertEqual(r['bonus']['grantedExtra']['mean'],.5)

    def test_empty_conditions_are_null_and_zero_hits_have_nonzero_upper_bound(self):
        m=BalanceMetrics(CONFIG)
        for _ in range(2):m.begin_round();m.spin(event('basegame',0,0));m.end_round()
        r=m.report()
        self.assertIsNone(r['base']['positivePayout']['mean'])
        self.assertIsNone(r['bonus']['payoutX']['mean'])
        self.assertIsNone(r['shares']['base'])
        self.assertGreater(r['capHitRate']['wilson95'][1],0)
        self.assertFalse(r['screening']['releaseAccepted'])
        self.assertFalse(r['screening']['coverage']['bonusEntriesSufficient'])
        json.dumps(r,allow_nan=False)

    def test_histogram_quantiles_and_one_observation_uncertainty(self):
        r=distribution(Counter({0:2,10:1,20:1}))
        self.assertEqual(r['quantiles']['0.5'],0)
        self.assertEqual(r['quantiles']['0.95'],20)
        self.assertIsNone(mean_stats(Counter({5:1}))['standardError'])
        self.assertIsNone(rate_stats(0,0)['rate'])

    def test_real_rounds_reconcile_with_independently_validated_export(self):
        c=copy.deepcopy(CONFIG)
        c['reels']={mode:[['S','C01','W','C02','C03','W'] for _ in range(5)] for mode in ('basegame','freegame')}
        report=measure(c,9050,40);r=report['metrics'];books=[generate_round(c,9050,i)[0] for i in range(40)]
        totals=[b['payoutMultiplier'] for b in books]
        self.assertAlmostEqual(r['returns']['totalReturn']['mean'],sum(totals)/4000)
        self.assertEqual(r['capHitRate']['hits'],sum(x==c['roundCap'] for x in totals))
        large=sum(x for x in totals if x>=10000)
        self.assertAlmostEqual(r['tail']['returnShare'],large/sum(totals))
        self.assertAlmostEqual(r['returns']['totalReturn']['standardError'],report['standardError'])
        self.assertGreater(r['bonus']['fullBoardRate']['hits'],0)
        self.assertFalse(r['screening']['releaseAccepted'])
        json.dumps(report,allow_nan=False)

if __name__=='__main__':unittest.main()
