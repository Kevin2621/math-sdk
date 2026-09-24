"""Exact count-based base line expectation for independent cyclic uniform stops."""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from itertools import product
import json
from pathlib import Path
from line_model import CROPS, evaluate_lines
from reel_source import ReelSource


@lru_cache(maxsize=None)
def outcome(tokens, table_items):
    board=[[symbol]*3 for symbol,value in tokens]
    wilds={(r,y):value for r,(symbol,value) in enumerate(tokens) if symbol=='W' for y in range(3)}
    result=evaluate_lines(board,{1:[0]*5},dict(table_items),wilds)
    if not result.awards:return None
    a=result.awards[0]
    return a.crop,a.count,a.multiplier,a.amount


def calculate(config):
    if config['goldenRates']['basegame'][0]!=0:raise ValueError('Exact model requires Golden Picks off')
    reels=ReelSource(config['reels']['basegame']).strips
    fm=config['fixtureMath'];weights=fm['wildMultiplierWeights']
    if len(weights)!=3 or any(type(w) is not int or w<0 for w in weights) or sum(weights)<=0:raise ValueError('Invalid Wild weights')
    table=tuple(sorted(((s,int(n)),v) for s,p in fm['paytable'].items() for n,v in p.items()))
    # Validate map and table using the production evaluator.
    evaluate_lines([['C01']*3 for _ in range(5)],dict(enumerate(fm['paths'],1)),dict(table),{})
    bound=len(fm['paths'])*max(v for k,v in table)*15
    if bound>config['roundCap']:raise ValueError('Potential base cap clipping requires board-level calculation')
    options=[];denominator=1
    for strip in reels:
        c=Counter(strip);total=sum(weights);denominator*=len(strip)*total
        options.append([( (s,0),n*total) for s,n in sorted(c.items()) if s!='W']+
            [(('W',i+1),c['W']*w) for i,w in enumerate(weights) if w and c['W']])
    mass=Counter();win_mass=0
    for first in product(*options[:3]):
        prefix=tuple(t for t,m in first)
        if not any(all(s in (crop,'W') for s,v in prefix) for crop in CROPS):continue
        for last in product(*options[3:]):
            tokens=prefix+tuple(t for t,m in last)
            award=outcome(tokens,table)
            if award is None:continue
            probability_mass=1
            for token,m in first+last:probability_mass*=m
            mass[award[:3]]+=probability_mass*award[3];win_mass+=probability_mass
    lines=len(fm['paths']);expected=Fraction(sum(mass.values())*lines,denominator*100)
    return dict(method='Exact rational enumeration of single-line symbol and Wild-value outcomes; sum of line expectations',
        baseReturn=float(expected),baseReturnFraction=str(expected),singleLinePositiveProbability=float(Fraction(win_mass,denominator)),
        lineCount=lines,baseAwardUpperBoundX=bound/100,
        contributions=[dict(symbol=s,matchLength=n,wildMultiplier=w,baseReturn=float(Fraction(v*lines,denominator*100))) for (s,n,w),v in sorted(mass.items())],
        limitations='Does not calculate whole-board positive frequency, bonus return or volatility. Line events overlap; do not multiply single-line hit probability by line count to infer paying-spin frequency.')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.config.read_bytes();c=json.loads(raw);r=calculate(c)
    import hashlib
    r.update(config=c,configSha256=hashlib.sha256(raw).hexdigest())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
    print(r['baseReturn'])
