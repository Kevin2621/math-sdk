"""Portable prepare/run/evaluate workflow. Never activates a playtest or publishes."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zstandard

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'math-sdk'))
sys.path.insert(0, str(ROOT / 'wild-pickins/tools'))
from contract import validate
from optimize_experimental import evaluate_weights

CONFIG = ROOT/'math-sdk/games/wild_pickins/experiments/wp25-separate-bonus.json'

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')

def segment(book):
    if any(e['type']=='freeSpinTrigger' for e in book['events']):
        return 'bonus'
    p=book['payoutMultiplier']
    return 'zero' if p==0 else 'base_2_to_3' if 200<=p<=300 else 'base_other'

def load(source, validate_contract=True):
    config=json.loads((source/'experiment-config.json').read_text())
    if config != json.loads(CONFIG.read_text()):
        raise ValueError('Source is not the preserved separate-bonus candidate')
    books=[]
    with (source/'books_base.jsonl.zst').open('rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader, io.TextIOWrapper(reader) as lines, (source/'lookUpTable_base.csv').open() as f:
        for line,row in zip(lines,csv.reader(f),strict=True):
            b=json.loads(line)
            envelope={k:config[k] for k in ('schemaVersion','gameId','lineSetId','mathVersion','assetMapVersion','spinBudget','roundCap','fixtureMath')}
            envelope.update(fixtureOnly=True,events=b['events'])
            if validate_contract:
                validate(envelope)
            if list(map(int,row)) != [b['id'],1,b['payoutMultiplier']] or b['events'][-1]['amount']!=b['payoutMultiplier']:
                raise ValueError('Source lookup mismatch or nonuniform source')
            # Retain only aggregate metrics in RAM; complete books remain immutable on disk.
            results=[e for e in b['events'] if e['type']=='wildPickinsSpinResult']
            bonus=any(e['type']=='freeSpinTrigger' for e in b['events'])
            books.append(dict(id=b['id'],payoutMultiplier=b['payoutMultiplier'],
                events=[dict(type='freeSpinTrigger')] if bonus else [],
                baseWin=results[0]['spinWin'], bonusWin=sum(e['spinWin'] for e in results[1:]),
                sticky=len(results[-1]['stickyAfter']) if bonus else 0,
                fullHarvest=any(e['endReason']=='fullHarvest' for e in results)))
            if len(books) % 100000 == 0:
                print(f'Loaded {len(books):,} source rounds (contract validation: {validate_contract})', flush=True)
    if not books or len({b['id'] for b in books})!=len(books):
        raise ValueError('Empty source or duplicate IDs')
    return books,config

def prepare(source, output, profile, threads=8, trials=10000, shows=1000, pigs=1000):
    if min(threads,trials,shows,pigs)<1:
        raise ValueError('Workload settings must be positive')
    books,config=load(source)
    return prepare_validated(source, output, profile, books, config, threads, trials, shows, pigs)

def prepare_validated(source, output, profile, books, config, threads=8, trials=10000, shows=1000, pigs=1000):
    """Prepare from an in-process validated load, allowing paired profiles without a second scan."""
    if profile not in ('reference', 'quieter-base') or min(threads,trials,shows,pigs)<1:
        raise ValueError('Invalid profile or workload')
    # SDK exact-payout fences consume every remaining matching book. Claim bonus
    # IDs first so a zero-paying bonus cannot be reassigned to the nonbonus zero fence.
    groups={name:[b for b in books if segment(b)==name] for name in ('bonus','zero','base_other','base_2_to_3')}
    if any(not g for g in groups.values()):
        raise ValueError('Source lacks a required outcome group; generate a larger natural sample')
    n=len(books)
    probs={k:len(g)/n for k,g in groups.items()}
    means={k:sum(b['payoutMultiplier']/100 for b in g)/len(g) for k,g in groups.items()}
    # Keep bonus entry probability fixed. Reduce the specified base band by 20% in comparison.
    if profile=='quieter-base':
        removed=probs['base_2_to_3']*.2
        probs['base_2_to_3']-=removed
        probs['zero']+=removed
    contributions={k:probs[k]*means[k] for k in groups}
    contributions['bonus']=.967-contributions['base_other']-contributions['base_2_to_3']
    means['bonus']=contributions['bonus']/probs['bonus']
    fences=[]; forces=[]; targets={}
    for k,g in groups.items():
        values=[b['payoutMultiplier']/100 for b in g]
        if not min(values)<=means[k]<=max(values):
            raise ValueError(f'{k}: requested mean outside sample support')
        search=[dict(name='wpCategory',value=k)]
        forces.append(dict(search=search,timesTriggered=len(g),bookIds=[b['id'] for b in g]))
        fences.append(dict(name=k,hr=str(1/probs[k]),rtp=str(contributions[k]),avg_win=str(means[k]),
            identity_condition=dict(search=[] if k=='zero' else search,opposite=False,win_range_start=0 if k=='zero' else -1,win_range_end=0 if k=='zero' else -1),
            min_mean_to_median='0',max_mean_to_median='1000000'))
        targets[k]=dict(probability=probs[k],returnContribution=contributions[k],meanX=means[k],books=len(g))
    output.mkdir(parents=True,exist_ok=False)
    library=output/'games/wild_pickins/library'
    for d in ('configs','forces','lookup_tables','optimization_files','publish_files'):
        (library/d).mkdir(parents=True)
    shutil.copyfile(source/'lookUpTable_base.csv',library/'lookup_tables/lookUpTable_base.csv')
    write(library/'configs/math_config.json',dict(game_id='wild_pickins',bet_modes=[dict(bet_mode='base',cost=1,rtp=.967,max_win=config['roundCap']/100)],fences=[dict(bet_mode='base',fences=fences)],dresses=[dict(bet_mode='base',dresses=[])],bias=[dict(bet_mode='base',bias=[])]))
    write(library/'forces/force_record_base.json',forces)
    (output/'src').mkdir()
    setup=dict(game_name='wild_pickins',bet_type='base',path_to_games='./games',num_show_pigs=shows,num_pigs_per_fence=pigs,threads_for_fence_construction=threads,threads_for_show_construction=threads,score_type='rtp',test_spins=[50,100,200],test_spins_weights=[.3,.4,.3],simulation_trials=trials,run_1000_batch=False,min_mean_to_median=0.0,max_mean_to_median=1000000.0,pmb_rtp=1.0,max_trial_dist=15)
    (output/'src/setup.toml').write_text('\n'.join(f'{k} = {json.dumps(v)}' for k,v in setup.items())+'\n')
    write(output/'manifest.json',dict(profile=profile,sourceHashes={name:digest(source/name) for name in ('books_base.jsonl.zst','lookUpTable_base.csv','experiment-config.json')},configSha256=digest(CONFIG),targets=targets,sourceRounds=n,fullHarvestBooks=sum(b['fullHarvest'] for b in books),experimentalOnly=True))
    print(f'Prepared {profile}: {output}. No optimizer executed.')

def evaluate(source,output,validated=None):
    manifest=json.loads((output/'manifest.json').read_text())
    for name,sha in manifest['sourceHashes'].items():
        if digest(source/name)!=sha: raise ValueError(f'Source changed: {name}')
    books,config=load(source) if validated is None else validated
    lut=output/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv'
    with lut.open() as f: rows=[tuple(map(int,r)) for r in csv.reader(f)]
    report=evaluate_weights(books,rows,config['roundCap'])
    weights={i:w for i,w,p in rows}; total=sum(weights.values())
    def probability(predicate): return sum(weights[b['id']] for b in books if predicate(b))/total
    def average(field): return sum(weights[b['id']]*b[field] for b in books)/total
    bonus_p=probability(lambda b:bool(b['events']))
    report.update(profile=manifest['profile'],lookupSha256=digest(lut),
        bonusEntryProbability=bonus_p,bonusMeanX=average('bonusWin')/100/bonus_p if bonus_p else None,
        bonusBelow5XConditional=probability(lambda b:bool(b['events']) and b['bonusWin']<500)/bonus_p if bonus_p else None,
        meanFinalStickyConditional=average('sticky')/bonus_p if bonus_p else None,
        baseLdwProbability=probability(lambda b:0<b['baseWin']<100),
        baseProfitProbability=probability(lambda b:b['baseWin']>100),
        baseReturnContribution=average('baseWin')/100,
        fullHarvestProbability=probability(lambda b:b['fullHarvest']),
        effectiveBookCount=total**2/sum(w*w for w in weights.values()),
        largestBookProbability=max(weights.values())/total,
        top100BookProbability=sum(sorted(weights.values(),reverse=True)[:100])/total)
    actual={k:probability(lambda b:segment(b)==k) for k in manifest['targets']}
    report['segmentProbabilities']=actual
    report['checks']=dict(rtpWithin001PercentagePoint=abs(report['weightedRtp']-.967)<=.0001,
        segmentProbabilitiesWithin0001=all(abs(actual[k]-v['probability'])<=.0001 for k,v in manifest['targets'].items()))
    report['productionAccepted']=False
    report['limitations']='No automatic activation. Bonus payout shape/sticky mix may change under weighting. No maximum frequency target; absent Full Harvest support cannot be repaired by weights. Session diversity, tail stability and medium volatility need review.'
    write(output/'weighted-evaluation.json',report)
    print(json.dumps(report,indent=2))
    if not all(report['checks'].values()): raise ValueError('Output failed comparison gates; retain for diagnosis, do not activate')

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--source',type=Path,required=True);prep.add_argument('--output',type=Path,required=True);prep.add_argument('--profile',choices=['reference','quieter-base'],required=True)
    for name,default in [('threads',8),('trials',10000),('shows',1000),('pigs',1000)]:prep.add_argument('--'+name,type=int,default=default)
    for command in ('run','evaluate'):
        cmd=sub.add_parser(command);cmd.add_argument('--source',type=Path,required=True);cmd.add_argument('--output',type=Path,required=True)
        if command=='run':cmd.add_argument('--binary',type=Path,required=True)
    a=p.parse_args()
    if a.command=='prepare':prepare(a.source,a.output,a.profile,a.threads,a.trials,a.shows,a.pigs)
    else:
        if a.command=='run':
            manifest=json.loads((a.output/'manifest.json').read_text())
            for name,sha in manifest['sourceHashes'].items():
                if digest(a.source/name)!=sha:raise ValueError('Source changed')
            with (a.output/'optimizer.log').open('x') as log:
                subprocess.run([str(a.binary.resolve())],cwd=a.output,stdout=log,stderr=subprocess.STDOUT,check=True)
        evaluate(a.source,a.output)

if __name__=='__main__':main()
