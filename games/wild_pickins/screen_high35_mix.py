"""Preserve visible high/Wild density while varying per-reel high identities."""
import json
from pathlib import Path
from copy import deepcopy
from random import Random
from collections import Counter
from exact_base_return import calculate

if __name__=='__main__':
    root=Path('wild-pickins/reports/math/high35-wild5-step4');base=json.loads((root/'config.json').read_text());rows=[]
    for shift in range(0,41,2):
        c=deepcopy(base)
        for r,strip in enumerate(c['reels']['basegame']):
            positions=[i for i,s in enumerate(strip) if s in ('C01','C02','C03')]
            Random(9145+r).shuffle(positions)
            values=[]
            for k in range(3):values += [f'C{k+1:02}']*(28+shift if k==r%3 else 28-shift//2)
            for i,s in zip(positions,values):strip[i]=s
            assert len(positions)==84 and Counter(strip)['W']==5
        c['mathVersion']=f'experimental-high35-wild5-mix-{shift}'
        exact=calculate(c)
        rows.append(dict(shift=shift,baseReturn=exact['baseReturn']))
        (root/f'mix-{shift}-config.json').write_text(json.dumps(c,indent=2)+'\n')
        (root/f'mix-{shift}-exact.json').write_text(json.dumps(exact,indent=2)+'\n')
    (root/'mix-screen.json').write_text(json.dumps(rows,indent=2)+'\n')
    best=min(rows,key=lambda r:abs(r['baseReturn']-.2901))
    (root/'best-mix.json').write_text(json.dumps(best)+'\n');print(best)
