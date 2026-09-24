"""Seeded natural-reel diagnostic; reports sampling error, not certified RTP."""
import argparse
from collections import Counter
from fractions import Fraction
import json
import math
from pathlib import Path
from random import Random
from round_model import RoundModel
from reel_source import ReelSource
from experiment_random import ExperimentRandom, SCHEME
from experiment_evidence import archive_inputs, finish_evidence
from balance_metrics import BalanceMetrics, markdown_report

def measure(config,seed,rounds):
    if type(rounds) is not int or rounds<2:raise ValueError('At least two complete rounds required')
    metrics=BalanceMetrics(config)
    scheme=config.get('rngScheme','legacy')
    if scheme not in ('legacy',SCHEME):raise ValueError('Unknown experimental RNG scheme')
    fm=config['fixtureMath'];sources={mode:ReelSource(strips) for mode,strips in config['reels'].items()}
    table=lambda name:{(s,int(n)):v for s,p in fm[name].items() for n,v in p.items()}
    pay,bonus_pay=table('paytable'),table('bonusPaytable');paths=dict(enumerate(fm['paths'],1))
    rng=Random(seed);counts=Counter();base=bonus=squares=bonus_spins=scatter_cash=0;maximum=0
    for round_id in range(rounds):
        metrics.begin_round()
        indexed=ExperimentRandom(seed,round_id) if scheme==SCHEME else None
        model=RoundModel(paths,pay,config['roundCap'],config['spinBudget'],Fraction(*config['goldenRates']['basegame']),Fraction(*config['goldenRates']['freegame']),rng,bonus_paytable=bonus_pay,wild_multiplier_weights=tuple(fm['wildMultiplierWeights']),bonus_scatter_pays={int(n):v for n,v in fm['bonusScatterPays'].items()},collision_spins_per_hit=fm.get('collisionSpinsPerHit',False),settlement_policy=fm.get('settlementPolicy','fullHarvest'),experiment_random=indexed)
        while not model.ended:
            result=model.spin(sources[model.mode].draw(rng,experiment_random=indexed,mode=model.mode,spin_index=0 if model.mode=='basegame' else model.completed).board)
            metrics.spin(result)
            if result['gameType']=='basegame':
                win=result['spinWin'];base+=win
                counts['zeroBase' if not win else 'belowStakeBase' if win<100 else 'breakEvenBase' if win==100 else 'profitBase']+=1
                counts['bonusEntries']+=bool(result['entryAward'])
            else: bonus_spins+=1
            scatter_cash+=result.get('scatterWin',0)
            counts['fullHarvest']+=result['endReason']=='fullHarvest'
        bonus+=model.bonus_total;squares+=(model.total/100)**2;maximum=max(maximum,model.total)
        metrics.end_round()
    mean=(base+bonus)/(rounds*100)
    sd=math.sqrt(max(0,(squares-rounds*mean**2)/(rounds-1)))
    return dict(seed=seed,rounds=rounds,observedReturn=mean,standardError=sd/math.sqrt(rounds),baseContribution=base/(rounds*100),bonusContribution=bonus/(rounds*100),scatterCashContribution=scatter_cash/(rounds*100),maximumObservedX=maximum/100,meanBonusSpins=bonus_spins/counts['bonusEntries'] if counts['bonusEntries'] else 0,counts=dict(counts),rates={k:v/rounds for k,v in counts.items()},metrics=metrics.report(),note='Natural reel sample, not finite weighted RTP or a validated rare-tail estimate.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--rounds',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.rounds<2:p.error('At least two rounds required')
    if a.output.exists():p.error('Refusing to overwrite previous evidence')
    summary_path=a.output.with_name(a.output.stem+'-summary.md')
    if summary_path.exists():p.error('Refusing to overwrite previous summary')
    config_bytes=a.config.read_bytes();config=json.loads(config_bytes)
    inputs=a.output.with_name(a.output.stem+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
    provenance=archive_inputs(config_bytes,inputs,a.seed,a.rounds,'balance_multiplier_wilds.py')
    result=measure(config,a.seed,a.rounds)
    result.update(config=config,rngScheme=provenance['rngScheme'],sourceDigest=provenance['sourceDigest'],configSha256=provenance['configSha256'])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    (inputs/'report.json').write_bytes(a.output.read_bytes())
    summary=markdown_report(result)
    with summary_path.open('x') as f:f.write(summary)
    (inputs/'summary.md').write_text(summary);finish_evidence(inputs,provenance)
    print(json.dumps({k:v for k,v in result.items() if k not in ('config','metrics')},indent=2))
