"""Run exactly 20,000 bonuses per entry award using the active control unchanged."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
from bonus_entry_matrix import run_cell
from serve_local import MULTIPLIER_PATH

ROOT=Path('wild-pickins/reports/math/bonus-control-entries-20k')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--resume',action='store_true');a=p.parse_args()
    ROOT.mkdir(parents=True,exist_ok=a.resume)
    lock=(ROOT/'run.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not a.resume:(ROOT/'config.json').write_bytes(MULTIPLIER_PATH.read_bytes())
    raw=(ROOT/'config.json').read_bytes();c=json.loads(raw);weights=tuple(c['fixtureMath']['wildMultiplierWeights'])
    assert all(v[0]==0 for v in c['goldenRates'].values())
    manifest=dict(status='running',seed=9210,bonusesPerCell=20000,totalBonuses=60000,weights=weights,bonusWildCounts=[s.count('W') for s in c['reels']['freegame']],entryAwards=[10,15,20],configSha256=hashlib.sha256(raw).hexdigest(),activeGameChanged=False)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with ProcessPoolExecutor(max_workers=3) as pool:reports=list(pool.map(run_cell,[(weights,e,str(ROOT),20000) for e in (10,15,20)]))
    (ROOT/'comparison.json').write_text(json.dumps(reports,indent=2)+'\n')
    rows=['# Active control bonus entries — 20,000 each','','Exactly 60,000 forced-entry bonuses total; active control configuration unchanged. Empty starting sticky board, zero prior base cash and full cap available. No starter Wild, density change or paytable change. Conditional results are not paid-game RTP; natural entry frequencies must be applied before combining groups.','','| Entry spins | Mean | Median | Below 30× | 30–under 100× | 500×+ | Cap hits |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in reports:
        rows.append(f"| {r['entrySpins']} | {r['payout']['mean']:.2f}× | {r['payout']['quantiles']['0.5']:.2f}× | {r['bands']['below30']['rate']:.2%} | {r['bands']['30to100']['rate']:.2%} | {r['bands']['500plus']['rate']:.2%} | {r['counts']['capHits']} |")
    rows+=['','Seed 9210, paired indexed draws across entry awards. Reports retain confidence intervals, payout/duration histograms and growth by spin. Tail estimates remain sample-limited.','', '[Full comparison](comparison.json).']
    (ROOT/'comparison.md').write_text('\n'.join(rows)+'\n')
    manifest['status']='complete';(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
