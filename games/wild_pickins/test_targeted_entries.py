import unittest
from itertools import product
from generate_targeted_entries import ConditionalEntry

class ConditionalTests(unittest.TestCase):
    def test_exact_support_and_uniform_tuple_probability(self):
        strips=[['S','C01','C02','C03']+['C04']*r for r in range(5)]
        for n in (4,5):
            sampler=ConditionalEntry(strips,n)
            valid=sum(sum(sum(s[(i+y)%len(s)]=='S' for y in range(3)) for s,i in zip(strips,stops))==n
                for stops in product(*(range(len(s)) for s in strips)))
            self.assertEqual(sampler.count,valid)
            # pattern mass = product of stop counts / total; uniform within pattern
            # gives exactly 1 / total to each valid tuple.
            for pattern,count in sampler.patterns:
                from fractions import Fraction
                probability=Fraction(count,sampler.count)
                for r,v in enumerate(pattern):probability/=len(sampler.stops[r][v])
                self.assertEqual(probability,Fraction(1,valid))
            for identity in range(30):
                sample=sampler.draw(9222,identity)
                self.assertEqual(sum(s=='S' for reel in sample.board for s in reel),n)
                self.assertEqual(sample,sampler.draw(9222,identity))
    def test_impossible_entry(self):
        with self.assertRaises(ValueError):ConditionalEntry([['C01']*4]*5,5)

if __name__=='__main__':unittest.main()
