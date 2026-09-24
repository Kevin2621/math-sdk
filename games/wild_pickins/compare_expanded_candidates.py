"""Read-only five-candidate review, including base cash and conditional diversity."""
import csv,json
from pathlib import Path
from optimizer_candidate import load_prepared,digest,write
from inspect_weight_concentration import distribution
ROOT=Path(__file__).resolve().parents[3]/'wild-pickins/reports/math'

def median(rows,weights,field):
    total=sum(weights[r['id']] for r in rows);acc=0
    for row in sorted(rows,key=lambda r:r[field]):
        acc+=weights[row['id']]
        if total and 2*acc>=total:return row[field]/100
    return None

def main():
    first=json.loads((ROOT/'rust-expanded-base1/manifest.json').read_text())
    rows=[r for s in first['sources'] for r in load_prepared(Path(s['prepared']))]
    rows += [r for r in load_prepared(Path(first['additionalBase']['prepared'])) if r['entry']==0]
    results=[]
    for i in range(1,6):
        path=ROOT/f'rust-expanded-base{i}'
        manifest=json.loads((path/'manifest.json').read_text())
        assert all(manifest[k]==first[k] for k in ('sources','additionalBase','binarySha256','referenceWeightsSha256'))
        evaluation=json.loads((path/'evaluation.json').read_text())
        lookup=path/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv'
        assert digest(lookup)==evaluation['lookupSha256']
        with lookup.open() as f:weights={int(identity):int(w) for identity,w,pay in csv.reader(f)}
        assert set(weights)=={r['id'] for r in rows}
        total=sum(weights.values())
        positive=[r for r in rows if r['base']>0]
        bands={name:sum(weights[r['id']] for r in rows if low<=r['base']<high)/total for name,low,high in
            [('zero',0,1),('partial',1,100),('1to2',100,200),('2to5',200,500),('5to10',500,1000),('10to50',1000,5000),('50plus',5000,10**12)]}
        item=dict(candidate=i,metrics={k:evaluation[k] for k in ('totalReturn','baseReturn','bonusReturn','baseHitRate','effectiveBookCount','largestBookProbability','top100BookProbability')},
            checks=json.loads((path/'comparison.json').read_text())['checks'],
            baseBands=bands,basePayingMedian=median(positive,weights,'base'),
            basePayingMean=evaluation['baseReturn']/evaluation['baseHitRate'],
            baseProfitProbability=sum(weights[r['id']] for r in rows if r['base']>100)/total,
            entryMetrics={},entryDiversity={})
        for entry in (10,15,20):
            entryrows=[r for r in rows if r['entry']==entry]
            e=evaluation['entries'][str(entry)]
            item['entryDiversity'][entry]=distribution(entryrows,weights)
            item['entryMetrics'][entry]={k:e[k] for k in ('meanX','medianX','noWildFirstThree','meanDuration','meanDeadSpins','bands')}
            item['entryMetrics'][entry]['stickyAtSpin5']=e['progressionConditionalOnReachingSpin'][4]['sticky']
            item['entryMetrics'][entry]['stickyAtSpin10']=e['progressionConditionalOnReachingSpin'][9]['sticky']
        results.append(item)
    out=ROOT/'expanded-candidate-review';out.mkdir(exist_ok=False);write(out/'comparison.json',results)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
