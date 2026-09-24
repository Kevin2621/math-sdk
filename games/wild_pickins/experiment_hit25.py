"""Count-preserving base-spacing candidates, fixed scatter and Wild positions."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from random import Random
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from exact_base_return import calculate


def arrange(original, seed, steps):
    strip=original.copy();rng=Random(seed);movable=[i for i,s in enumerate(strip) if s not in ('W','S')]
    def score(edges):return sum(strip[i]==strip[(i+d)%len(strip)] for i,d in edges)
    for _ in range(steps):
        a,b=rng.sample(movable,2)
        edges={(i,d) for p in (a,b) for d in (1,2) for i in (p,(p-d)%len(strip))}
        before=score(edges);strip[a],strip[b]=strip[b],strip[a]
        if score(edges)>before:strip[a],strip[b]=strip[b],strip[a]
    assert Counter(strip)==Counter(original)
    assert [(i,s) for i,s in enumerate(strip) if s in ('W','S')]==[(i,s) for i,s in enumerate(original) if s in ('W','S')]
    return strip

if __name__=='__main__':
    root=Path('wild-pickins/reports/math/hit25-step4');root.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-split4060-entry100.json').read_text())
    expectation=calculate(source)['baseReturnFraction'];names=[]
    for steps in (0,100,500,2000,10000):
        name=f'spacing-{steps}';names.append(name);c=deepcopy(source)
        c['reels']['basegame']=[arrange(s,9200+r,steps) for r,s in enumerate(source['reels']['basegame'])]
        assert c['reels']['freegame']==source['reels']['freegame']
        assert calculate(c)['baseReturnFraction']==expectation
        c['mathVersion']='experimental-hit25-'+name;c['description']='Fixed-count spacing screen; not activated.'
        (root/(name+'-config.json')).write_text(json.dumps(c,indent=2)+'\n')
    def run(name):
        with (root/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,'math-sdk/games/wild_pickins/balance_multiplier_wilds.py','--config',str(root/(name+'-config.json')),'--seed','9201','--rounds','30000','--output',str(root/(name+'-sample.json'))],stdout=log,stderr=subprocess.STDOUT,check=True)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,names))
