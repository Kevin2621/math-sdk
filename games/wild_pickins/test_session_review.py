from pathlib import Path
import tempfile
import unittest
from session_review import review_sessions

class SessionReviewTests(unittest.TestCase):
    def test_zero_weight_outcomes_are_never_sampled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lookup.csv';path.write_text('0,0,500000\n1,3,0\n')
            r=review_sessions(path,{0},sessions=10,spins=20)
            self.assertEqual(r['medianNetX'],-20)
            self.assertEqual(r['noBonusSessionRate'],1)
            self.assertEqual(r['medianLongestZeroReturnRun'],20)
            path.write_text('0,3,200\n1,0,0\n')
            r=review_sessions(path,{0},sessions=10,spins=20)
            self.assertEqual(r['medianNetX'],20)
            self.assertEqual(r['noBonusSessionRate'],0)
            self.assertEqual(r['medianLongestZeroReturnRun'],0)
