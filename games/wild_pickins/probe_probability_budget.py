"""Deterministic budget feasibility probe; not the Rust optimizer or a publish command.

Exponential tilting within fixed groups provides a diverse reference distribution.
No events or payouts are changed. Trial assumptions are recorded in the output.
"""
import argparse
from collections import defaultdict
from itertools import product
import json
import math
from pathlib import Path
from optimizer_candidate import load_prepared, summarize, write
from generate_targeted_entries import ConditionalEntry


def tilt(groups, masses, field, target):
    def calculate(t):
        weights={}; total=0.0
        for name,rows in groups.items():
            values=[r[field]/100 for r in rows]
            terms=[t*v for v in values];shift=max(terms)
            exp=[math.exp(x-shift) for x in terms];den=sum(exp)
            for r,v,e in zip(rows,values,exp):
                w=masses[name]*e/den;weights[r['id']]=w;total+=w*v
        return total,weights
    low=sum(masses[k]*min(r[field]/100 for r in rows) for k,rows in groups.items())
    high=sum(masses[k]*max(r[field]/100 for r in rows) for k,rows in groups.items())
    if not low<target<high:raise ValueError(f'{field} target {target} outside strict support ({low},{high})')
    lo,hi=-1.,1.
    while calculate(lo)[0]>target:lo*=2
    while calculate(hi)[0]<target:hi*=2
    for _ in range(65):
        mid=(lo+hi)/2
        if calculate(mid)[0]<target:lo=mid
        else:hi=mid
    actual,weights=calculate((lo+hi)/2)
    return weights,dict(target=target,actual=actual,support=[low,high],tilt=(lo+hi)/2)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',nargs='+',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    from optimizer_candidate import digest
    for path in a.prepared:
        manifest=json.loads((path/'manifest.json').read_text())
        if manifest['sourceHashes']['experiment-config.json']!=digest(a.config):
            raise ValueError('Prepared source configuration mismatch')
    rows=[r for path in a.prepared for r in load_prepared(path)]
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Overlapping source IDs')
    config=json.loads(a.config.read_text())
    # Conditional entry shares come from exact valid stop-tuple counts.
    counts={e:ConditionalEntry(config['reels']['basegame'],n).count for e,n in [(10,3),(15,4),(20,5)]}
    shares={e:c/sum(counts.values()) for e,c in counts.items()}
    bonusgroups=defaultdict(list);basegroups=defaultdict(list)
    for r in rows:(bonusgroups if r['entry'] else basegroups)[r['group']].append(r)
    masses={}
    trial10=dict(below10=.15,**{'10to30':.20,'30to100':.60,'100to500':.045,'500plus':.005})
    for band,fraction in trial10.items():
        name=f'entry10_{band}'
        if name not in bonusgroups:raise ValueError(f'Missing required group {name}')
        masses[name]=.01*shares[10]*fraction
    # Preserve observed non-cap band proportions of targeted 15/20 strata.
    # This is an explicit trial assumption, NOT inferred natural entry probability.
    cap_probability=1e-7
    if 'entry20_cap' not in bonusgroups:raise ValueError('Missing cap coverage')
    masses['entry20_cap']=cap_probability
    for entry in (15,20):
        names=[k for k in bonusgroups if k.startswith(f'entry{entry}_') and not k.endswith('_cap')]
        count=sum(len(bonusgroups[k]) for k in names)
        available=.01*shares[entry]-(cap_probability if entry==20 else 0)
        for k in names:masses[k]=available*len(bonusgroups[k])/count
    if set(masses)!=set(bonusgroups):raise ValueError('Unbudgeted bonus groups require an explicit allocation')
    bw,bonuscheck=tilt(bonusgroups,masses,'bonus',.5802)
    bonus_base=sum(bw[r['id']]*r['base']/100 for group in bonusgroups.values() for r in group)
    bonus_hit=sum(bw[r['id']] for group in bonusgroups.values() for r in group if r['base']>0)
    positive=.25-bonus_hit
    positive_count=sum(len(v) for k,v in basegroups.items() if k!='base_zero')
    basemasses={k:positive*len(v)/positive_count for k,v in basegroups.items() if k!='base_zero'}
    basemasses['base_zero']=.99-positive
    if any(x<=0 for x in basemasses.values()):raise ValueError('Infeasible base masses')
    aw,basecheck=tilt(basegroups,basemasses,'base',.3868-bonus_base)
    weights=dict(aw)
    weights.update(bw)
    lookup=[(r['id'],round(weights[r['id']]*(2**50)),r['payout']) for r in rows]
    result=summarize(rows,lookup)
    gates=dict(totalReturn=abs(result['totalReturn']-.967)<1e-8,
        baseReturn=abs(result['baseReturn']-.3868)<1e-8,bonusReturn=abs(result['bonusReturn']-.5802)<1e-8,
        baseHitRate=abs(result['baseHitRate']-.25)<1e-8,
        bonusEntry=abs(result['bonus']['probability']-.01)<1e-8,
        entry10Middle=abs(result['entries']['10']['bands']['30to100']-.60)<1e-8,
        cap=abs(result['capProbability']-cap_probability)<1e-10)
    if not all(gates.values()):raise ValueError(f'Exported-weight checks failed: {gates}')
    a.output.mkdir(parents=True,exist_ok=False)
    with (a.output/'reference-weights.csv').open('w') as f:
        for i,w,pay in lookup:f.write(f'{i},{w},{pay}\n')
    write(a.output/'evaluation.json',dict(result,checks=gates,productionAccepted=False))
    write(a.output/'budget.json',dict(totalReturn=.967,baseReturn=.3868,bonusReturn=.5802,entryProbability=.01,
        entryShares=shares,entry10Bands=trial10,capProbability=cap_probability,
        groupMasses=dict(masses,**basemasses),bonusSupport=bonuscheck,baseSupport=basecheck,
        note='Illustrative trial. 1-in-10-million cap probability is a chosen probe value, not a platform requirement or approved final target. Scalar tilting reference, not Rust optimization.'))
    write(a.output/'sources.json',[dict(prepared=str(path.resolve()),manifest=json.loads((path/'manifest.json').read_text())) for path in a.prepared])
    print(json.dumps(dict(checks=gates,meanBonus=result['bonus']['meanX'],medianBonus=result['bonus']['medianX'],
        effectiveBooks=result['effectiveBookCount'],largestBookProbability=result['largestBookProbability']),indent=2))

if __name__=='__main__':main()
