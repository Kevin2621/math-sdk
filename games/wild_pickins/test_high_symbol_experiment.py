import unittest
from collections import Counter
from copy import deepcopy
from experiment_late_highs import candidates, stacked_candidates

class HighSymbolExperimentTests(unittest.TestCase):
    def test_all_reels_nested_and_specials_preserved(self):
        strip=['C01']*8+['C02']*8+['C03']*8+['C04']*204+['W']*4+['S']*8
        config={'reels':{'basegame':[strip.copy() for _ in range(5)],'freegame':[strip.copy() for _ in range(5)]}}
        original=deepcopy(config)
        variants=candidates(config,True)
        self.assertEqual(config,original)
        for r in range(5):
            changed=[]
            for k in ('8','10','12'):
                out=variants[k]['reels']['basegame'][r]
                self.assertEqual(len(out),240)
                self.assertEqual(out[-12:],strip[-12:])
                self.assertTrue(all(Counter(out)[s]==int(k) for s in ('C01','C02','C03')))
                changed.append({i for i,(a,b) in enumerate(zip(strip,out)) if a!=b})
                self.assertEqual(variants[k]['reels']['freegame'],config['reels']['freegame'])
            self.assertTrue(changed[0]<=changed[1]<=changed[2])
        late=candidates(config)
        self.assertEqual(late['12']['reels']['basegame'][:3],config['reels']['basegame'][:3])

    def test_stacks_preserve_counts_and_make_runs(self):
        strip=['C01','C02','C03','C04']*12+['C04']*180+['W']*4+['S']*8
        config={'reels':{'basegame':[strip.copy() for _ in range(5)],'freegame':[strip.copy() for _ in range(5)]}}
        variants=stacked_candidates(config)
        self.assertEqual(variants,stacked_candidates(config))
        for size in (2,3):
            for out in variants[str(size)]['reels']['basegame']:
                self.assertEqual(Counter(out),Counter(strip))
                self.assertEqual(out[-12:],strip[-12:])
                for symbol in ('C01','C02','C03'):
                    self.assertTrue(any(all(out[(i+j)%240]==symbol for j in range(size)) for i in range(240)))
            self.assertEqual(variants[str(size)]['reels']['freegame'],config['reels']['freegame'])
