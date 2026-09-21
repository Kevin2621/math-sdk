"""Controlled base experiments with fixed 25-line pays and bonus inputs."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from coverage_books import read_books
from statistics import mean

HERE=Path(__file__).resolve().parent

def candidates(baseline):
    for name in ('control','golden20','crop_focus'):
        c=copy.deepcopy(baseline)
        c['description']=f'Experimental base comparison: {name}; no production selection.'
        c['mathVersion']='experimental-base-1'
        if name=='golden20':c['goldenRates']['basegame']=[1,5]
        if name=='crop_focus':
            # 16 crop stops: 3 each of C01/C02, 2 each C03-C06, 1 each C07/C08.
            # Preserve reel lengths and all Wild/scatter positions exactly.
            crops=['C01','C02','C03','C01','C04','C02','C05','C06',
                   'C01','C03','C02','C04','C05','C06','C07','C08']
            for strip in c['reels']['basegame']:
                values=iter(crops)
                for i,symbol in enumerate(strip):
                    if symbol.startswith('C'):strip[i]=next(values)
        yield name,c

def base_metrics(run):
    payouts=[];picks=0;paying_picks=0;visible=set();longest_zero=streak=0
    for book in read_books(run/'books_base.jsonl.zst'):
        result=next(e for e in book['events'] if e['type']=='wildPickinsSpinResult')
        amount=result['lineWin']/100;payouts.append(amount)
        pick=any(e['type']=='goldenCropPick' and e['spinId']==0 for e in book['events'])
        picks+=pick;paying_picks+=pick and amount>0
        visible.add(json.dumps(result['finalBoard'],separators=(',',':')))
        streak=streak+1 if amount==0 else 0;longest_zero=max(longest_zero,streak)
    n=len(payouts)
    return dict(baseReturn=mean(payouts),basePositiveRate=sum(v>0 for v in payouts)/n,
        baseProfitRate=sum(v>1 for v in payouts)/n,baseUnderStakeRate=sum(0<v<1 for v in payouts)/n,
        basePickRate=picks/n,basePickWithLinePayRate=paying_picks/n,
        distinctFinalBaseBoards=len(visible),longestObservedZeroBaseRun=longest_zero,
        note='Pick/pay label is co-occurrence, not causal uplift. Zero-base streak excludes bonus awards; observed sequence only.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--rounds',type=int,default=20000)
    p.add_argument('--seeds',type=int,nargs='+',default=[50,51])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((HERE/'experiments/wp25-golden05.json').read_text())
    configs=list(candidates(baseline));rows=[]
    for name,c in configs:(a.output/f'{name}.json').write_text(json.dumps(c,indent=2)+'\n')
    for seed in a.seeds:
        for name,c in configs:
            run=a.output/f'{name}-seed{seed}'
            with (a.output/f'{name}-seed{seed}.log').open('w') as log:
                subprocess.run([sys.executable,str(HERE/'generate_experimental.py'),'--config',str(a.output/f'{name}.json'),
                    '--rounds',str(a.rounds),'--seed',str(seed),'--output',str(run)],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(HERE/'evaluate_experimental.py'),str(run)],stdout=log,stderr=subprocess.STDOUT,check=True)
            row=dict(candidate=name,**json.loads((run/'evaluation.json').read_text()),baseMetrics=base_metrics(run))
            rows.append(row);(a.output/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(f"{name} seed {seed}: return {row['observedReturn']*100:.4f}%, base {row['baseMetrics']['baseReturn']*100:.4f}%, base profit {row['baseMetrics']['baseProfitRate']*100:.3f}%",flush=True)

if __name__=='__main__':main()
