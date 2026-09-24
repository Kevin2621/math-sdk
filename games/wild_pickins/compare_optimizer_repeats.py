"""Describe stochastic Rust repeats using fixed-source payout and book concentration."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from optimizer_candidate import load_prepared, write

ROOT=Path(__file__).resolve().parents[3]/'wild-pickins/reports/math'

def main():
    original=json.loads((ROOT/'rust-budget-trial1/manifest.json').read_text())
    rows=[r for s in original['sources'] for r in load_prepared(Path(s['prepared']))]
    by_id={r['id']:r for r in rows};results=[]
    for name in ['rust-budget-trial1']+[f'rust-budget-repeat{i}' for i in range(1,6)]:
        path=ROOT/name;manifest=json.loads((path/'manifest.json').read_text())
        assert manifest['status']=='complete'
        assert all(manifest[k]==original[k] for k in ('sources','binarySha256','referenceWeightsSha256'))
        assert {k:v for k,v in manifest['setup'].items() if k!='path_to_games'}=={k:v for k,v in original['setup'].items() if k!='path_to_games'}
        with (path/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv').open() as f:
            weights={int(i):int(w) for i,w,p in csv.reader(f)}
        total=sum(weights.values());clusters=defaultdict(int);counts=defaultdict(int)
        for i,w in weights.items():
            r=by_id[i];key=(r['group'],r['payout']);clusters[key]+=w;counts[key]+=1
        highest=max(weights,key=weights.get);top=by_id[highest]
        baseclusters=sorted([(k,w) for k,w in clusters.items() if k[0]=='base_profit'],key=lambda x:x[1],reverse=True)
        evaluation=json.loads((path/'evaluation.json').read_text());comparison=json.loads((path/'comparison.json').read_text())
        result=dict(run=name,checks=comparison['checks'],metrics={k:evaluation[k] for k in ('totalReturn','baseReturn','bonusReturn','baseHitRate','effectiveBookCount','largestBookProbability','top100BookProbability')},
            highestBook=dict(id=highest,group=top['group'],payoutX=top['payout']/100,probability=weights[highest]/total,peerCount=counts[(top['group'],top['payout'])]),
            payout176Probability=clusters[('base_profit',176)]/total,
            topProfitPayouts=[dict(payoutX=k[1]/100,probability=w/total,books=counts[k]) for k,w in baseclusters[:5]],
            bonusMedian=evaluation['bonus']['medianX'],entry10Median=evaluation['entries']['10']['medianX'])
        results.append(result)
    output=ROOT/'rust-budget-repeat-comparison';output.mkdir(exist_ok=False)
    write(output/'comparison.json',results)
    lines=['# Five fixed-input Rust repeats','', 'Original run shown for context; repeats 1–5 are five additional independent stochastic searches. Same source manifests, reference weights, executable hash and settings verified. Only the output path differs. No game activation or tolerance changes.','',
        '| Run | Largest-book payout | Largest-book probability | Top 100 mass | 1.76× combined mass | Bonus median |',
        '|---|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"| {r['run']} | {r['highestBook']['payoutX']:.2f}× | {100*r['metrics']['largestBookProbability']:.4f}% | {100*r['metrics']['top100BookProbability']:.3f}% | {100*r['payout176Probability']:.4f}% | {r['bonusMedian']:.2f}× |")
    (output/'comparison.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
    print(json.dumps([dict(run=r['run'],checks=r['checks'],metrics=r['metrics']) for r in results],indent=2))

if __name__=='__main__':main()
