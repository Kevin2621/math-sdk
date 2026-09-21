"""Audit and collect diverse rule-valid books by rejection sampling, not payout editing."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import zstandard
from generate_experimental import generate_round

MECHANICS = {
    'base-loss', 'base-win', 'golden-win', 'golden-no-line-win',
    'entry-3', 'entry-4', 'entry-5', 'retrigger-3', 'retrigger-4', 'retrigger-5',
    'collision', 'multiple-collisions', 'combined-awards', 'budget-clipping',
    'hidden-scatter', 'last-spin-extension', 'normal-bonus-end',
    'full-harvest', 'round-cap', 'no-eligible-golden-target',
}
PAYOUTS = {'payout-zero', 'payout-under-1x', 'payout-1-to-5x', 'payout-5-to-20x',
           'payout-20-to-100x', 'payout-100x-plus'}


def labels(book):
    tags = set()
    amount = book['payoutMultiplier']
    tags.add('payout-zero' if amount == 0 else 'payout-under-1x' if amount < 100 else
             'payout-1-to-5x' if amount < 500 else 'payout-5-to-20x' if amount < 2000 else
             'payout-20-to-100x' if amount < 10000 else 'payout-100x-plus')
    events = book['events']
    has_bonus = any(e['type'] == 'freeSpinTrigger' for e in events)
    if not has_bonus:
        tags.add('base-win' if amount else 'base-loss')
    reveals = {e['spinId']: e for e in events if e['type'] == 'reveal'}
    picks = {e['spinId'] for e in events if e['type'] == 'goldenCropPick'}
    remaining = 0
    for event in events:
        if event['type'] == 'freeSpinTrigger':
            tags.add(f"entry-{len(event['positions'])}")
            remaining = event['totalFs']
        if event['type'] != 'wildPickinsSpinResult':
            continue
        spin = event['spinId']
        reveal = reveals[spin]
        before = {(p['reel'], p['row']) for p in reveal['stickyBefore']}
        underlying = reveal['underlyingBoard']
        if any(underlying[r][y] == 'S' for r,y in before):
            tags.add('hidden-scatter')
        if not any(s.startswith('C') and (r,y) not in before
                   for r,reel in enumerate(underlying) for y,s in enumerate(reel)):
            tags.add('no-eligible-golden-target')
        if spin in picks:
            # This reports co-occurrence, not whether the pick caused the line win.
            tags.add('golden-win' if event['lineWin'] else 'golden-no-line-win')
        if not spin:
            continue
        collision, retrigger = event['nominalCollisionAward'], event['nominalRetriggerAward']
        if collision:
            tags.add('collision')
        if len(event['collisionPositions']) > 1:
            tags.add('multiple-collisions')
        if retrigger:
            tags.add(f"retrigger-{len(event['scatterPositions'])}")
        if collision and retrigger:
            tags.add('combined-awards')
        if event['endReason'] not in ('fullHarvest','roundCap') and event['grantedExtraSpins'] < collision+retrigger:
            tags.add('budget-clipping')
        if remaining == 1 and event['grantedExtraSpins']:
            tags.add('last-spin-extension')
        remaining = event['remaining']
        reason = event['endReason']
        if reason:
            tags.add({'fullHarvest':'full-harvest', 'roundCap':'round-cap',
                      'spinsExhausted':'normal-bonus-end'}[reason])
    # A cap may also terminate a base round.
    if any(e.get('endReason') == 'roundCap' for e in events):
        tags.add('round-cap')
    return tags


def read_books(path):
    with path.open('rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader, io.TextIOWrapper(reader) as lines:
        for line in lines:
            yield json.loads(line)


def fingerprint(book):
    return hashlib.sha256(json.dumps(book['events'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit(books, quota):
    counts, examples, seen = Counter(), {}, set()
    total = 0
    visual_counts, payout_counts = Counter(), Counter()
    for book in books:
        total += 1
        # Board-sequence diversity ignores stops/padding and event metadata.
        boards = [e['finalBoard'] for e in book['events'] if e['type']=='wildPickinsSpinResult']
        visual_key = hashlib.sha256(json.dumps(boards,separators=(',', ':')).encode()).hexdigest()
        visual_counts[visual_key] += 1
        payout_counts[book['payoutMultiplier']] += 1
        key = fingerprint(book)
        if key in seen:
            continue
        seen.add(key)
        tags = labels(book)
        counts.update(tags)
        for tag in tags:
            examples.setdefault(tag, book['id'])
    return dict(books=total, distinctEventSequences=len(seen), distinctFinalBoardSequences=len(visual_counts),
                mostRepeatedFinalBoardSequenceCount=max(visual_counts.values(),default=0),
                distinctPayoutAmounts=len(payout_counts),
                minimumDistinctBooksPerLabel=quota,
                coverage={tag: dict(count=counts[tag], exampleBookId=examples.get(tag),
                                   missingToQuota=max(0,quota-counts[tag])) for tag in sorted(MECHANICS|PAYOUTS)},
                note='Labels overlap. Payout buckets are lower-inclusive and upper-exclusive. '
                     'Golden win means pick and line payout coexist, not causation. '
                     'Missing sampled outcomes are not proven impossible. Coverage is not exhaustive or production approval.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=20000)
    parser.add_argument('--quota', type=int, default=10)
    parser.add_argument('--seed', type=int, default=45)
    args = parser.parse_args()
    if bool(args.source) == bool(args.config) or args.quota < 1 or not 1 <= args.attempts <= 100000:
        parser.error('Use source or config; positive quota and 1–100000 attempts required')
    args.output.mkdir(parents=True, exist_ok=False)
    if args.source:
        report = audit(read_books(args.source), args.quota)
        report['source'] = str(args.source.resolve())
    else:
        config = json.loads(args.config.read_text())
        counts, seen, accepted, provenance = Counter(), set(), [], []
        for attempt in range(args.attempts):
            book, _ = generate_round(config, args.seed, attempt)
            tags = labels(book)
            if not any(counts[tag] < args.quota for tag in tags):
                continue
            key = fingerprint(book)
            if key in seen:
                continue
            seen.add(key)
            source_id = book['id']
            book['id'] = len(accepted)
            accepted.append(book)
            counts.update(tags)
            provenance.append(dict(bookId=book['id'], sourceRoundId=source_id, labels=sorted(tags), eventsSha256=key))
            if all(counts[tag] >= args.quota for tag in MECHANICS|PAYOUTS):
                break
        with (args.output/'books_base.jsonl.zst').open('wb') as raw, zstandard.ZstdCompressor().stream_writer(raw) as writer:
            for book in accepted:
                writer.write((json.dumps(book,separators=(',',':'))+'\n').encode())
        (args.output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        (args.output/'experiment-config.json').write_text(json.dumps(config,indent=2)+'\n')
        report = audit(accepted, args.quota)
        report.update(seed=args.seed, attemptedRounds=attempt+1, targetedSelection=True,
                      configSha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                      probabilityWarning='Selected for coverage. No probability weights or RTP estimate assigned.')
    (args.output/'coverage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
