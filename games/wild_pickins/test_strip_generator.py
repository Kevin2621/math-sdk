import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from src.reels.generator import construct, validate, trigger_probability
from build_reel_candidates import build

class StripTests(unittest.TestCase):
    def test_reproducible_counts(self):
        counts={'A':90,'S':10}
        a=construct(counts,seed=4,visible_limits={'S':1})
        self.assertEqual(a,construct(counts,seed=4,visible_limits={'S':1}))
        self.assertEqual(Counter(a),counts)
        validate(a,3,{'S':1})

    def test_limits_and_wrap(self):
        with self.assertRaises(ValueError): validate(['S','A','A','S'],3,{'S':1})
        validate(['S','A','A','S'],3,{'S':2})
        with self.assertRaises(ValueError): construct({'S':5,'A':5},seed=1,visible_limits={'S':1})
        a=construct({'S':5,'A':5},seed=1,visible_limits={'S':2})
        validate(a,3,{'S':2})

    def test_candidate_isolation_and_entry(self):
        import json
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=build(root/'a'); b=build(root/'b')
            self.assertEqual(a,b)
            ref=json.loads((root/'a/reference.json').read_text())
            for row in a['candidates']:
                self.assertAlmostEqual(row['bonusEntryProbability'],.00856)
                cfg=json.loads((root/'a'/(row['name']+'.json')).read_text())
                mode='basegame' if row['name'].startswith('bonus-') else 'freegame'
                self.assertEqual(ref['reels'][mode],cfg['reels'][mode])
            self.assertAlmostEqual(trigger_probability(ref['reels']['basegame'],'S',3),.00856)
