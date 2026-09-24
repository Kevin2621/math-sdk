"""Build a 40/60 local comparison: near-100 entry, exact base-pay calibration."""
from pathlib import Path
from copy import deepcopy
from itertools import product
from math import prod
from random import Random
import json
from exact_base_return import calculate
from src.reels.generator import trigger_probability
from reel_source import ReelSource

if __name__=='__main__':
 root=Path('wild-pickins/reports/math/split4060-step4');root.mkdir(parents=True,exist_ok=False)
 old=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-entry75-bonus-wild5.json').read_text())
 # Start with original eight-scatter strips; add legal scatter positions only.
 base=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-high35-wild5-mix28-picks-off.json').read_text())
 best=min(product((8,9),repeat=5),key=lambda counts:abs(sum(prod((n*3/240 if bit else 1-n*3/240) for n,bit in zip(counts,bits)) for bits in product((0,1),repeat=5) if sum(bits)>=3)-.01))
 c=deepcopy(old)
 c['reels']['basegame']=deepcopy(base['reels']['basegame'])
 for r,(strip,n) in enumerate(zip(c['reels']['basegame'],best)):
  positions=[i for i,s in enumerate(strip) if s in ('C04','C05','C06','C07','C08')];Random(9190+r).shuffle(positions)
  for i in positions:
   if strip.count('S')==n:break
   if all(strip[(i+d)%240]!='S' for d in (-2,-1,1,2)):strip[i]='S'
  assert strip.count('S')==n
 ReelSource(c['reels']['basegame'])
 original=calculate(c)['baseReturn'];factor=.3868/original
 c['fixtureMath']['paytable']={s:{n:round(v*factor) for n,v in pays.items()} for s,pays in c['fixtureMath']['paytable'].items()}
 # Bonus strip variant: upgrade one low to a Wild on 0..5 reels, keeping 35% highs.
 six=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-mix28-bonus-high35-no-scatters.json').read_text())
 for count in range(6):
  v=deepcopy(c)
  for r in range(count):v['reels']['freegame'][r]=deepcopy(six['reels']['freegame'][r])
  v['mathVersion']=f'experimental-4060-entry100-bonusmix{count}';v['description']='40/60 target comparison; scaled base paytable; bonus table unchanged.'
  (root/f'candidate-{count}.json').write_text(json.dumps(v,indent=2)+'\n')
 p=trigger_probability(c['reels']['basegame'],'S',3)
 (root/'targets.json').write_text(json.dumps(dict(entryProbability=p,entryInterval=1/p,bonusMeanTarget=.5802/p,base=calculate(c),baseScale=factor),indent=2)+'\n')
