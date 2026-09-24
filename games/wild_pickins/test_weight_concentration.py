import unittest
from inspect_weight_concentration import distribution

class ConcentrationTests(unittest.TestCase):
    def test_equal_and_concentrated_weights(self):
        rows=[dict(id=i) for i in range(4)]
        equal=distribution(rows,{i:1 for i in range(4)})
        self.assertEqual(equal['effectiveBooks'],4)
        self.assertEqual(equal['pairRepeatProbability'],.25)
        concentrated=distribution(rows,{0:3,1:1,2:0,3:0})
        self.assertEqual(concentrated['effectiveBooks'],1.6)
        self.assertEqual(concentrated['largestProbability'],.75)
        self.assertEqual(concentrated['positiveWeightBooks'],2)
        self.assertIsNone(distribution(rows,{i:0 for i in range(4)})['effectiveBooks'])

if __name__=='__main__':unittest.main()
