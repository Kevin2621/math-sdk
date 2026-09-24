"""Build requested combined candidate; deterministic one-low replacement per reel."""
import json
from pathlib import Path
from copy import deepcopy
from random import Random
from collections import Counter
from exact_base_return import calculate
from reel_source import ReelSource

if __name__=='__main__':
    root=Path('wild-pickins/reports/math/high35-wild5-step4');root.mkdir(parents=True,exist_ok=False)
    source=Path('wild-pickins/reports/math/visibility-comparison-step4/high35-config.json')
    c=json.loads(source.read_text());before=deepcopy(c)
    for r,strip in enumerate(c['reels']['basegame']):
        positions=[i for i,s in enumerate(strip) if s in ('C04','C05','C06','C07','C08')]
        i=Random(9140+r).choice(positions);strip[i]='W'
        assert sum(a!=b for a,b in zip(strip,before['reels']['basegame'][r]))==1
        assert Counter(strip)['W']==5
        assert all(Counter(strip)[s]==28 for s in ('C01','C02','C03'))
    assert c['reels']['freegame']==before['reels']['freegame']
    ReelSource(c['reels']['basegame'])
    c['mathVersion']='experimental-high35-wild5';c['description']='35% highs plus fifth base Wild; not activated.'
    (root/'config.json').write_text(json.dumps(c,indent=2)+'\n')
    (root/'exact.json').write_text(json.dumps(calculate(c),indent=2)+'\n')
