from collections import Counter
import copy
import json
from pathlib import Path
import unittest
from compare_base_game import candidates
from generate_experimental import generate_round

class BaseComparisonTests(unittest.TestCase):
    def setUp(self):
        self.baseline=json.loads((Path(__file__).parent/'experiments/wp25-golden05.json').read_text())
        self.configs=dict(candidates(self.baseline))

    def test_each_arm_changes_only_its_intended_factor(self):
        control=copy.deepcopy(self.configs['control'])
        for name,changed in self.configs.items():
            actual=copy.deepcopy(changed);expected=copy.deepcopy(control)
            actual.pop('description');expected.pop('description')
            if name=='golden20':expected['goldenRates']['basegame']=[1,5]
            if name=='crop_focus':expected['reels']['basegame']=actual['reels']['basegame']
            self.assertEqual(actual,expected)
        self.assertEqual(self.baseline['goldenRates']['basegame'],[1,10])

    def test_crop_arm_preserves_special_stops_and_all_crops(self):
        for old,new in zip(self.baseline['reels']['basegame'],self.configs['crop_focus']['reels']['basegame']):
            self.assertEqual(len(old),len(new))
            self.assertEqual([(i,s) for i,s in enumerate(old) if s in ('S','W')],
                             [(i,s) for i,s in enumerate(new) if s in ('S','W')])
            self.assertEqual(Counter(new),Counter(dict(C01=3,C02=3,C03=2,C04=2,C05=2,C06=2,C07=1,C08=1,S=1,W=1)))

    def test_candidates_generate_valid_complete_rounds(self):
        for c in self.configs.values():
            for i in range(30):
                b,_=generate_round(c,50,i)
                self.assertEqual(b['payoutMultiplier'],b['events'][-1]['amount'])
                self.assertLessEqual(b['payoutMultiplier'],500000)
                self.assertLessEqual(sum(e['type']=='reveal' for e in b['events']),31)
