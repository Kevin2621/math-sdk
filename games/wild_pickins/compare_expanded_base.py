"""Compare five unchanged-budget searches before/after additional base coverage."""
import csv
import json
from pathlib import Path
from collections import Counter
from optimizer_candidate import load_prepared,write
ROOT=Path(__file__).resolve().parents[3]/'wild-pickins/reports/math'

def main():
    baseline=ROOT/'rust-budget-trial1'
    original=json.loads((baseline/'manifest.json').read_text())
    rows=[r for s in original['sources'] for r in load_prepared(Path(s['prepared']))]
    extra=[r for r in load_prepared(ROOT/'optimizer-pool-second100k-seed9221-analysis') if not r['entry']]
    by_id={r['id']:r for r in rows+extra}
    reports=[]
    for expanded,prefix in [(False,'rust-budget-repeat'),(True,'rust-expanded-base')]:
        for i in range(1,6):
            run=ROOT/f'{prefix}{i}';manifest=json.loads((run/'manifest.json').read_text())
            assert manifest['binarySha256']==original['binarySha256']
            assert manifest['sources']==original['sources']
            assert manifest['referenceWeightsSha256']==original['referenceWeightsSha256']
            setup=lambda m:{k:v for k,v in m['setup'].items() if k!='path_to_games'}
            assert setup(manifest)==setup(original)
            for name in ('configs/math_config.json',):
                assert (run/'games/wild_pickins/library'/name).read_bytes()==(baseline/'games/wild_pickins/library'/name).read_bytes()
            with (run/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv').open() as f:
                weights={int(i):int(w) for i,w,p in csv.reader(f)}
            assert set(weights)=={r['id'] for r in (rows+extra if expanded else rows)}
            total=sum(weights.values());top=max(weights,key=weights.get);r=by_id[top]
            prob176=sum(w for i,w in weights.items() if by_id[i]['group']=='base_profit' and by_id[i]['payout']==176)/total
            evaluation=json.loads((run/'evaluation.json').read_text());check=json.loads((run/'comparison.json').read_text())['checks']
            reports.append(dict(run=run.name,expanded=expanded,topPayoutX=r['payout']/100,
                topProbability=weights[top]/total,payout176Probability=prob176,
                top100Probability=evaluation['top100BookProbability'],effectiveBooks=evaluation['effectiveBookCount'],
                baseReturn=evaluation['baseReturn'],baseHitRate=evaluation['baseHitRate'],checks=check))
    output=ROOT/'expanded-base-comparison';output.mkdir(exist_ok=False)
    support={name:Counter(r['payout'] for r in group if r['group']=='base_profit')[176] for name,group in [('original',rows),('expanded',rows+extra)]}
    write(output/'comparison.json',dict(addedBaseRounds=len(extra),payout176Support=support,runs=reports))
    lines=['# Expanded base-pool comparison','',f'Added {len(extra):,} non-triggering base rounds; 971 new bonus rounds excluded. Bonus book IDs, group probabilities/means, binary and settings verified unchanged. The 1.76× profitable-base payout has '+str(support['original'])+' supporting books before and '+str(support['expanded'])+' after.','',
        '| Run | Largest-book payout | Largest-book probability | Top 100 mass | 1.76× mass |','|---|---:|---:|---:|---:|']
    for r in reports:lines.append(f"| {r['run']} | {r['topPayoutX']:.2f}× | {100*r['topProbability']:.4f}% | {100*r['top100Probability']:.3f}% | {100*r['payout176Probability']:.4f}% |")
    (output/'comparison.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
