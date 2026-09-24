"""Paired base-only test: modest high-symbol increases on reels four and five."""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from random import Random
from balance_metrics import mean_stats
from payline_metrics import PaylineMetrics
from experiment_evidence import archive_inputs, finish_evidence
from experiment_random import ExperimentRandom
from reel_source import ReelSource
from round_model import RoundModel


def candidates(reference, all_reels=False):
    result={}
    for copies in (8,10,12):
        config=deepcopy(reference)
        for reel in (range(5) if all_reels else (3,4)):
            strip=config['reels']['basegame'][reel]
            positions=[i for i,s in enumerate(strip) if s in ('C04','C05','C06','C07','C08')]
            Random(9070+reel).shuffle(positions)
            # Nested replacements preserve all Wild/scatter positions and existing highs.
            replacements=['C01','C02','C03']*(copies-8)
            for position,symbol in zip(positions,replacements):strip[position]=symbol
        config['mathVersion']=f'experimental-late-highs-{copies}'
        config['description']='Paired late-reel high-count experiment; not selected for playback.'
        if not all_reels: assert config['reels']['basegame'][:3]==reference['reels']['basegame'][:3]
        assert config['reels']['freegame']==reference['reels']['freegame']
        for r in (range(5) if all_reels else (3,4)):
            assert [(i,s) for i,s in enumerate(config['reels']['basegame'][r]) if s in ('W','S')]==[(i,s) for i,s in enumerate(reference['reels']['basegame'][r]) if s in ('W','S')]
            assert all(Counter(config['reels']['basegame'][r])[s]==copies for s in ('C01','C02','C03'))
        result[str(copies)]=config
    return result


def stacked_candidates(reference):
    result={'8':deepcopy(reference)}
    for size in (2,3):
        config=deepcopy(reference)
        for reel,strip in enumerate(config['reels']['basegame']):
            original=strip.copy();locked=set();rng=Random(9080+reel)
            for symbol in ('C01','C02','C03'):
                remaining=strip.count(symbol)
                while remaining>=size:
                    starts=list(range(len(strip)));rng.shuffle(starts)
                    target=next(([ (start+j)%len(strip) for j in range(size)] for start in starts
                        if all((start+j)%len(strip) not in locked and strip[(start+j)%len(strip)] not in ('W','S') for j in range(size))),None)
                    if target is None: raise ValueError('No eligible stack window')
                    for pos in target:
                        if strip[pos]!=symbol:
                            donor=next(i for i,sym in enumerate(strip) if sym==symbol and i not in locked and i not in target)
                            strip[pos],strip[donor]=strip[donor],strip[pos]
                    locked.update(target);remaining-=size
            assert Counter(strip)==Counter(original)
            assert [(i,s) for i,s in enumerate(strip) if s in ('W','S')]==[(i,s) for i,s in enumerate(original) if s in ('W','S')]
        config['mathVersion']=f'experimental-high-stacks-{size}'
        config['description']='High-symbol stacks; unchanged counts and specials; not selected.'
        result[str(size)]=config
    return result


def run(reference,output,rounds,seed,all_reels=False,stacks=False):
    output.mkdir(parents=True,exist_ok=False)
    configs=stacked_candidates(reference) if stacks else candidates(reference,all_reels);hist={k:Counter() for k in configs};delta={k:Counter() for k in configs}
    awards={k:Counter() for k in configs};entries=Counter();hits=Counter()
    sources={k:ReelSource(c['reels']['basegame']) for k,c in configs.items()}
    trackers={k:PaylineMetrics(c["fixtureMath"]["paths"]) for k,c in configs.items()}
    provenance={}
    for k,c in configs.items():
        raw=(json.dumps(c,indent=2)+'\n').encode();(output/(k+'.json')).write_bytes(raw)
        folder=output/(k+'-inputs');folder.mkdir()
        provenance[k]=archive_inputs(raw,folder,seed,rounds,'experiment_late_highs.py')
    for rid in range(rounds):
        values={};positive=[];trigger=[]
        for k,c in configs.items():
            fm=c['fixtureMath'];indexed=ExperimentRandom(seed,rid);rng=Random(seed)
            table=lambda name:{(s,int(n)):v for s,p in fm[name].items() for n,v in p.items()}
            model=RoundModel(dict(enumerate(fm['paths'],1)),table('paytable'),c['roundCap'],c['spinBudget'],Fraction(0),Fraction(0),rng,bonus_paytable=table('bonusPaytable'),wild_multiplier_weights=tuple(fm['wildMultiplierWeights']),bonus_scatter_pays={int(n):v for n,v in fm['bonusScatterPays'].items()},collision_spins_per_hit=True,settlement_policy='accumulation',experiment_random=indexed)
            r=model.spin(sources[k].draw(rng,experiment_random=indexed,mode='basegame',spin_index=0).board)
            trackers[k].spin(r)
            value=r['spinWin'];values[k]=value;hist[k][value/100]+=1
            hits[k]+=value>0;entries[k]+=bool(r['entryAward']);positive.append(value>0);trigger.append(r['entryAward'])
            for a in r['lines'].awards:
                awards[k][('high' if a.crop in ('C01','C02','C03') else 'low')+'-'+str(a.count)]+=1
        assert len(set(trigger))==1
        if not all_reels and not stacks: assert len(set(positive))==1
        for k,v in values.items():delta[k][(v-values['8'])/100]+=1
    report={'seed':seed,'rounds':rounds,'scope':'Paired base-only screen; no bonus RTP estimate.', 'changedReels':list(range(1,6)) if all_reels or stacks else [4,5], 'experiment':'high-stacks' if stacks else 'high-counts', 'variants':{}}
    for k in configs:
        report['variants'][k]={'paylineAttribution':trackers[k].report(rounds),'highShareOnReels4And5':sum(s in ('C01','C02','C03') for s in configs[k]['reels']['basegame'][3])/240,'baseReturn':mean_stats(hist[k]),'positiveRate':hits[k]/rounds,'positiveMeanX':sum(v*n for v,n in hist[k].items())/hits[k] if hits[k] else None,'bonusEntries':entries[k],'winningLinesByTierAndLength':dict(awards[k]),'pairedReturnDifferenceFrom8':mean_stats(delta[k])}
    raw=json.dumps(report,indent=2)+'\n';(output/'report.json').write_text(raw)
    for k in configs:
        folder=output/(k+'-inputs');(folder/'report.json').write_text(raw);finish_evidence(folder,provenance[k])
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stacks',action='store_true');p.add_argument('--all-reels',action='store_true');p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--rounds',type=int,default=20000);p.add_argument('--seed',type=int,default=9071);a=p.parse_args()
    if a.rounds<2:p.error('At least two rounds required')
    print(json.dumps(run(json.loads(a.reference.read_text()),a.output,a.rounds,a.seed,a.all_reels,a.stacks),indent=2))
