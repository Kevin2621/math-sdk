"""Experimental seeded generator using the rule core and SDK Book/lookup writer.

Not an optimizer, production math configuration, or publish command.
"""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
from random import Random
from types import SimpleNamespace
import hashlib
import json
import sys
import zstandard
from src.state.books import Book
from src.write_data.write_data import make_lookup_tables
from round_model import RoundModel
from reel_source import ReelSource
from book_export import BookExporter
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'wild-pickins/tools'))
from contract import validate

def generate_round(config,seed,round_id):
    if config.get('experimentalOnly') is not True: raise ValueError('Explicit experimental config required')
    sources={mode:ReelSource(config['reels'][mode]) for mode in ('basegame','freegame')}
    rng=Random(f'wild-pickins:{seed}:{round_id}')
    fm=config['fixtureMath']
    model=RoundModel({i:p for i,p in enumerate(fm['paths'],1)},
        {(c,int(n)):v for c,vals in fm['paytable'].items() for n,v in vals.items()},
        config['roundCap'],config['spinBudget'],Fraction(*config['goldenRates']['basegame']),
        Fraction(*config['goldenRates']['freegame']),rng,
        bonus_paytable={(c,int(n)):v for c,vals in fm['bonusPaytable'].items() for n,v in vals.items()} if 'bonusPaytable' in fm else None)
    exporter=BookExporter()
    while not model.ended:
        sample=sources[model.mode].draw(rng)
        result=model.spin(sample.board)  # No fixture target override.
        exporter.append(result,finished=model.ended,win_level=config['winLevel'],reel_sample=sample)
    envelope={k:config[k] for k in ('schemaVersion','gameId','lineSetId','mathVersion','assetMapVersion','spinBudget','roundCap','fixtureMath')}
    envelope.update(fixtureOnly=True,events=exporter.events)
    validate(envelope)
    sdk=Book(round_id,'experimental')
    for event in exporter.events: sdk.add_event(event)
    sdk.payout_multiplier=model.total/100
    sdk.basegame_wins=(model.total-model.bonus_total)/100
    sdk.freegame_wins=model.bonus_total/100
    output=sdk.to_json()
    # SDK Book uses float scaling; assert exact agreement at the boundary.
    if output['payoutMultiplier']!=model.total: raise ValueError('SDK monetary conversion mismatch')
    return output,envelope

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--rounds',type=int,required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.rounds<=1000000: parser.error('Experimental runner supports 1–1000000 rounds')
    config=json.loads(args.config.read_text())
    # Refuse overwriting evidence or mixing runs.
    args.output.mkdir(parents=True,exist_ok=False)
    library={};counts=Counter();sample=None
    with (args.output/'books_base.jsonl.zst').open('wb') as raw:
        with zstandard.ZstdCompressor().stream_writer(raw) as writer:
            for i in range(args.rounds):
                book,envelope=generate_round(config,args.seed,i)
                writer.write((json.dumps(book,separators=(',',':'))+'\n').encode())
                library[i]={'id':book['id'],'payoutMultiplier':book['payoutMultiplier']}
                counts.update(e['type'] for e in book['events'])
                if (i+1)%10000==0: print(f'Validated and wrote {i+1}/{args.rounds} rounds',flush=True)
                if sample is None or (not any(e['type']=='freeSpinTrigger' for e in sample['events']) and any(e['type']=='freeSpinTrigger' for e in envelope['events'])):sample=envelope
    make_lookup_tables(SimpleNamespace(library=library),str(args.output/'lookUpTable_base.csv'))
    (args.output/'sample-book.json').write_text(json.dumps(sample,indent=2)+'\n')
    (args.output/'experiment-config.json').write_text(json.dumps(config,indent=2)+'\n')
    payouts=[b['payoutMultiplier'] for b in library.values()]
    report=dict(experimentalOnly=True,seed=args.seed,rounds=args.rounds,configSha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
        mode='base',cost=1,eventCounts=dict(counts),observedMeanReturn=sum(payouts)/(100*len(payouts)),
        nonzeroRounds=sum(v>0 for v in payouts),maximumObservedBookAmount=max(payouts),
        note='Unoptimized equal-weight experimental sample; not approved RTP, theoretical model, platform acceptance or release artifacts.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
