"""Replay explicit fixture board/target inputs through the new rule core and serialize C01."""
from pathlib import Path
from fractions import Fraction
from random import Random
import argparse
import json
import sys
from round_model import RoundModel
from book_export import BookExporter
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'wild-pickins/tools'))
from contract import validate

def export(source):
    b=json.loads(source.read_text());validate(b)
    model=RoundModel({i:p for i,p in enumerate(b['fixtureMath']['paths'],1)},
        {(c,int(n)):v for c,values in b['fixtureMath']['paytable'].items() for n,v in values.items()},
        b['roundCap'],b['spinBudget'],Fraction(0),Fraction(0),Random(0))
    output=BookExporter()
    for e in b['events']:
        if e['type']!='reveal':continue
        target=e['goldenTarget']
        r=model.spin(e['underlyingBoard'],fixture_target=(target['reel'],target['row']) if target else None)
        output.append(r,finished=model.ended,win_level=1)
    generated={**b,'mathVersion':'rule-core-fixture-replay-1','events':output.events}
    validate(generated)
    return generated

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    generated=export(args.source)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(generated,indent=2)+'\n')
    print(f'Exported and validated {len(generated["events"])} events: {args.output}')
