"""Decompose entered-bonus payouts from an archived complete-round report."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def summarize(report):
    hist=Counter()
    for row in report['metrics']['sufficientStatistics']['bonusRows']:
        hist[row['values'][0]]+=row['count']
    entries=sum(hist.values());cash=sum(v*n for v,n in hist.items());paid=report['rounds']
    assert entries==report['metrics']['bonus']['entryRate']['hits']
    assert abs(cash/(paid*100)-report['bonusContribution'])<1e-10
    bands=[]
    for label,lo,hi in [('Below 10x',0,1000),('10–under 30x',1000,3000),('30–under 100x',3000,10000),('100–under 500x',10000,50000),('500x+',50000,None)]:
        count=sum(n for v,n in hist.items() if lo<=v and (hi is None or v<hi))
        amount=sum(v*n for v,n in hist.items() if lo<=v and (hi is None or v<hi))
        bands.append(dict(band=label,count=count,frequency=count/entries if entries else None,meanWithinBandX=amount/(count*100) if count else None,shareOfBonusCash=amount/cash if cash else None,contributionToMeanBonusX=amount/(entries*100) if entries else None,returnContribution=amount/(paid*100)))
    assert sum(b['count'] for b in bands)==entries
    thresholds={str(x):dict(count=sum(n for v,n in hist.items() if v>=x*100),frequency=sum(n for v,n in hist.items() if v>=x*100)/entries if entries else None) for x in (200,500,1000,5000)}
    # Illustrative budget only: top up weak payouts while leaving every other payout fixed.
    costs={str(floor):sum(max(0,floor*100-v)*n for v,n in hist.items())/(100*entries) if entries else None for floor in (30,50)}
    return dict(paidRounds=paid,bonusEntries=entries,meanBonusX=cash/(100*entries) if entries else None,bonusReturn=cash/(100*paid),bands=bands,tailThresholds=thresholds,roundCapHits=report["metrics"]["capHitRate"]["hits"],hypotheticalFloorExtraMeanX=costs,note='Descriptive sample decomposition, not a proposed payout floor or final tail estimate. Bands include zero payouts and use settled bonus cash; base payouts excluded.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.report.read_bytes();out=summarize(json.loads(raw));out.update(source=str(a.report),sourceSha256=hashlib.sha256(raw).hexdigest())
    with a.output.open('x') as f:f.write(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
