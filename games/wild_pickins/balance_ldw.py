"""Experimental shared-paytable and bonus-growth comparison; no payout filtering."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from statistics import mean
from coverage_books import read_books
HERE=Path(__file__).resolve().parent

def candidates(source,densities=(36,72),tables=('quarter','tiered','strong')):
    for table,top in [('quarter',[25,25]),('tiered',[60,40]),('strong',[100,50])]:
        if table not in tables:continue
        for density in densities:
            c=copy.deepcopy(source)
            c['description']=f'LDW experiment {table}-w{density}: shared pays, no payout filtering; experimental only.'
            c['mathVersion']='experimental-ldw-1'
            for i,(crop,pay) in enumerate(c['fixtureMath']['paytable'].items()):
                pay['3']=top[i] if i<2 else 25
                pay['4']=max(50,pay['4'],pay['3'])
                pay['5']=max(100,pay['5'],pay['4'])
            if density==54:
                c['reels']['freegame']=[strip+strip+['C08' if s=='W' else s for s in strip] for strip in c['reels']['freegame']]
            if density==72:
                c['reels']['freegame']=[strip+['C08' if s=='W' else s for s in strip] for strip in c['reels']['freegame']]
            yield f'{table}-w{density}',c

def metrics(run):
    values=[];bonuses=[];bonus_ids=[];streak=longest=triples=0;below_quarter=0
    for b in read_books(run/'books_base.jsonl.zst'):
        results=[e for e in b['events'] if e['type']=='wildPickinsSpinResult']
        value=results[0]['lineWin']/100;values.append(value)
        ldw=0<value<1;streak=streak+1 if ldw else 0;longest=max(longest,streak);triples+=streak>=3
        below_quarter+=0<value<.25
        if len(results)>1:bonuses.append(results[-1]['bonusTotal']/100);bonus_ids.append(len(values)-1)
    def quantile(xs,p):
        import math
        return sorted(xs)[max(0,math.ceil(p*len(xs))-1)] if xs else None
    gaps=[b-a for a,b in zip(bonus_ids,bonus_ids[1:])]
    n=len(values);positive=sum(x>0 for x in values)
    return dict(baseReturn=mean(values),basePositiveRate=positive/n,
        baseLdwRate=sum(0<x<1 for x in values)/n,
        ldwAmongPaying=sum(0<x<1 for x in values)/positive if positive else None,
        baseProfitRate=sum(x>1 for x in values)/n,baseBreakEvenRate=sum(x==1 for x in values)/n,
        minimumPositiveBase=min((x for x in values if x>0),default=None),belowQuarterCount=below_quarter,
        longestLdwStreak=longest,overlappingThreeLdwWindows=triples,
        threeLdwWindowRate=triples/max(1,n-2),bonusMedian=quantile(bonuses,.5),bonusMean=mean(bonuses) if bonuses else None,
        completeBonusGaps=len(gaps),bonusGapMedian=quantile(gaps,.5),bonusGapP95=quantile(gaps,.95),
        note='LDW denominator is all base spins. Gaps omit censored start/end waits. Triples are overlapping windows within each seed.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds',type=int,default=10000);p.add_argument('--seeds',type=int,nargs='+',default=[52,53])
    p.add_argument('--densities',type=int,nargs='+',choices=[36,54,72],default=[36,72])
    p.add_argument('--tables',nargs='+',choices=['quarter','tiered','strong'],default=['quarter','tiered','strong'])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    source=json.loads((HERE/'experiments/wp25-base-crop-focus.json').read_text());configs=list(candidates(source,a.densities,a.tables));rows=[]
    for name,c in configs:(a.output/f'{name}.json').write_text(json.dumps(c,indent=2)+'\n')
    for seed in a.seeds:
        for name,c in configs:
            run=a.output/f'{name}-seed{seed}'
            with (a.output/f'{name}-seed{seed}.log').open('w') as log:
                subprocess.run([sys.executable,str(HERE/'generate_experimental.py'),'--config',str(a.output/f'{name}.json'),
                    '--rounds',str(a.rounds),'--seed',str(seed),'--output',str(run)],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(HERE/'evaluate_experimental.py'),str(run)],stdout=log,stderr=subprocess.STDOUT,check=True)
            row=dict(candidate=name,**json.loads((run/'evaluation.json').read_text()),ldw=metrics(run));rows.append(row)
            (a.output/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(f"{name} seed {seed}: RTP {row['observedReturn']*100:.3f}%, LDW {row['ldw']['baseLdwRate']*100:.2f}%, base profit {row['ldw']['baseProfitRate']*100:.2f}%",flush=True)
if __name__=='__main__':main()
