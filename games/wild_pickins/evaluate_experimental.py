"""Reconcile and describe equal-weight experimental books; not platform certification."""
import argparse
import csv
import io
import json
import math
from pathlib import Path
from statistics import mean, stdev

import zstandard


def summarize(books, rows):
    payouts, durations, sticky_counts = [], [], []
    base_lines = bonus_lines = harvest = 0
    full = cap = nominal_retrigger = nominal_collision = granted = budget_hits = 0
    seen = set()
    for book, row in zip(books, rows, strict=True):
        identity, weight, amount = map(int, row)
        if weight != 1:
            raise ValueError('Only equal-weight sampled runs are supported')
        if identity in seen or identity != book['id'] or amount != book['payoutMultiplier']:
            raise ValueError('Duplicate ID or lookup/book mismatch')
        seen.add(identity)
        events = book['events']
        if events[-1]['type'] != 'finalWin' or events[-1]['amount'] != amount:
            raise ValueError('Final payout mismatch')
        results = [e for e in events if e['type'] == 'wildPickinsSpinResult']
        if sum(e['lineWin'] + e['harvestTopUp'] for e in results) != amount:
            raise ValueError('Payout component mismatch')
        bonus = [e for e in results if e['spinId'] > 0]
        base_lines += sum(e['lineWin'] for e in results if e['spinId'] == 0)
        bonus_lines += sum(e['lineWin'] for e in bonus)
        harvest += sum(e['harvestTopUp'] for e in results)
        full += any(e['endReason'] == 'fullHarvest' for e in results)
        cap += any(e['endReason'] == 'roundCap' for e in results)
        if bonus:
            durations.append(len(bonus))
            sticky_counts.extend(len(e['stickyAfter']) for e in bonus)
        nominal_retrigger += sum(e['nominalRetriggerAward'] for e in bonus)
        nominal_collision += sum(e['nominalCollisionAward'] for e in bonus)
        granted += sum(e['grantedExtraSpins'] for e in bonus)
        # Only count budget clipping while the round is still eligible for additions.
        budget_hits += any(e['endReason'] not in ('fullHarvest', 'roundCap') and
            e['grantedExtraSpins'] < e['nominalRetriggerAward'] + e['nominalCollisionAward'] for e in bonus)
        payouts.append(amount / 100)
    if not payouts:
        raise ValueError('Empty sample')
    n = len(payouts)
    ordered = sorted(durations)
    def duration_quantile(p):
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)] if ordered else None
    return dict(
        experimentalOnly=True, rounds=n, observedReturn=mean(payouts),
        targetReturn=0.967, targetVolatility='medium',
        returnGapPercentagePoints=(mean(payouts)-0.967)*100,
        samplePayoutStdDev=stdev(payouts) if n > 1 else None,
        positiveWinRate=sum(p > 0 for p in payouts)/n,
        profitRate=sum(p > 1 for p in payouts)/n,
        maximumObservedPayoutX=max(payouts),
        returnContributions=dict(baseLines=base_lines/(100*n), bonusLines=bonus_lines/(100*n),
                                 harvestTopUps=harvest/(100*n)),
        bonusRounds=len(durations), bonusRate=len(durations)/n,
        bonusDuration=dict(mean=mean(durations) if durations else None,
                           p50=duration_quantile(.5), p95=duration_quantile(.95),
                           maximum=max(durations) if durations else None),
        fullHarvestRounds=full, roundCapRounds=cap,
        meanStickyCellsPerBonusSpin=mean(sticky_counts) if sticky_counts else None,
        extraSpins=dict(nominalRetrigger=nominal_retrigger, nominalCollision=nominal_collision,
                        actuallyGranted=granted, roundsWithBudgetClipping=budget_hits),
        limitation='Empirical equal-weight sample only. Rare tails and theoretical RTP are not established. '
                   'Award counts do not measure causal retrigger/collision payout cost. '
                   'Quantiles use nearest rank; no platform risk certification or volatility classification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    with (args.run/'books_base.jsonl.zst').open('rb') as raw, \
            zstandard.ZstdDecompressor().stream_reader(raw) as reader, \
            io.TextIOWrapper(reader) as lines, \
            (args.run/'lookUpTable_base.csv').open() as lookup:
        report = summarize((json.loads(line) for line in lines), csv.reader(lookup))
    source = json.loads((args.run/'report.json').read_text())
    report['seed'] = source['seed']
    report['configSha256'] = source['configSha256']
    (args.run/'evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
