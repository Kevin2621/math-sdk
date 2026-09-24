import unittest,json
from pathlib import Path
from copy import deepcopy
from exact_base_return import calculate

class ExactTests(unittest.TestCase):
    def config(self):return json.loads((Path(__file__).parent/'experiments/wp25-comparison-picks-off.json').read_text())
    def test_forced_boards(self):
        c=self.config();c['reels']['basegame']=[['C01']*3 for _ in range(5)]
        self.assertEqual(calculate(c)['baseReturn'],125)
        c['reels']['basegame']=[['W']*3 for _ in range(5)];c['fixtureMath']['wildMultiplierWeights']=[0,0,1]
        self.assertEqual(calculate(c)['baseReturn'],1875)
        c['reels']['basegame'][0]=['C08']*3;c['reels']['basegame'][1]=['C01']*3
        self.assertEqual(calculate(c)['baseReturn'],0)
    def test_simple_probability_and_guards(self):
        c=self.config();c['reels']['basegame']=[['C01','C08','C08']]+[['C01']*3 for _ in range(4)]
        self.assertEqual(calculate(c)['baseReturnFraction'],'125/3')
        c['goldenRates']['basegame']=[1,10]
        with self.assertRaises(ValueError):calculate(c)
        c['goldenRates']['basegame']=[0,1];c['roundCap']=100
        with self.assertRaises(ValueError):calculate(c)
