"""Current accumulation-game optimizer labels and exact weighted diagnostics.

Prepare does not run the optimizer, choose a budget, publish, or activate a game.
Amounts in metadata are integer hundredths of the total bet.
"""
import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import zstandard
from generate_experimental import ROOT
from contract import validate


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def band(amount):
    for limit, name in [(1000, 'below10'), (3000, '10to30'), (10000, '30to100'),
                        (50000, '100to500')]:
        if amount < limit:
            return name
    return '500plus'


def labels(book, cap):
    events = book['events']
    spins = [e for e in events if e['type'] == 'wildPickinsSpinResult']
    triggers = [e for e in events if e['type'] == 'freeSpinTrigger']
    if not spins or len(triggers) > 1:
        raise ValueError('Expected one complete paid round without scatter retriggers')
    entry = triggers[0]['totalFs'] if triggers else 0
    if entry not in (0, 10, 15, 20) or (not entry and len(spins) != 1):
        raise ValueError('Invalid entry award or bonus sequence')
    base = spins[0]['spinWin']
    bonus = sum(s['spinWin'] for s in spins[1:])
    total = book['payoutMultiplier']
    if (any(type(s['spinWin']) is not int or s['spinWin'] < 0 for s in spins)
            or base + bonus != total or not 0 <= total <= cap
            or events[-1]['type'] != 'finalWin' or events[-1]['amount'] != total):
        raise ValueError('Settled components do not match final payout')
    if any(s['harvestTopUp'] or s['endReason'] == 'fullHarvest' for s in spins):
        raise ValueError('Historical Full Harvest books are not supported')
    base_status = 'zero' if base == 0 else 'ldw' if base < 100 else 'breakEven' if base == 100 else 'profit'
    capped = total == cap
    group = f'entry{entry}_{"cap" if capped else band(bonus)}' if entry else f'base_{"cap" if capped else base_status}'
    progression = []
    previous = 0
    for i, spin in enumerate(spins[1:], 1):
        sticky = len(spin['stickyAfter'])
        progression.append(dict(spin=i, sticky=sticky, newWilds=sticky-previous,
            collisions=spin['nominalCollisionAward'], extraSpins=spin['grantedExtraSpins'],
            payout=spin['spinWin']))
        previous = sticky
    return dict(id=book['id'], payout=total, base=base, bonus=bonus, entry=entry,
        group=group, bonusBand=band(bonus) if entry else None, cap=capped, baseStatus=base_status,
        firstWild=next((p['spin'] for p in progression if p['sticky']), None),
        duration=len(progression), deadSpins=sum(p['payout'] == 0 for p in progression),
        progression=progression)


def read_source(source):
    config = json.loads((source/'experiment-config.json').read_text())
    if (config.get('experimentalOnly') is not True
            or config['fixtureMath'].get('settlementPolicy') != 'accumulation'):
        raise ValueError('Current experimental accumulation config required')
    rows = []
    with (source/'books_base.jsonl.zst').open('rb') as raw, \
            zstandard.ZstdDecompressor().stream_reader(raw) as stream, \
            io.TextIOWrapper(stream) as lines, (source/'lookUpTable_base.csv').open() as lookup:
        for line, row in zip(lines, csv.reader(lookup), strict=True):
            book = json.loads(line)
            envelope = {k: config[k] for k in ('schemaVersion','gameId','lineSetId','mathVersion',
                'assetMapVersion','spinBudget','roundCap','fixtureMath')}
            validate(dict(envelope, fixtureOnly=True, events=book['events']))
            if list(map(int, row)) != [book['id'], 1, book['payoutMultiplier']]:
                raise ValueError('Expected matching uniform source lookup')
            rows.append(labels(book, config['roundCap']))
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Empty pool or duplicate IDs')
    return config, rows


