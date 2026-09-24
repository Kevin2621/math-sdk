"""Controlled 35/40%-high and 5/6-Wild base comparisons against active control."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import subprocess
import sys
from exact_base_return import calculate
from reel_source import ReelSource


def variants(control):
    result={}
    for name,high,wild in [('control',24,4),('high35',28,4),('high40',32,4),('wild5',24,5),('wild6',24,6)]:
        c=deepcopy(control)
        for r,strip in enumerate(c['reels']['basegame']):
            original=strip.copy();positions=[i for i,s in enumerate(strip) if s in ('C04','C05','C06','C07','C08')]
            Random(9130+r).shuffle(positions)
            additions=['C01','C02','C03']*(high-24)+['W']*(wild-4)
            for i,s in zip(positions,additions):strip[i]=s
            counts=Counter(strip)
            assert len(strip)==240 and all(counts[s]==high for s in ('C01','C02','C03')) and counts['W']==wild
            assert [i for i,s in enumerate(strip) if s=='S']==[i for i,s in enumerate(original) if s=='S']
            if wild==4:assert [i for i,s in enumerate(strip) if s=='W']==[i for i,s in enumerate(original) if s=='W']
            if high==24:assert [(i,s) for i,s in enumerate(strip) if s in ('C01','C02','C03')]==[(i,s) for i,s in enumerate(original) if s in ('C01','C02','C03')]
        ReelSource(c['reels']['basegame'])
        assert c['reels']['freegame']==control['reels']['freegame']
        assert all(v[0]==0 for v in c['goldenRates'].values())
        c['description']='Controlled visibility comparison; not activated.'
        c['mathVersion']='experimental-visibility-'+name
        result[name]=c
    return result


if __name__=='__main__':
    root=Path('wild-pickins/reports/math/visibility-comparison-step4');root.mkdir(parents=True,exist_ok=False)
    control=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-high30-picks-off.json').read_text())
    for name,c in variants(control).items():
        path=root/(name+'-config.json');path.write_text(json.dumps(c,indent=2)+'\n')
        (root/(name+'-exact.json')).write_text(json.dumps(calculate(c),indent=2)+'\n')
        with (root/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,'math-sdk/games/wild_pickins/balance_multiplier_wilds.py','--config',str(path),'--seed','9131','--rounds','100000','--output',str(root/(name+'-sample.json'))],stdout=log,stderr=subprocess.STDOUT,check=True)
        print(name+' complete',flush=True)
