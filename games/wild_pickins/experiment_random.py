"""Indexed random inputs for local experiments; no shared consumption state."""
import json
from random import Random

SCHEME='wp-indexed-v1'

class ExperimentRandom:
    def __init__(self,seed,round_id):
        if type(seed) is not int or type(round_id) is not int or seed<0 or round_id<0:
            raise ValueError('Nonnegative integer seed and round ID required')
        self.seed=seed;self.round_id=round_id

    def stream(self,mode,spin,purpose,reel=None):
        key=json.dumps([SCHEME,self.seed,self.round_id,mode,spin,purpose,reel],separators=(',',':'))
        return Random(key)

    def weighted_value(self,weights,mode,spin,reel):
        if len(weights)!=3 or any(type(w) is not int or w<0 for w in weights) or not sum(weights):
            raise ValueError('Three nonnegative integer weights with positive total required')
        # One common binary uniform quantile across candidate distributions.
        # Refine its interval if it straddles a weight boundary. Integer-only
        # thresholds also make proportionally scaled weights equivalent.
        rng=self.stream(mode,spin,'wild-value',reel)
        numerator=0;denominator=1;total=sum(weights)
        while True:
            numerator=(numerator<<64)|rng.getrandbits(64);denominator<<=64
            lo=numerator*total//denominator
            hi=((numerator+1)*total-1)//denominator
            cumulative=0
            for value,weight in enumerate(weights,1):
                previous=cumulative;cumulative+=weight
                if previous<=lo and hi<cumulative:return value
