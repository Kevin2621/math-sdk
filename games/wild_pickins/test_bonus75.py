import json
from pathlib import Path
from collections import Counter
import unittest
from build_bonus75 import build
from src.reels.generator import trigger_probability

class Bonus75Tests(unittest.TestCase):
    def test_isolation_and_entry(self):
        source=json.loads((Path(__file__).parent/'experiments/wp25-mix28-bonus-high35-no-scatters.json').read_text())
        original=json.dumps(source,sort_keys=True);v=build(source)
        self.assertEqual(v,build(source));self.assertEqual(original,json.dumps(source,sort_keys=True))
        p=trigger_probability(v['6']['reels']['basegame'],'S',3)
        self.assertTrue(74<1/p<76)
        for key,c in v.items():
            self.assertEqual(c['reels']['basegame'],v['6']['reels']['basegame'])
            for r,strip in enumerate(c['reels']['basegame']):
                for symbol in ('C01','C02','C03','W'):
                    self.assertEqual([i for i,s in enumerate(strip) if s==symbol],[i for i,s in enumerate(source['reels']['basegame'][r]) if s==symbol])
            for r,strip in enumerate(c['reels']['freegame']):
                self.assertEqual(len(strip),240);self.assertEqual(strip.count('W'),int(key));self.assertNotIn('S',strip)
                for symbol in ('C01','C02','C03'):
                    self.assertEqual([i for i,s in enumerate(strip) if s==symbol],[i for i,s in enumerate(source['reels']['freegame'][r]) if s==symbol])
