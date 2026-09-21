"""Isolated SDK optimizer bridge. Integration targets only, not production selection."""
import argparse
from collections import defaultdict
import csv
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import zstandard

from evaluate_experimental import summarize


def read_books(run):
    with (run/'books_base.jsonl.zst').open('rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader, io.TextIOWrapper(reader) as lines:
        return [json.loads(line) for line in lines]


def category(book, cap):
    if book['payoutMultiplier'] == cap:
        return 'maximum'
    if book['payoutMultiplier'] == 0:
        return 'zero'
    if any(e['type'] == 'freeSpinTrigger' for e in book['events']):
        return 'bonus'
    return 'base'


def prepare(run, output):
    config = json.loads((run/'experiment-config.json').read_text())
    if config.get('experimentalOnly') is not True:
        raise ValueError('Experimental source required')
    books = read_books(run)
    with (run/'lookUpTable_base.csv').open() as f:
        summarize(books, csv.reader(f))
    groups = defaultdict(list)
    for book in books:
        groups[category(book, config['roundCap'])].append(book)
    cap = config['roundCap']/100
    # Deliberately explicit integration allocations, not a medium-volatility prescription.
    targets = {'maximum': (.01, cap/.01), 'zero': (0, 'x'),
               'bonus': (.657, 40), 'base': (.3, 3)}
    fences, forces, coverage = [], [], {}
    for name, (rtp, hr) in targets.items():
        group = groups[name]
        if not group:
            raise ValueError(f'Missing outcome category: {name}')
        payouts = [b['payoutMultiplier']/100 for b in group]
        average = 0 if name == 'zero' else rtp*hr
        if not min(payouts) <= average <= max(payouts):
            raise ValueError(f'{name} target average {average} outside observed payout support')
        search = [dict(name='wpCategory', value=name)]
        forces.append(dict(search=search, timesTriggered=len(group), bookIds=[b['id'] for b in group]))
        exact = cap if name == 'maximum' else 0 if name == 'zero' else -1
        fences.append(dict(name=name, hr=str(hr), rtp=str(rtp), avg_win=str(average),
                           identity_condition=dict(search=[] if exact >= 0 else search, opposite=False,
                                                   win_range_start=exact, win_range_end=exact),
                           min_mean_to_median='0', max_mean_to_median='1000000'))
        coverage[name] = dict(books=len(group), distinctPayouts=len(set(payouts)), minimumX=min(payouts),
                              maximumX=max(payouts), targetReturnContribution=rtp, targetAverageX=average)
    output.mkdir(parents=True, exist_ok=False)
    library = output/'games/wild_pickins/library'
    for name in ('configs', 'forces', 'lookup_tables', 'optimization_files', 'publish_files'):
        (library/name).mkdir(parents=True)
    shutil.copyfile(run/'lookUpTable_base.csv', library/'lookup_tables/lookUpTable_base.csv')
    math_config = dict(game_id='wild_pickins', bet_modes=[dict(bet_mode='base', cost=1, rtp=.967, max_win=cap)],
                       fences=[dict(bet_mode='base', fences=fences)],
                       dresses=[dict(bet_mode='base', dresses=[])], bias=[dict(bet_mode='base', bias=[])])
    (library/'configs/math_config.json').write_text(json.dumps(math_config, indent=2)+'\n')
    (library/'forces/force_record_base.json').write_text(json.dumps(forces)+'\n')
    (output/'src').mkdir()
    setup = dict(game_name='wild_pickins', bet_type='base', path_to_games=str(output.resolve()/'games'),
                 num_show_pigs=20, num_pigs_per_fence=40, threads_for_fence_construction=1,
                 threads_for_show_construction=1, score_type='rtp', test_spins=[50,100,200],
                 test_spins_weights=[.3,.4,.3], simulation_trials=100, run_1000_batch=False,
                 min_mean_to_median=0.0, max_mean_to_median=1000000.0, pmb_rtp=1.0, max_trial_dist=15)
    (output/'src/setup.toml').write_text('\n'.join(f'{k} = {json.dumps(v)}' for k,v in setup.items())+'\n')
    (output/'integration.json').write_text(json.dumps(dict(experimentalOnly=True, source=str(run.resolve()),
        sourceBooksSha256=hashlib.sha256((run/'books_base.jsonl.zst').read_bytes()).hexdigest(),
        targetRtp=.967, targetVolatility='medium', categoryCoverage=coverage,
        warning='Integration allocations only. Broad search bounds do not define medium volatility. '
                'Small sample and sparse maximum-win coverage are not release-ready. SDK optimizer uses unseeded RNG.'), indent=2)+'\n')
    return books, config


def evaluate_weights(books, rows, cap):
    by_id = {b['id']: b for b in books}
    if len(by_id) != len(books):
        raise ValueError('Duplicate book ID')
    seen, weighted = set(), []
    for row in rows:
        identity, weight, amount = map(int, row)
        if identity in seen or identity not in by_id or weight < 0:
            raise ValueError('Invalid optimized ID/weight')
        seen.add(identity)
        if amount != by_id[identity]['payoutMultiplier']:
            raise ValueError('Optimizer changed a payout')
        weighted.append((by_id[identity], weight, amount))
    if seen != set(by_id):
        raise ValueError('Optimizer dropped book IDs')
    total = sum(w for _,w,_ in weighted)
    if total <= 0:
        raise ValueError('Empty weighted distribution')
    rtp = Fraction(sum(w*p for _,w,p in weighted), total*100)
    mean = float(rtp)
    categories = defaultdict(lambda: dict(probability=0, returnContribution=0))
    for book, weight, amount in weighted:
        entry = categories[category(book, cap)]
        entry['probability'] += weight/total
        entry['returnContribution'] += weight*amount/(100*total)
    return dict(experimentalOnly=True, totalWeight=total, weightedRtp=mean,
                exactRtpNumerator=rtp.numerator, exactRtpDenominator=rtp.denominator,
                targetGapPercentagePoints=(mean-.967)*100,
                weightedPayoutStdDev=math.sqrt(sum(w*(p/100-mean)**2 for _,w,p in weighted)/total),
                positiveWinRate=sum(w for _,w,p in weighted if p>0)/total,
                profitRate=sum(w for _,w,p in weighted if p>100)/total,
                zeroWeightBooks=sum(w==0 for _,w,_ in weighted), categories=dict(categories),
                note='Exact statistics of this finite weighted table; not medium-volatility approval or platform certification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path, help='Built SDK PigFarmRust executable; omit to prepare inputs only')
    args = parser.parse_args()
    books, config = prepare(args.source, args.output)
    if args.binary:
        with (args.output/'optimizer.log').open('w') as log:
            subprocess.run([str(args.binary.resolve())], cwd=args.output, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=180)
        with (args.output/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv').open() as f:
            report = evaluate_weights(books, csv.reader(f), config['roundCap'])
        (args.output/'weighted-evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    else:
        print(f'Prepared isolated optimizer inputs at {args.output}')


if __name__ == '__main__':
    main()
