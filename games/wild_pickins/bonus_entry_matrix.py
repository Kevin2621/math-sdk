"""Stratified bonus-only experiments; checkpointed bonuses per cell."""
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from random import Random
import time
from balance_metrics import distribution,rate_stats
from experiment_random import ExperimentRandom
from experiment_evidence import archive_inputs,finish_evidence
from round_model import RoundModel
from reel_source import ReelSource

ROOT=Path('wild-pickins/reports/math/bonus-entry-matrix-40k')
MIXES=((85,12,3),(90,8,2),(95,4,1))

def make_model(config,entry,indexed):
    fm=config['fixtureMath'];table=lambda key:{(s,int(n)):v for s,p in fm[key].items() for n,v in p.items()}
    model=RoundModel(dict(enumerate(fm['paths'],1)),table('paytable'),config['roundCap'],config['spinBudget'],Fraction(0),Fraction(0),Random(0),bonus_paytable=table('bonusPaytable'),wild_multiplier_weights=tuple(config['experimentBonusWeights']),bonus_scatter_pays={int(n):v for n,v in fm['bonusScatterPays'].items()},collision_spins_per_hit=True,settlement_policy='accumulation',experiment_random=indexed)
    model.mode='freegame';model.granted=entry;model.remaining=entry
    return model

def run_cell(args):
    weights,entry,root,total=args;root=Path(root);name='-'.join(map(str,weights))+f'-entry{entry}';folder=root/name;folder.mkdir(exist_ok=True)
    config=json.loads((root/'config.json').read_text());config['experimentBonusWeights']=list(weights)
    raw=(json.dumps(config,indent=2)+'\n').encode()
    if (folder/'reproducibility.json').exists():
        import hashlib
        from experiment_evidence import ROOT as workspace
        evidence=json.loads((folder/'reproducibility.json').read_text())
        if evidence['configSha256']!=hashlib.sha256(raw).hexdigest() or evidence['rounds']!=total:raise ValueError('Resume configuration mismatch')
        for name_,digest in evidence['sourceHashes'].items():
            if hashlib.sha256((workspace/name_).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed since checkpoint: '+name_)
    else:evidence=archive_inputs(raw,folder,9210,total,'bonus_entry_matrix.py')
    if (folder/'report.json').exists():return json.loads((folder/'report.json').read_text())
    source=ReelSource(config['reels']['freegame']);payout=Counter();duration=Counter();occupancy=Counter();progress=defaultdict(Counter);counts=Counter();started=time.time()
    start=0;elapsed=0
    if (folder/'checkpoint.json').exists():
        state=json.loads((folder/'checkpoint.json').read_text());start=state['completed'];elapsed=state['elapsedSeconds']
        payout=Counter(dict(state['payout']));duration=Counter(dict(state['duration']));occupancy=Counter(dict(state['occupancy']));counts=Counter(state['counts'])
        progress=defaultdict(Counter,{int(k):Counter(v) for k,v in state['progress'].items()})
        assert sum(payout.values())==start and start<=total
    for rid in range(start,total):
        indexed=ExperimentRandom(9210,rid);model=make_model(config,entry,indexed);first=None
        while not model.ended:
            r=model.spin(source.draw(model.rng,experiment_random=indexed,mode='freegame',spin_index=model.completed).board)
            fresh=len(set(r['stickyAfter'])-set(r['stickyBefore']));row=progress[model.completed]
            row.update(observations=1,newWilds=fresh,stickyCells=len(r['stickyAfter']),collisions=len(r['collisionPositions']),extraSpins=r['grantedExtraSpins'],positiveSpins=int(r['spinWin']>0))
            if fresh and first is None:first=model.completed
            counts['fullBoardSpins']+=len(r['stickyAfter'])==15
        payout[model.bonus_total/100]+=1;duration[model.completed]+=1;occupancy[len(model.sticky)]+=1
        counts['noWildFirst3']+=first is None or first>3;counts['capHits']+=model.total==model.cap
        if (rid+1)%1000==0 or rid+1==total:
            timing=dict(completed=rid+1,total=total,elapsedSeconds=elapsed+time.time()-started)
            state=dict(**timing,payout=list(payout.items()),duration=list(duration.items()),occupancy=list(occupancy.items()),counts=dict(counts),progress=dict(progress))
            temp=folder/'checkpoint.tmp';temp.write_text(json.dumps(state));temp.replace(folder/'checkpoint.json')
            temp=folder/'progress.tmp';temp.write_text(json.dumps(timing));temp.replace(folder/'progress.json')
    bands={name:rate_stats(sum(n for x,n in payout.items() if pred(x)),total) for name,pred in [('below10',lambda x:x<10),('below30',lambda x:x<30),('30to100',lambda x:30<=x<100),('50to100',lambda x:50<=x<100),('100to500',lambda x:100<=x<500),('200plus',lambda x:x>=200),('500plus',lambda x:x>=500),('1000plus',lambda x:x>=1000)]}
    report=dict(weights=weights,entrySpins=entry,bonuses=total,payout=distribution(payout),duration=distribution(duration),finalSticky=distribution(occupancy),bands=bands,counts=dict(counts),progress=[dict(spin=k,**v) for k,v in sorted(progress.items())],scope='Forced-entry bonus-only experiment, empty starting sticky board, zero prior base cash, full cap available. Not paid-round RTP. Same indexed draws paired across cells; no entry-frequency weighting applied.')
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');finish_evidence(folder,evidence)
    print(name+' complete',flush=True);return report

if __name__=='__main__':
    import argparse,fcntl
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--resume',action='store_true');a=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=a.resume)
    lock=(ROOT/'run.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    active=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-split4060-hit25.json').read_text())
    six=json.loads(Path('math-sdk/games/wild_pickins/experiments/wp25-mix28-bonus-high35-no-scatters.json').read_text())
    active['reels']['freegame']=deepcopy(six['reels']['freegame'])
    assert all(s.count('W')==6 and 'S' not in s and all(s.count(h)==28 for h in ('C01','C02','C03')) for s in active['reels']['freegame'])
    if not a.resume:(ROOT/'config.json').write_text(json.dumps(active,indent=2)+'\n')
    (ROOT/'manifest.json').write_text(json.dumps(dict(status='running',seed=9210,bonusesPerCell=40000,totalBonuses=360000,mixes=MIXES,entryAwards=[10,15,20],activeGameChanged=False),indent=2)+'\n')
    with ProcessPoolExecutor(max_workers=3) as pool:reports=list(pool.map(run_cell,[(w,e,str(ROOT),40000) for w in MIXES for e in (10,15,20)]))
    (ROOT/'comparison.json').write_text(json.dumps(reports,indent=2)+'\n')
    (ROOT/'manifest.json').write_text(json.dumps(dict(status='complete',seed=9210,bonusesPerCell=40000,totalBonuses=360000,mixes=MIXES,entryAwards=[10,15,20],activeGameChanged=False),indent=2)+'\n')