def summarize(rows, lookup):
    by_id = {r['id']: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError('Duplicate metadata IDs')
    weights = {}
    for fields in lookup:
        if len(fields) != 3:
            raise ValueError('Expected ID, integer weight, payout')
        i, w, p = map(int, fields)
        if i not in by_id or i in weights or w < 0 or p != by_id[i]['payout']:
            raise ValueError('Invalid lookup ID, weight or payout')
        weights[i] = w
    if set(weights) != set(by_id) or not sum(weights.values()):
        raise ValueError('Missing IDs or empty distribution')
    total = sum(weights.values())
    def mass(sub): return sum(weights[r['id']] for r in sub)
    def mean(sub, key, denominator):
        return float(Fraction(sum(weights[r['id']]*r[key] for r in sub), denominator)) if denominator else None
    def conditional(sub):
        m = mass(sub)
        hist = Counter()
        for r in sub: hist[r['bonus']] += weights[r['id']]
        median = None
        cumulative = 0
        for amount, w in sorted(hist.items()):
            cumulative += w
            if m and 2*cumulative >= m:
                median = amount/100
                break
        progression = []
        for spin in range(1, max((r['duration'] for r in sub), default=0)+1):
            alive = [r for r in sub if r['duration'] >= spin]
            alive_mass = mass(alive)
            item = dict(spin=spin, reachProbability=alive_mass/m if m else None)
            for field in ('sticky', 'newWilds', 'collisions', 'extraSpins', 'payout'):
                item[field] = (sum(weights[r['id']]*r['progression'][spin-1][field] for r in alive)/alive_mass
                    if alive_mass else None)
            progression.append(item)
        return dict(probability=m/total, meanX=mean(sub,'bonus',m*100), medianX=median,
            bands={b:mass([r for r in sub if r['bonusBand']==b])/m if m else None
                for b in ('below10','10to30','30to100','100to500','500plus')},
            tailProbability={str(x):mass([r for r in sub if r['bonus']>=x*100])/m if m else None for x in (500,1000,5000)},
            roundCapProbability=mass([r for r in sub if r['cap']])/m if m else None,
            noWildFirstThree=mass([r for r in sub if r['firstWild'] is None or r['firstWild']>3])/m if m else None,
            meanDuration=mean(sub,'duration',m), meanDeadSpins=mean(sub,'deadSpins',m),
            progressionConditionalOnReachingSpin=progression)
    bonus = [r for r in rows if r['entry']]
    exact = Fraction(sum(weights[r['id']]*r['payout'] for r in rows),total*100)
    return dict(totalWeight=total, rounds=len(rows), exactReturn=str(exact), totalReturn=float(exact),
        baseReturn=mean(rows,'base',total*100), bonusReturn=mean(rows,'bonus',total*100),
        baseHitRate=mass([r for r in rows if r['base']>0])/total,
        baseStatusProbabilities={s:mass([r for r in rows if r['baseStatus']==s])/total for s in ('zero','ldw','breakEven','profit')},
        capProbability=mass([r for r in rows if r['cap']])/total,
        groups={g:mass([r for r in rows if r['group']==g])/total for g in sorted({r['group'] for r in rows})},
        bonus=conditional(bonus), entries={str(e):conditional([r for r in bonus if r['entry']==e]) for e in (10,15,20)},
        effectiveBookCount=total**2/sum(w*w for w in weights.values()),
        largestBookProbability=max(weights.values())/total,
        top100BookProbability=sum(sorted(weights.values(),reverse=True)[:100])/total,
        zeroWeightBooks=sum(w==0 for w in weights.values()))


def prepare(source, output):
    config, rows = read_source(source)
    groups = defaultdict(list)
    for row in rows: groups[row['group']].append(row)
    output.mkdir(parents=True, exist_ok=False)
    write(output/'metadata.json',rows)
    write(output/'force-records.json',[dict(search=[dict(name='wpGroup',value=g)],
        timesTriggered=len(items),bookIds=[r['id'] for r in items]) for g,items in sorted(groups.items())])
    coverage = {g:dict(books=len(items), distinctPayouts=len({r['payout'] for r in items}),
        minimumTotalX=min(r['payout'] for r in items)/100,maximumTotalX=max(r['payout'] for r in items)/100)
        for g,items in sorted(groups.items())}
    write(output/'coverage.json',dict(groups=coverage,
        missingBonusGroups=[f'entry{e}_{b}' for e in (10,15,20)
            for b in ('below10','10to30','30to100','100to500','500plus','cap')
            if f'entry{e}_{b}' not in groups]))
    baseline=summarize(rows,[(r['id'],1,r['payout']) for r in rows])
    if (source/'sampling.json').exists():
        baseline['sampling']=json.loads((source/'sampling.json').read_text())
        baseline['interpretation']='Conditional targeted sample, not natural paid-game RTP or entry rates'
    write(output/'uniform-evaluation.json',baseline)
    write(output/'manifest.json',dict(source=str(source.resolve()),experimentalOnly=True,
        sourceHashes={name:digest(source/name) for name in (('experiment-config.json','books_base.jsonl.zst','lookUpTable_base.csv','sampling.json') if (source/'sampling.json').exists() else ('experiment-config.json','books_base.jsonl.zst','lookUpTable_base.csv'))},
        artifactHashes={name:digest(output/name) for name in ('metadata.json','force-records.json','coverage.json')},
        toolSha256=digest(Path(__file__)), roundCap=config['roundCap'],
        note='Labels and diagnostics only. No target budget selected, optimizer run, or gameplay activation.'))


def load_prepared(path):
    manifest=json.loads((path/'manifest.json').read_text())
    for folder, key in ((Path(manifest['source']),'sourceHashes'),(path,'artifactHashes')):
        for name, expected in manifest[key].items():
            if digest(folder/name)!=expected: raise ValueError(f'Changed evidence: {name}')
    return json.loads((path/'metadata.json').read_text())


def check_targets(rows, targets):
    """Necessary per-group support checks, not a component-constrained feasibility proof."""
    groups = defaultdict(list)
    for r in rows: groups[r['group']].append(r)
    if set(targets['groups']) != set(groups):
        raise ValueError('Targets must cover exactly the observed groups')
    probability = Fraction(0); contribution = Fraction(0); fences=[]
    for name, target in targets['groups'].items():
        p=Fraction(str(target['probability'])); mean=Fraction(str(target['meanTotalX']))
        if not 0 < p <= 1: raise ValueError('Each fence needs positive probability; zero groups require separate handling')
        values=[Fraction(r['payout'],100) for r in groups[name]]
        if not min(values)<=mean<=max(values): raise ValueError(f'{name}: mean outside observed support')
        probability+=p; contribution+=p*mean
        fences.append(dict(name=name,hr=str(float(1/p)),rtp=str(float(p*mean)),avg_win=str(float(mean)),
            identity_condition=dict(search=[dict(name='wpGroup',value=name)],opposite=False,
                win_range_start=-1,win_range_end=-1),min_mean_to_median='0',max_mean_to_median='1000000'))
    if probability != 1: raise ValueError('Group probabilities must sum exactly to one')
    if contribution != Fraction(str(targets['totalReturn'])): raise ValueError('Group contributions do not equal target return')
    return dict(fences=fences,totalReturn=float(contribution),
        singlePayoutGroups=[g for g,items in groups.items() if len({r['payout'] for r in items})==1],
        runnableOptimizerConfig=False,
        integrationNote='Single-payout metadata groups are supported by the patched local Rust optimizer. Rebuild before use; this is still a fence draft, not a complete executable setup or component-feasibility proof.',
        status='Necessary support checks passed; component constraints and Rust convergence not established')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    for name in ('evaluate','check-targets'):
        p=sub.add_parser(name);p.add_argument('--prepared',type=Path,required=True)
        p.add_argument('--lookup' if name=='evaluate' else '--targets',type=Path,required=True)
        p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Refusing to overwrite evidence')
    if args.command=='prepare': prepare(args.source,args.output)
    else:
        rows=load_prepared(args.prepared)
        if args.command=='evaluate':
            with args.lookup.open() as f: result=summarize(rows,csv.reader(f))
            result.update(lookupSha256=digest(args.lookup),productionAccepted=False)
            manifest=json.loads((args.prepared/'manifest.json').read_text())
            sampling=Path(manifest['source'])/'sampling.json'
            if sampling.exists():
                result['sampling']=json.loads(sampling.read_text())
                result['interpretation']='Targeted entry stratum; not a complete natural paid-game distribution'
        else: result=check_targets(rows,json.loads(args.targets.read_text()))
        write(args.output,result)

if __name__=='__main__': main()
