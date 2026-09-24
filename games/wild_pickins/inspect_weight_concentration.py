"""Compare exported Rust and reference weight concentration without altering either."""
import argparse
import csv
from collections import defaultdict
import json
from pathlib import Path
from optimizer_candidate import load_prepared, summarize, digest, write


def distribution(rows, weights):
    total=sum(weights[r['id']] for r in rows)
    values=sorted((weights[r['id']] for r in rows),reverse=True)
    return dict(books=len(rows),positiveWeightBooks=sum(w>0 for w in values),weight=total,
        effectiveBooks=total**2/sum(w*w for w in values) if total else None,
        largestProbability=values[0]/total if total else None,
        top10Probability=sum(values[:10])/total if total else None,
        top100Probability=sum(values[:100])/total if total else None,
        pairRepeatProbability=sum(w*w for w in values)/total**2 if total else None)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads((a.run/'manifest.json').read_text())
    rows=[r for source in manifest['sources'] for r in load_prepared(Path(source['prepared']))]
    files={'rust':a.run/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv',
        'reference':a.reference/'reference-weights.csv'}
    weights={};evaluations={}
    for name,path in files.items():
        with path.open() as f:lookup=list(csv.reader(f))
        evaluations[name]=summarize(rows,lookup)
        weights[name]={int(i):int(w) for i,w,payout in lookup}
    totals={name:sum(w.values()) for name,w in weights.items()}
    groups=defaultdict(list);payouts=defaultdict(list)
    for r in rows:
        groups[r['group']].append(r);payouts[(r['group'],r['payout'])].append(r)
    result=dict(sourceHashes={k:digest(v) for k,v in files.items()},
        all={n:distribution(rows,w) for n,w in weights.items()},groups={},payoutClusters=[])
    for group,items in sorted(groups.items()):
        stats={n:distribution(items,w) for n,w in weights.items()}
        for name in weights:
            stats[name]['paidRoundProbability']=stats[name]['weight']/totals[name]
            stats[name]['baseContribution']=sum(weights[name][r['id']]*r['base'] for r in items)/(totals[name]*100)
            stats[name]['bonusContribution']=sum(weights[name][r['id']]*r['bonus'] for r in items)/(totals[name]*100)
        result['groups'][group]=stats
    for (group,payout),items in payouts.items():
        mass={n:sum(w[r['id']] for r in items)/totals[n] for n,w in weights.items()}
        result['payoutClusters'].append(dict(group=group,payoutX=payout/100,books=len(items),probability=mass,
            probabilityRatio=mass['rust']/mass['reference'] if mass['reference'] else None))
    result['payoutClusters'].sort(key=lambda r:r['probability']['rust'],reverse=True)
    result['topBooks']=[]
    for r in sorted(rows,key=lambda r:weights['rust'][r['id']],reverse=True)[:100]:
        probabilities={n:w[r['id']]/totals[n] for n,w in weights.items()}
        result['topBooks'].append(dict(r,probability=probabilities,
            ratio=probabilities['rust']/probabilities['reference'] if probabilities['reference'] else None,
            payoutPeerCount=len(payouts[(r['group'],r['payout'])])))
    result['bonusExperience']={}
    for e in ('10','15','20'):
        result['bonusExperience'][e]={name:{k:evaluations[name]['entries'][e][k] for k in
            ('meanX','medianX','noWildFirstThree','meanDuration','meanDeadSpins')} for name in weights}
    result['deviations']={k:evaluations['rust'][k]-evaluations['reference'][k] for k in
        ('totalReturn','baseReturn','bonusReturn','baseHitRate')}
    a.output.mkdir(parents=True,exist_ok=False);write(a.output/'concentration.json',result)
    print(json.dumps(dict(overall=result['all'],topBooks=[{k:r[k] for k in ('id','group','payout','probability','ratio','payoutPeerCount')} for r in result['topBooks'][:10]],groups={g:{n:s[n]['effectiveBooks'] for n in weights} for g,s in result['groups'].items()}),indent=2))

if __name__=='__main__':main()
