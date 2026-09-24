"""Isolated Rust search against the first reference budget. Never activates gameplay."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
from collections import defaultdict
from optimizer_candidate import load_prepared, summarize, write, digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--additional-base',type=Path,help='Add only non-triggering rows; original group budgets remain fixed')
    p.add_argument('--supplement',type=Path,action='append',default=[],help='Add rows only to existing groups while retaining original group budgets')
    a=p.parse_args()
    sources=json.loads((a.reference/'sources.json').read_text())
    rows=[r for s in sources for r in load_prepared(Path(s['prepared']))]
    with (a.reference/'reference-weights.csv').open() as f: reference=list(csv.reader(f))
    baseline=summarize(rows,reference)
    weights={int(i):int(w) for i,w,_ in reference};total=sum(weights.values())
    additional=None
    if a.additional_base:
        extra_manifest=json.loads((a.additional_base/'manifest.json').read_text())
        if extra_manifest['sourceHashes']['experiment-config.json'] != sources[0]['manifest']['sourceHashes']['experiment-config.json']:
            raise ValueError('Additional source configuration mismatch')
        extra=load_prepared(a.additional_base)
        added=[r for r in extra if r['entry']==0]
        if {r['id'] for r in rows}&{r['id'] for r in added}:raise ValueError('Overlapping round IDs')
        oldgroups={r['group'] for r in rows}
        if any(r['group'] not in oldgroups for r in added):raise ValueError('New group requires explicit budget')
        rows.extend(added)
        # Zero reference weights keep the original probability/mean budgets exactly.
        weights.update({r['id']:0 for r in added})
        additional=dict(prepared=str(a.additional_base.resolve()),manifest=extra_manifest,
            filter='entry == 0',included=len(added),excludedBonuses=len(extra)-len(added))
    supplements=[]
    for prepared in a.supplement:
        evidence=json.loads((prepared/'manifest.json').read_text())
        if evidence['sourceHashes']['experiment-config.json']!=sources[0]['manifest']['sourceHashes']['experiment-config.json']:
            raise ValueError('Supplement config mismatch')
        extra=load_prepared(prepared)
        oldgroups={r['group'] for r in rows}
        if any(r['group'] not in oldgroups for r in extra):raise ValueError('Supplement has unbudgeted groups')
        if {r['id'] for r in rows}&{r['id'] for r in extra}:raise ValueError('Supplement IDs overlap')
        rows.extend(extra);weights.update({r['id']:0 for r in extra})
        supplements.append(dict(prepared=str(prepared.resolve()),manifest=evidence,included=len(extra)))
    groups=defaultdict(list)
    for r in rows:groups[r['group']].append(r)
    fences=[];forces=[]
    for name,items in sorted(groups.items()):
        mass=sum(weights[r['id']] for r in items)
        mean=sum(weights[r['id']]*r['payout'] for r in items)/(mass*100)
        probability=mass/total
        search=[dict(name='wpGroup',value=name)]
        fences.append(dict(name=name,hr=str(1/probability),rtp=str(probability*mean),avg_win=str(mean),
            identity_condition=dict(search=search,opposite=False,win_range_start=-1,win_range_end=-1),
            min_mean_to_median='0',max_mean_to_median='1000000'))
        forces.append(dict(search=search,timesTriggered=len(items),bookIds=[r['id'] for r in items]))
    a.output.mkdir(parents=True,exist_ok=False)
    library=a.output/'games/wild_pickins/library'
    for folder in ('configs','forces','lookup_tables','publish_files','optimization_files'):(library/folder).mkdir(parents=True)
    write(library/'configs/math_config.json',dict(game_id='wild_pickins',bet_modes=[dict(bet_mode='base',cost=1,rtp=baseline['totalReturn'],max_win=5000)],
        fences=[dict(bet_mode='base',fences=fences)],dresses=[dict(bet_mode='base',dresses=[])],bias=[dict(bet_mode='base',bias=[])]))
    write(library/'forces/force_record_base.json',forces)
    with (library/'lookup_tables/lookUpTable_base.csv').open('w') as f:
        for r in rows:f.write(f"{r['id']},1,{r['payout']}\n")
    (a.output/'src').mkdir()
    setup=dict(game_name='wild_pickins',bet_type='base',path_to_games=str((a.output/'games').resolve()),
        num_show_pigs=40,num_pigs_per_fence=100,threads_for_fence_construction=2,threads_for_show_construction=2,
        score_type='rtp',test_spins=[50,100,200],test_spins_weights=[.3,.4,.3],simulation_trials=200,
        run_1000_batch=False,min_mean_to_median=0.,max_mean_to_median=1000000.,pmb_rtp=1.,max_trial_dist=15)
    (a.output/'src/setup.toml').write_text('\n'.join(f'{k} = {json.dumps(v)}' for k,v in setup.items()))
    write(a.output/'manifest.json',dict(status='running',sources=sources,additionalBase=additional,supplements=supplements,binarySha256=digest(a.binary),
        referenceWeightsSha256=digest(a.reference/'reference-weights.csv'),setup=setup,
        scope='Small stochastic feasibility search, not final optimization; whole-book group means fixed, components evaluated afterward.'))
    with (a.output/'optimizer.log').open('w') as log:
        process=subprocess.run([str(a.binary.resolve())],cwd=a.output,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    if process.returncode:raise RuntimeError(f'Optimizer failed: {process.returncode}; see optimizer.log')
    lookup=library/'publish_files/lookUpTable_base_0.csv'
    with lookup.open() as f: result=summarize(rows,csv.reader(f))
    metrics=('totalReturn','baseReturn','bonusReturn','baseHitRate','capProbability')
    comparison={k:dict(reference=baseline[k],rust=result[k],difference=result[k]-baseline[k]) for k in metrics}
    comparison['bonusEntry']=dict(reference=baseline['bonus']['probability'],rust=result['bonus']['probability'])
    comparison['entry10Middle']=dict(reference=baseline['entries']['10']['bands']['30to100'],rust=result['entries']['10']['bands']['30to100'])
    # Numerical budgets are predeclared for this diagnostic, not release criteria.
    checks=dict(totalReturn=abs(result['totalReturn']-.967)<.0001,
        baseReturn=abs(result['baseReturn']-.3868)<.0001,bonusReturn=abs(result['bonusReturn']-.5802)<.0001,
        baseHitRate=abs(result['baseHitRate']-.25)<.0001,
        bonusEntry=abs(result['bonus']['probability']-.01)<1e-8,
        entry10Middle=abs(result['entries']['10']['bands']['30to100']-.6)<1e-8,
        cap=abs(result['capProbability']-1e-7)<1e-10)
    write(a.output/'evaluation.json',dict(result,lookupSha256=digest(lookup),productionAccepted=False))
    write(a.output/'comparison.json',dict(metrics=comparison,checks=checks,
        tolerance='Return and base-hit absolute tolerance 0.0001; entry/band 1e-8; cap 1e-10',
        medianBonus=dict(reference=baseline['bonus']['medianX'],rust=result['bonus']['medianX'])))
    manifest=json.loads((a.output/'manifest.json').read_text());manifest['status']='complete';write(a.output/'manifest.json',manifest)
    print(json.dumps(dict(comparison=comparison,checks=checks,medianBonus=result['bonus']['medianX']),indent=2))

if __name__=='__main__':main()
