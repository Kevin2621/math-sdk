import hashlib
from pathlib import Path
import tempfile
import unittest
from weighted_playtest import WeightedTable
from serve_local import round_response

class WeightedPlaytestTests(unittest.TestCase):
    def test_integer_boundaries_and_zero_weights(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lut.csv';p.write_text('0,0,500\n1,3,25\n2,1,200\n')
            t=WeightedTable(p,hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual([t.at(i) for i in range(4)],[(1,25)]*3+[(2,200)])
            self.assertEqual(t.sample(1,2,'reference'),t.sample(1,2,'reference'))
            with self.assertRaises(ValueError):WeightedTable(p,'bad')
    def test_actual_profiles_reproduce_source_payout_and_identity(self):
        for profile in ('reference','quieter-base'):
            r=round_response(61,0,profile)
            self.assertEqual(r,round_response(61,0,profile))
            self.assertEqual(r['profile'],profile)
            self.assertIsInstance(r['sourceBookId'],int)
            self.assertIsNotNone(r['lookupSha256'])
        with self.assertRaises(ValueError):round_response(61,0,'unknown')
