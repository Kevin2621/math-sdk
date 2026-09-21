from collections import Counter
import json
from pathlib import Path
import unittest
from balance_ldw import candidates,metrics
from generate_experimental import generate_round

class LdwBalanceTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads((Path(__file__).parent/'experiments/wp25-base-crop-focus.json').read_text())
        self.configs=dict(candidates(self.source))
    def test_minimum_pay_and_controlled_base_entry_inputs(self):
        self.assertEqual(len(self.configs),6)
        for c in self.configs.values():
            self.assertEqual(c['reels']['basegame'],self.source['reels']['basegame'])
            self.assertEqual(c['goldenRates'],self.source['goldenRates'])
            self.assertEqual(c['spinBudget'],30);self.assertEqual(c['roundCap'],500000)
            self.assertEqual(c['fixtureMath']['paths'],self.source['fixtureMath']['paths'])
            for pays in c['fixtureMath']['paytable'].values():
                self.assertGreaterEqual(min(pays.values()),25)
                self.assertLessEqual(pays['3'],pays['4']);self.assertLessEqual(pays['4'],pays['5'])
    def test_bonus_density_change_preserves_scatter_rate(self):
        for old,new in zip(self.source['reels']['freegame'],self.configs['quarter-w72']['reels']['freegame']):
            self.assertEqual(len(new),2*len(old))
            self.assertEqual(new.count('W'),old.count('W'))
            self.assertEqual(new.count('S'),2*old.count('S'))
    def test_midpoint_density_and_family_selection(self):
        c=dict(candidates(self.source,(54,),('quarter',)))
        self.assertEqual(set(c),{'quarter-w54'})
        for old,new in zip(self.source['reels']['freegame'],c['quarter-w54']['reels']['freegame']):
            self.assertEqual(len(new),len(old)*3)
            self.assertEqual(new.count('W'),old.count('W')*2)
            self.assertEqual(new.count('S'),old.count('S')*3)
        generate_round(c['quarter-w54'],54,0)
    def test_generated_floor_and_complete_round_validation(self):
        for c in self.configs.values():
            for i in range(15):
                b,_=generate_round(c,52,i)
                value=next(e['lineWin'] for e in b['events'] if e['type']=='wildPickinsSpinResult')
                self.assertTrue(value==0 or value>=25)
    def test_ldw_denominator_streaks_and_bonus_gaps(self):
        from unittest.mock import patch
        values=[.25,.8,.25,0,1,2]
        books=[]
        for i,v in enumerate(values):
            results=[dict(type='wildPickinsSpinResult',lineWin=int(v*100))]
            if i in (0,5):results.append(dict(type='wildPickinsSpinResult',bonusTotal=200))
            books.append(dict(events=results))
        with patch('balance_ldw.read_books',return_value=iter(books)):
            r=metrics(Path('.'))
        self.assertEqual(r['baseLdwRate'],.5);self.assertEqual(r['ldwAmongPaying'],3/5)
        self.assertEqual(r['longestLdwStreak'],3);self.assertEqual(r['overlappingThreeLdwWindows'],1)
        self.assertEqual(r['belowQuarterCount'],0);self.assertEqual(r['bonusGapMedian'],5)
