"""Payline attribution before clipping; aggregate settled cash reconciles separately."""
from collections import Counter, defaultdict


class PaylineMetrics:
    def __init__(self, paths):
        self.paths=paths
        self.categories=defaultdict(Counter)
        self.spins=Counter();self.cash=defaultdict(Counter);self.rows=defaultdict(Counter)

    def spin(self, result):
        mode=result['gameType'];self.spins[mode]+=1
        nominal=0
        tiers=set()
        for award in result['lines'].awards:
            tiers.add("high" if award.crop in ("C01","C02","C03") else "low")
            positions=award.positions
            pattern=tuple(result['finalBoard'][r][y] for r,y in positions)
            wilds=tuple((r,y,result.get('wildMultipliers',{}).get((r,y),1)) for r,y in positions if result['finalBoard'][r][y]=='W')
            key=(mode,award.line_id,award.crop,award.count,award.multiplier,pattern,wilds)
            row=self.rows[key];row['hits']+=1;row['nominalBookAmount']+=award.amount
            row['unmultipliedBookAmount']+=award.base_amount;nominal+=award.amount
        category='mixed' if len(tiers)==2 else 'highOnly' if 'high' in tiers else 'lowOnly' if 'low' in tiers else 'noLineWin'
        self.categories[mode][category]+=1
        settled=result.get('lineWin',nominal)
        if not 0<=settled<=nominal:raise ValueError('Line settlement outside nominal award')
        self.cash[mode].update(nominalBookAmount=nominal,settledBookAmount=settled,clippedBookAmount=nominal-settled)

    def report(self, paid_rounds):
        detail=[]
        for (mode,line,symbol,length,multiplier,pattern,wilds),counts in sorted(self.rows.items()):
            detail.append(dict(mode=mode,lineId=line,path=self.paths[line-1],symbol=symbol,
                matchLength=length,wildMultiplier=multiplier,matchedSymbols=list(pattern),
                wildPositionsAndValues=[list(w) for w in wilds],**counts,
                hitsPerModeSpin=counts['hits']/self.spins[mode],
                nominalReturnContribution=counts['nominalBookAmount']/100/paid_rounds if paid_rounds else None))
        def grouped(fields):
            groups=defaultdict(Counter)
            for row in detail:
                key=tuple(row[f] for f in fields)
                groups[key].update({k:row[k] for k in ('hits','nominalBookAmount','unmultipliedBookAmount')})
            return [dict(zip(fields,key),**counts,nominalReturnContribution=counts['nominalBookAmount']/100/paid_rounds if paid_rounds else None)
                    for key,counts in sorted(groups.items())]
        return dict(units='100 book units per original total wager',paidRounds=paid_rounds,
            spinCategories={mode:{name:dict(count=counts[name],denominator=self.spins[mode],rate=counts[name]/self.spins[mode]) for name in ('lowOnly','highOnly','mixed','noLineWin')} for mode,counts in self.categories.items()},
            spinCategoryMeaning='Mutually exclusive categories of nominal qualifying line wins, excluding scatter cash. Wild substitutions use the resolved paying symbol. Bonus categories may differ from settled cash when clipped.',
            modeSpins=dict(self.spins),settlement={m:dict(c) for m,c in self.cash.items()},
            byPayline=grouped(('mode','lineId')),bySymbolAndLength=grouped(('mode','symbol','matchLength')),
            byPaylineSymbolLengthMultiplier=grouped(('mode','lineId','symbol','matchLength','wildMultiplier')),
            detail=detail,
            attribution='Detailed contributions are nominal before cap clipping. Subtract mode-level clippedBookAmount to reconcile settled line cash; scatter cash is separate. No arbitrary allocation of cap deductions to individual lines.',
            counting='One highest-paying interpretation per line per spin. Grouped symbol hit counts count lines, not unique winning spins. Omitted combinations have zero hits. Correlated line events are not independent samples.')
