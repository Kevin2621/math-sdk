"""Separate entry-frequency and bonus-Wild comparison candidates."""
from copy import deepcopy
from itertools import product
from random import Random
import json
from pathlib import Path
from src.reels.generator import trigger_probability
from reel_source import ReelSource
from exact_base_return import calculate


def build(source):
    best=None
    for counts in product((9,10),repeat=5):
        ps=[n*3/240 for n in counts]
        probability=sum(__import__('math').prod(p if bit else 1-p for p,bit in zip(ps,bits)) for bits in product((0,1),repeat=5) if sum(bits)>=3)
        key=(abs(probability-1/75),counts)
        if best is None or key<best[0]:best=(key,counts)
    base=deepcopy(source)
    for r,(strip,count) in enumerate(zip(base['reels']['basegame'],best[1])):
        positions=[i for i,s in enumerate(strip) if s in ('C04','C05','C06','C07','C08')];Random(9170+r).shuffle(positions)
        for i in positions:
            if strip.count('S')==count:break
            if all(strip[(i+d)%240]!='S' for d in (-2,-1,1,2)):strip[i]='S'
        assert strip.count('S')==count
    ReelSource(base['reels']['basegame'])
    results={}
    for wilds in (4,5,6):
        c=deepcopy(base)
        for r,strip in enumerate(c['reels']['freegame']):
            positions=[i for i,s in enumerate(strip) if s=='W'];Random(9180+r).shuffle(positions)
            for j,i in enumerate(positions[:6-wilds]):strip[i]=f'C{4+(r+j)%5:02}'
            assert strip.count('W')==wilds and 'S' not in strip
            assert all(strip.count(s)==28 for s in ('C01','C02','C03'))
        c['mathVersion']=f'experimental-entry75-bonus-wild{wilds}';c['description']='Near-75 entry and bonus Wild-density comparison; not activated.'
        results[str(wilds)]=c
    return results

if __name__=='__main__':
    root=Path('wild-pickins/reports/math/bonus75-step4');root.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-mix28-bonus-high35-no-scatters.json').read_text())
    variants=build(source)
    for name,c in variants.items():(root/f'wild{name}-config.json').write_text(json.dumps(c,indent=2)+'\n')
    p=trigger_probability(variants['6']['reels']['basegame'],'S',3)
    (root/'entry-and-base.json').write_text(json.dumps(dict(entryProbability=p,meanInterval=1/p,requiredBonusMeanForTarget=.6769/p,base=calculate(variants['6'])),indent=2)+'\n')
