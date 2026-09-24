import unittest
from collections import Counter
from experiment_hit25 import arrange
from test_balance_metrics import CONFIG,event
from balance_metrics import BalanceMetrics

class Hit25Tests(unittest.TestCase):
    def test_preserved_counts_specials_and_repeatability(self):
        source=['C01']*20+['S']+['C02']*20+['W']+['C03']*20
        out=arrange(source,4,500)
        self.assertEqual(out,arrange(source,4,500));self.assertEqual(Counter(out),Counter(source))
        self.assertEqual(out[20],'S');self.assertEqual(out[41],'W')
        score=lambda s:sum(s[i]==s[(i+d)%len(s)] for i in range(len(s)) for d in (1,2))
        self.assertLessEqual(score(out),score(source))
    def test_gaps(self):
        m=BalanceMetrics(CONFIG)
        for value in (0,0,20,0,200,0):
            m.begin_round();m.spin(event('basegame',value,value));m.end_round()
        r=m.report()['baseStreaks']
        self.assertEqual(r['zeroPayout']['completedGaps']['histogram'],[{'value':1,'count':1},{'value':2,'count':1}])
        self.assertEqual(r['noProfit']['completedGaps']['histogram'],[{'value':4,'count':1}])
        self.assertEqual(r['noProfit']['trailingCensoredGap'],1)
