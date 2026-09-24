"""Regenerate bonus strips: 35% highs, zero scatters, six Wilds per 240."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from src.reels.generator import construct


def build(source):
    config=deepcopy(source)
    for reel in range(5):
        counts={f'C{i:02}':28 if i<=3 else 8 for i in range(1,9)}
        counts['W']=6
        remaining=240-sum(counts.values());heavy=round(remaining*.25)
        counts[f'C{reel+4:02}']+=heavy
        for i in range(remaining-heavy):counts[f'C{4+i%5:02}']+=1
        strip=construct(counts,seed=9160+reel,window_height=3,visible_limits={'S':0})
        assert len(strip)==240 and strip.count('W')==6 and 'S' not in strip
        assert all(strip.count(s)==28 for s in ('C01','C02','C03'))
        config['reels']['freegame'][reel]=strip
    assert config['reels']['basegame']==source['reels']['basegame']
    config['mathVersion']='experimental-mix28-bonus-high35-no-scatters'
    config['description']='Generated bonus strips: 35% highs, 0% scatters, 6/240 Wilds; unchanged base. Golden Picks off.'
    return config

if __name__=='__main__':
    root=Path(__file__).parent/'experiments'
    source=json.loads((root/'wp25-high35-wild5-mix28-picks-off.json').read_text())
    (root/'wp25-mix28-bonus-high35-no-scatters.json').write_text(json.dumps(build(source),indent=2)+'\n')
