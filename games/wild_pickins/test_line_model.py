import unittest
from line_model import CROPS, evaluate_lines

class LineModelTests(unittest.TestCase):
    def setUp(self):
        self.pay={(c,n):0 for c in CROPS for n in (3,4,5)}
        self.pay.update({('C01',3):12,('C01',4):8,('C01',5):20,('C02',3):30})
    def board(self,seq): return [[s,'S','S'] for s in seq]
    def run_line(self,seq): return evaluate_lines(self.board(seq),{1:[0]*5},self.pay)
    def test_shorter_match_can_pay_more(self):
        self.assertEqual(self.run_line(['C01']*4+['C03']).total,12)
    def test_wild_prefix_selects_highest_eligible_crop(self):
        result=self.run_line(['W','W','W','C01','C01'])
        self.assertEqual((result.total,result.awards[0].crop,result.awards[0].count),(30,'C02',3))
    def test_all_wilds_pay_once(self): self.assertEqual(self.run_line(['W']*5).total,30)
    def test_scatter_breaks_line(self): self.assertEqual(self.run_line(['C01','W','S','C01','C01']).total,0)
    def test_cannot_start_on_second_reel(self): self.assertEqual(self.run_line(['C03']+['C01']*4).total,0)
    def test_distinct_lines_add(self):
        board=[['C01','C01','S'] for _ in range(5)]
        result=evaluate_lines(board,{1:[0]*5,2:[1]*5},self.pay)
        self.assertEqual(result.total,40)
    def test_duplicate_paths_rejected(self):
        with self.assertRaises(ValueError): evaluate_lines(self.board(['W']*5),{1:[0]*5,2:[0]*5},self.pay)
    def test_fractional_money_rejected(self):
        self.pay['C01',3]=0.5
        with self.assertRaises(ValueError): self.run_line(['C01']*5)

if __name__=='__main__': unittest.main()
