import unittest
from types import SimpleNamespace
from line_model import LineAward
from payline_metrics import PaylineMetrics

class PaylineMetricsTests(unittest.TestCase):
    def test_attribution_and_clipping(self):
        m=PaylineMetrics([[0]*5,[1]*5])
        board=[['C01']*3 for _ in range(5)];board[1][0]='W'
        a=LineAward(1,'C01',3,300,((0,0),(1,0),(2,0)),3,100)
        b=LineAward(2,'C01',3,100,((0,1),(1,1),(2,1)),1,100)
        m.spin(dict(gameType='freegame',lines=SimpleNamespace(awards=[a,b]),finalBoard=board,wildMultipliers={(1,0):3},lineWin=250))
        r=m.report(2)
        self.assertEqual(r['settlement']['freegame'],dict(nominalBookAmount=400,settledBookAmount=250,clippedBookAmount=150))
        self.assertEqual(sum(x['nominalReturnContribution'] for x in r['byPayline']),2)
        self.assertEqual(r['bySymbolAndLength'][0]['hits'],2)
        self.assertEqual(r['detail'][0]['wildPositionsAndValues'],[[1,0,3]])
        self.assertEqual(r['detail'][0]['matchedSymbols'],['C01','W','C01'])
        self.assertEqual(r['detail'][0]['hitsPerModeSpin'],1)

    def test_empty(self):
        self.assertEqual(PaylineMetrics([[0]*5]).report(0)['detail'],[])

    def test_exclusive_spin_categories(self):
        m=PaylineMetrics([[0]*5,[1]*5]);board=[['C01']*3 for _ in range(5)]
        low=LineAward(1,'C04',3,20,((0,0),(1,0),(2,0)),1,20)
        high=LineAward(2,'C01',3,100,((0,1),(1,1),(2,1)),1,100)
        for awards in ([],[low],[high],[low,high]):
            m.spin(dict(gameType='basegame',lines=SimpleNamespace(awards=awards),finalBoard=board,lineWin=sum(a.amount for a in awards)))
        cats=m.report(4)['spinCategories']['basegame']
        self.assertEqual(sum(v['count'] for v in cats.values()),4)
        self.assertTrue(all(v['rate']==.25 for v in cats.values()))
