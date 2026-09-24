import json
from pathlib import Path
import unittest
from compare_visibility_candidates import variants

class VisibilityTests(unittest.TestCase):
    def test_controlled_nested_replacements(self):
        c=json.loads((Path(__file__).parent/'experiments/wp25-high30-picks-off.json').read_text())
        original=json.dumps(c,sort_keys=True);v=variants(c)
        self.assertEqual(v,variants(c));self.assertEqual(original,json.dumps(c,sort_keys=True))
        self.assertEqual(v['control']['reels'],c['reels'])
        for r in range(5):
            def changes(name):return {i:s for i,s in enumerate(v[name]['reels']['basegame'][r]) if s!=c['reels']['basegame'][r][i]}
            self.assertEqual(len(changes('high35')),12);self.assertEqual(len(changes('high40')),24)
            self.assertEqual(len(changes('wild5')),1);self.assertEqual(len(changes('wild6')),2)
            self.assertTrue(changes('high35').items()<=changes('high40').items())
            self.assertTrue(changes('wild5').items()<=changes('wild6').items())
