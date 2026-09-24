"""Uniform independent reel-stop sampling from explicitly supplied cyclic strips."""
from dataclasses import dataclass
from line_model import CROPS

@dataclass(frozen=True)
class ReelSample:
    board: list
    stops: tuple
    top: tuple
    bottom: tuple

class ReelSource:
    def __init__(self,strips):
        if len(strips)!=5: raise ValueError('Five reel strips required')
        self.strips=tuple(tuple(s) for s in strips)
        for strip in self.strips:
            if len(strip)<3 or any(s not in (*CROPS,'W','S') for s in strip): raise ValueError('Invalid strip')
            for stop in range(len(strip)):
                if sum(strip[(stop+y)%len(strip)]=='S' for y in range(3))>1:
                    raise ValueError('Strip allows multiple visible scatters, including wraparound')
    def draw(self,rng,*,experiment_random=None,mode=None,spin_index=None):
        stops=tuple((rng if experiment_random is None else experiment_random.stream(mode,spin_index,'reel-stop',r)).randrange(len(strip)) for r,strip in enumerate(self.strips))
        return ReelSample(
            [[strip[(stop+y)%len(strip)] for y in range(3)] for strip,stop in zip(self.strips,stops)],
            stops,tuple(strip[(stop-1)%len(strip)] for strip,stop in zip(self.strips,stops)),
            tuple(strip[(stop+3)%len(strip)] for strip,stop in zip(self.strips,stops)))
