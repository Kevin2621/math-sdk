"""Seeded fixed-length independent-book session diagnostics (no wallet/bankroll model)."""
from array import array
from bisect import bisect_right
import csv
from random import Random

def review_sessions(lookup, bonus_ids, sessions=10000, spins=100, seed=6100):
    cumulative=array('Q'); amounts=array('I'); bonus=array('B');total=0
    with lookup.open() as f:
        for row in csv.reader(f):
            identity,weight,amount=map(int,row)
            if weight<0 or amount<0:raise ValueError('Negative weight/payout')
            total+=weight;cumulative.append(total);amounts.append(amount);bonus.append(identity in bonus_ids)
    if total<=0:raise ValueError('Empty weighted distribution')
    rng=Random(seed);nets=[];zero_runs=[];without_bonus=0
    for _ in range(sessions):
        payout=0;longest=current=0;saw_bonus=False
        for _ in range(spins):
            i=bisect_right(cumulative,rng.randrange(total));payout+=amounts[i];saw_bonus|=bool(bonus[i])
            current=current+1 if amounts[i]==0 else 0;longest=max(longest,current)
        nets.append(payout/100-spins);zero_runs.append(longest);without_bonus+=not saw_bonus
    nets.sort();zero_runs.sort()
    def q(values,p):return values[max(0,int(len(values)*p+.999999)-1)]
    return dict(seed=seed,sessions=sessions,paidRoundsPerSession=spins,meanNetX=sum(nets)/sessions,
        medianNetX=q(nets,.5),netP10X=q(nets,.1),netP90X=q(nets,.9),profitableSessionRate=sum(n>0 for n in nets)/sessions,
        noBonusSessionRate=without_bonus/sessions,medianLongestZeroReturnRun=q(zero_runs,.5),p95LongestZeroReturnRun=q(zero_runs,.95),
        limitation='Monte Carlo finite weighted-book sampling with replacement. Each session plays all rounds without bankroll stopping; not wallet recovery or frontend playback validation. Zero means total paid-round payout zero, not merely a losing base spin.')
