"""Paired rule-core investigation; no production config or published books changed."""
import argparse,copy,json,math
from pathlib import Path
from random import Random
from fractions import Fraction
from statistics import mean
from round_model import RoundModel
from reel_source import ReelSource
from line_model import evaluate_lines
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'wild-pickins/tools'))
from contract import line_awards
HERE=Path(__file__).resolve().parent

def variants(source):
    old=json.loads((HERE/'experiments/wp25-base-crop-focus.json').read_text())
    for name in ('control','wild36','golden10','scatter_half','wild36_golden10'):
        c=copy.deepcopy(source)
        if name in ('wild36','wild36_golden10'):c['reels']['freegame']=old['reels']['freegame']
        if name in ('golden10','wild36_golden10'):c['goldenRates']['freegame']=[1,10]
        if name=='scatter_half':c['reels']['freegame']=[s+['C08' if v=='S' else v for v in s] for s in c['reels']['freegame']]
        yield name,c

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--rounds',type=int,default=30000);p.add_argument('--seeds',type=int,nargs='+',default=[56,57]);a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=False)
 source=json.loads((HERE/'experiments/wp25-ldw-quarter-w54.json').read_text());configs=dict(variants(source))
 (a.output/'configs.json').write_text(json.dumps(configs,indent=2)+'\n')
 paths=dict(enumerate(source['fixtureMath']['paths'],1));pays={(c,int(n)):v for c,vs in source['fixtureMath']['paytable'].items() for n,v in vs.items()}
 reduced={k:v*3//5 for k,v in pays.items()};assert all(v*3%5==0 for v in pays.values())
 base_source=ReelSource(source['reels']['basegame']);reels={n:ReelSource(c['reels']['freegame']) for n,c in configs.items()}
 records={n:[] for n in configs};base_total=entries=0
 for seed in a.seeds:
  for identity in range(a.rounds):
   rng=Random(f'bonus-review-base:{seed}:{identity}')
   model=RoundModel(paths,pays,500000,30,Fraction(1,10),Fraction(1,20),rng)
   base=model.spin(base_source.draw(rng).board);base_total+=base['lineWin']
   if model.ended:continue
   entries+=1
   for name,c in configs.items():
    m=copy.deepcopy(model);m.bonus_golden=Fraction(*c['goldenRates']['freegame']);m.rng=Random(f'bonus-review-feature:{seed}:{identity}')
    spins=growth=scatter_spins=dead_scatter=retrigger=denied=collision=pick=0;first=None;reduced_sum=0;harvest=False
    while not m.ended:
     r=m.spin(reels[name].draw(m.rng).board);spins+=1
     raw=sum(w[1] for w in line_awards(r['finalBoard'],source['fixtureMath']['paths'],source['fixtureMath']['paytable']))
     assert r['lineWin']==min(raw,500000-(r['roundTotal']-r['spinWin']))
     new=len(r['stickyAfter'])-len(r['stickyBefore']);growth+=new>0
     if new and first is None:first=spins
     scatter=len(r['scatterPositions']);scatter_spins+=scatter>0;dead_scatter+=0<scatter<3
     retrigger+=r['nominalRetriggerAward']>0
     denied+=r['nominalRetriggerAward']>0 and r['grantedExtraSpins']==0
     collision+=r['nominalCollisionAward']>0;pick+=r['goldenTarget'] is not None
     reduced_sum+=evaluate_lines(r['finalBoard'],paths,reduced).total
     harvest|=r['endReason']=='fullHarvest'
    # Reduced-only line pays cannot alter stopping: the line-only bound is below cap.
    # Full Harvest still brings the entire paid round to cap, regardless of line scale.
    scaled_bonus=500000-base['lineWin'] if harvest else reduced_sum
    records[name].append(dict(seed=seed,id=identity,payout=m.bonus_total/100,scaledPayout=scaled_bonus/100,spins=spins,growthSpins=growth,finalSticky=len(r['stickyAfter']),firstWild=first,scatterSpins=scatter_spins,deadScatterSpins=dead_scatter,retriggerSpins=retrigger,deniedRetriggerSpins=denied,collisionSpins=collision,picks=pick,harvest=harvest))
  print(f'Finished seed {seed}: {entries} common bonus entries',flush=True)
 n=a.rounds*len(a.seeds);summaries=[]
 def q(v,p):return sorted(v)[max(0,math.ceil(len(v)*p)-1)] if v else None
 for name,rs in records.items():
  totalspins=sum(r['spins'] for r in rs);values=[r['payout'] for r in rs];scaled=[r['scaledPayout'] for r in rs]
  summary=dict(candidate=name,paidRounds=n,bonuses=entries,baseRtp=base_total/(100*n),observedRtp=base_total/(100*n)+sum(values)/n,bonusMean=mean(values),bonusMedian=q(values,.5),bonusP90=q(values,.9),bonusUnder5Rate=sum(v<5 for v in values)/entries,bonus20PlusRate=sum(v>=20 for v in values)/entries,meanSpins=mean(r['spins'] for r in rs),meanFinalSticky=mean(r['finalSticky'] for r in rs),growthSpinRate=sum(r['growthSpins'] for r in rs)/totalspins,firstWildMedian=q([r['firstWild'] for r in rs if r['firstWild']],.5),noGrowthBonusRate=sum(r['firstWild'] is None for r in rs)/entries,anyPickBonusRate=sum(r['picks']>0 for r in rs)/entries,meanPicks=mean(r['picks'] for r in rs),scatterSpinRate=sum(r['scatterSpins'] for r in rs)/totalspins,oneOrTwoScatterSpinRate=sum(r['deadScatterSpins'] for r in rs)/totalspins,retriggerSpins=sum(r['retriggerSpins'] for r in rs),deniedRetriggerSpins=sum(r['deniedRetriggerSpins'] for r in rs),collisionSpinRate=sum(r['collisionSpins'] for r in rs)/totalspins,harvests=sum(r['harvest'] for r in rs),bonus60PercentPays=dict(observedRtp=base_total/(100*n)+sum(scaled)/n,mean=mean(scaled),median=q(scaled,.5),under5Rate=sum(v<5 for v in scaled)/entries),bySeed={str(seed):dict(bonuses=sum(r['seed']==seed for r in rs),bonusMean=mean(r['payout'] for r in rs if r['seed']==seed)) for seed in a.seeds})
  summaries.append(summary)
  (a.output/f'{name}-bonus-records.json').write_text(json.dumps(rs)+'\n')
 (a.output/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
