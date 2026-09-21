"""Pool equal-weight experiments of one config and report payout/session-shape diagnostics."""
import argparse
import csv
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, stdev
from coverage_books import read_books
from evaluate_experimental import summarize as reconcile


def summarize(runs):
    configs=[json.loads((r/'experiment-config.json').read_text()) for r in runs]
    if any(c!=configs[0] for c in configs):
        raise ValueError('Cannot pool different configurations')
    payouts=[];bonus_pays=[];durations=[];base=[];bands=Counter();harvest=0
    for run in runs:
        with (run/'lookUpTable_base.csv').open() as lookup:
            reconcile(read_books(run/'books_base.jsonl.zst'),csv.reader(lookup))
        for b in read_books(run/'books_base.jsonl.zst'):
            payout=b['payoutMultiplier']/100
            payouts.append(payout)
            results=[e for e in b['events'] if e['type']=='wildPickinsSpinResult']
            base.append(results[0]['lineWin']/100)
            if len(results)>1:
                bonus_pays.append(results[-1]['bonusTotal']/100)
                durations.append(len(results)-1)
            harvest+=any(e['endReason']=='fullHarvest' for e in results)
            band=('zero' if payout==0 else 'under1x' if payout<1 else '1to5x' if payout<5 else
                  '5to20x' if payout<20 else '20to100x' if payout<100 else '100to1000x' if payout<1000 else '1000xPlus')
            bands[band]+=1
    n=len(payouts)
    def quantiles(values):
        ordered=sorted(values)
        return {str(q):ordered[max(0,math.ceil(q*len(ordered))-1)] for q in (.5,.9,.95,.99)} if ordered else {}
    # Wilson 95% interval for an iid Bernoulli Full Harvest indicator.
    z=1.959963984540054;p=harvest/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return dict(experimentalOnly=True,runs=[str(r) for r in runs],
        configSha256=hashlib.sha256(json.dumps(configs[0],sort_keys=True).encode()).hexdigest(),
        rounds=n,observedReturn=mean(payouts),sampleStdDev=stdev(payouts),
        meanStandardError=stdev(payouts)/math.sqrt(n),
        positiveRate=sum(v>0 for v in payouts)/n,profitRate=sum(v>1 for v in payouts)/n,
        baseSpinProfitRate=sum(v>1 for v in base)/n,baseSpinMean=mean(base),
        bonusRate=len(bonus_pays)/n,bonusPayoutQuantiles=quantiles(bonus_pays),
        meanBonusPayout=mean(bonus_pays) if bonus_pays else None,
        meanBonusDuration=mean(durations) if durations else None,
        payoutQuantiles=quantiles(payouts),payoutBandCounts=dict(bands),fullHarvests=harvest,
        fullHarvestProbabilityWilson95=[max(0,center-radius),min(1,center+radius)],
        caution='Empirical same-config iid-round samples. Standard error can miss an unsampled tail; '
                'Wilson interval concerns Harvest frequency, not RTP. No final weights or medium-volatility classification.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=summarize(a.runs)
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))
