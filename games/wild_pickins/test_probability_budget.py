import unittest
from probe_probability_budget import tilt
from generate_entry_coverage import ConditionalEntry

class BudgetTests(unittest.TestCase):
    def test_group_masses_and_requested_return(self):
        groups={'a':[dict(id=0,bonus=0),dict(id=1,bonus=100)],
                'b':[dict(id=2,bonus=100),dict(id=3,bonus=300)]}
        weights,check=tilt(groups,{'a':.6,'b':.4},'bonus',1.2)
        self.assertAlmostEqual(weights[0]+weights[1],.6)
        self.assertAlmostEqual(weights[2]+weights[3],.4)
        self.assertAlmostEqual(check['actual'],1.2)
        self.assertTrue(all(w>0 for w in weights.values()))
        with self.assertRaises(ValueError):tilt(groups,{'a':.6,'b':.4},'bonus',2)
    def test_three_scatter_sampler(self):
        sampler=ConditionalEntry([['S','C01','C02','C03','C04']]*5,3)
        for i in range(20):
            sample=sampler.draw(9224,i)
            self.assertEqual(sum(s=='S' for reel in sample.board for s in reel),3)

if __name__=='__main__':unittest.main()
