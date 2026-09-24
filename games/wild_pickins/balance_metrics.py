"""Common natural-sample metrics. Uncertainty units are complete paid rounds."""
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
from payline_metrics import PaylineMetrics

CRITERIA_PATH=Path(__file__).with_name('balance_criteria.json')

def mean_stats(hist):
    n=sum(hist.values())
    if not n:return dict(count=0,mean=None,standardError=None,approx95=None)
    mean=sum(x*k for x,k in hist.items())/n
    se=math.sqrt(sum(k*(x-mean)**2 for x,k in hist.items())/(n-1)/n) if n>1 else None
    return dict(count=n,mean=mean,standardError=se,approx95=[mean-1.96*se,mean+1.96*se] if se is not None else None)

def rate_stats(hits,n):
    if not n:return dict(hits=hits,denominator=n,rate=None,wilson95=None)
    p=hits/n;z=1.96;d=1+z*z/n
    center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return dict(hits=hits,denominator=n,rate=p,wilson95=[max(0,center-half),min(1,center+half)])

def distribution(hist):
    stats=mean_stats(hist);n=stats['count'];ordered=sorted(hist.items())
    def q(p):
        if not n:return None
        rank=max(1,math.ceil(n*p));seen=0
        for value,count in ordered:
            seen+=count
            if seen>=rank:return value
    return dict(**stats,quantiles={str(p):q(p) for p in (.1,.5,.9,.95,.99)},histogram=[dict(value=v,count=k) for v,k in ordered])

class BalanceMetrics:
    def __init__(self,config):
        self.base_streaks={name:dict(current=0,completed=Counter()) for name in ("zeroPayout", "noProfit")}
        self.paylines=PaylineMetrics(config["fixtureMath"]["paths"])
        self.config=config;self.criteria=json.loads(CRITERIA_PATH.read_text())
        self.joint=Counter();self.bonus_rows=Counter();self.progress=defaultdict(Counter)
        self.symbols={m:{s:Counter() for s in ('underlying','visible','qualifyingCells','stickyCells','assignedReels','assignedCells','visibleWildValues','qualifyingWildValues')} for m in ('basegame','freegame')}
        self.spins=Counter();self.entry_awards=Counter();self.totals=Counter();self.begin_round()

    def begin_round(self):
        self.current=Counter();self.current['firstFullSpin']=0

    def spin(self,r):
        self.paylines.spin(r)
        mode=r['gameType'];s=self.symbols[mode];self.spins[mode]+=1
        for reel in r['underlyingBoard']:s['underlying'].update(reel)
        for reel in r['finalBoard']:s['visible'].update(reel)
        cells={p for a in r['lines'].awards for p in a.positions}
        s['qualifyingCells'].update(r['finalBoard'][x][y] for x,y in cells)
        values=r.get('wildMultipliers',{})
        s['visibleWildValues'].update(values.values())
        s['qualifyingWildValues'].update(values[p] for p in cells if p in values)
        before=set(r['stickyBefore']);fresh={p:v for p,v in values.items() if p not in before}
        s['assignedCells'].update(fresh.values())
        s['assignedReels'].update({x:v for (x,y),v in fresh.items()}.values())
        s['stickyCells'].update(values[p] for p in r['stickyAfter'] if p in values)
        self.current['scatterCash']+=r.get('scatterWin',0)
        if mode=='basegame':
            self.current['base']=r['spinWin'];self.current['entryAward']=r['entryAward']
            if r['entryAward']:self.entry_awards[r['entryAward']]+=1
        else:
            self.current['duration']+=1;self.current['bonus']+=r['spinWin']
            occupancy=len(r['stickyAfter']);new=len(set(r['stickyAfter'])-before)
            if occupancy==15 and not self.current['firstFullSpin']:self.current['firstFullSpin']=self.current['duration']
            self.current['maxOccupancy']=max(self.current['maxOccupancy'],occupancy)
            self.current['collisions']+=len(r['collisionPositions'])
            self.current['nominalCollisionSpins']+=r['nominalCollisionAward']
            self.current['grantedExtra']+=r['grantedExtraSpins']
            self.current['budgetReached']|=r['totalGranted']==self.config['spinBudget']
            row=self.progress[self.current['duration']]
            row['observations']+=1;row['occupancySum']+=occupancy;row['newStickySum']+=new
            row['collisionSum']+=len(r['collisionPositions']);row['fullBoards']+=occupancy==15
        self.current['capHit']|=r['endReason']=='roundCap'
        self.current['roundTotal']=r['roundTotal']

    def end_round(self):
        c=self.current
        for name,track in self.base_streaks.items():
            losing=c['base']==0 if name=='zeroPayout' else c['base']<=100
            if losing:track['current']+=1
            else:
                track['completed'][track['current']]+=1;track['current']=0
        if c['base']+c['bonus']!=c['roundTotal']:raise ValueError('Round accounting mismatch')
        self.joint[c['base'],c['bonus']]+=1
        self.totals.update({k:c[k] for k in ('scatterCash','capHit')})
        if c['entryAward']:
            keys=('bonus','duration','maxOccupancy','collisions','nominalCollisionSpins','grantedExtra','budgetReached','firstFullSpin','capHit')
            self.bonus_rows[tuple(c[k] for k in keys)]+=1

    def report(self):
        n=sum(self.joint.values());entries=sum(self.bonus_rows.values())
        def projected(index,scale=1):
            h=Counter()
            for pair,count in self.joint.items():h[(sum(pair) if index is None else pair[index])*scale]+=count
            return h
        total=projected(None,.01);base=projected(0,.01);bonus=projected(1,.01)
        stats={k:mean_stats(h) for k,h in [('totalReturn',total),('baseReturn',base),('bonusReturn',bonus)]}
        paying=sum(k for x,k in base.items() if x>0)
        base_rates={name:rate_stats(sum(k for x,k in base.items() if pred(x)),n) for name,pred in {
            'zero':lambda x:x==0,'belowStake':lambda x:0<x<1,'breakEven':lambda x:x==1,'profit':lambda x:x>1,'positive':lambda x:x>0}.items()}
        conditional=distribution(Counter({x:k for x,k in base.items() if x>0}))
        total_mean=stats['totalReturn']['mean'];base_mean=stats['baseReturn']['mean'];bonus_mean=stats['bonusReturn']['mean']
        share=base_mean/total_mean if total_mean else None
        # Delta-method uncertainty preserves within-round base/bonus covariance.
        ratio_se=None
        if share is not None and n>1:
            ratio_se=math.sqrt(sum(k*((b*.01)-share*((b+f)*.01))**2 for (b,f),k in self.joint.items())/(n-1)/n)/total_mean
        bonus_names=('payoutX','duration','maxOccupancy','collisions','nominalCollisionSpins','grantedExtra','budgetReached','firstFullSpin','capHit')
        bh={name:Counter() for name in bonus_names}
        for row,count in self.bonus_rows.items():
            for i,name in enumerate(bonus_names):bh[name][row[i]*(.01 if i==0 else 1)]+=count
        review=self.criteria['reviewThresholds'];large=sum(x*k for x,k in total.items() if x>=review['largeRoundAtLeastX'])
        total_awards=sum(x*k for x,k in total.items())
        bonus_report={name:distribution(bh[name]) for name in bonus_names}
        bonus_report.update(entryRate=rate_stats(entries,n),startingSpinCounts=dict(self.entry_awards),
            firstFullSpinWhenReached=distribution(Counter({x:k for x,k in bh['firstFullSpin'].items() if x>0})),
            zeroRate=rate_stats(bh['payoutX'].get(0,0),entries),
            weakRate=rate_stats(sum(k for x,k in bh['payoutX'].items() if x<review['weakBonusBelowX']),entries),
            fullBoardRate=rate_stats(sum(k for x,k in bh['firstFullSpin'].items() if x>0),entries),
            budgetReachedRate=rate_stats(bh['budgetReached'].get(1,0),entries))
        cap=rate_stats(self.totals['capHit'],n)
        metrics=dict(version='wp-metrics-2',baseStreaks={name:dict(completedGaps=distribution(t['completed']),trailingCensoredGap=t['current'],meaning='Consecutive paid base spins before next qualifying hit; zero-length gaps included; bonus cash ignored; first gap begins at sample start') for name,t in self.base_streaks.items()},paylineAttribution=self.paylines.report(n),paidRounds=n,returns=stats,
            shares=dict(base=share,bonus=1-share if share is not None else None,baseStandardError=ratio_se),
            base=dict(rates=base_rates,positivePayout=conditional),bonus=bonus_report,
            roundPayout=distribution(total),capHitRate=cap,
            tail=dict(thresholdX=review['largeRoundAtLeastX'],returnShare=large/total_awards if total_awards else None,
                capReturnShare=sum(x*k for x,k in total.items() if x>=self.config['roundCap']/100)/total_awards if total_awards else None,
                rareTailResolved=False),
            scatterCashReturn=self.totals['scatterCash']/(100*n) if n else None,
            progressByBonusSpin=[dict(spin=i,**v,meanOccupancy=v['occupancySum']/v['observations'],meanNewSticky=v['newStickySum']/v['observations']) for i,v in sorted(self.progress.items())],
            symbolObservations={mode:{name:dict(denominator=sum(counts.values()),counts=dict(counts),frequencies={str(k):v/sum(counts.values()) for k,v in counts.items()}) for name,counts in groups.items()} for mode,groups in self.symbols.items()},
            observedSpins=dict(self.spins),configuredProbabilities=self.configured(),
            sufficientStatistics=dict(units='integer book units, 100 per original wager',jointBaseBonus=[dict(base=b,bonus=f,count=k) for (b,f),k in sorted(self.joint.items())],
                bonusColumns=['bonusBookAmount',*bonus_names[1:]],bonusUnits='first column in integer book units, other columns counts/flags; firstFullSpin=0 means never',bonusRows=[dict(values=list(row),count=k) for row,k in sorted(self.bonus_rows.items())]),
            limitations=['Normal mean intervals are approximate and do not establish unobserved rare tails.',
                'Progress is conditional on the bonus reaching that spin; late-spin survivors are selected.',
                'Symbol/value tallies are descriptive, not independent samples; sticky cells repeat and new same-reel values are shared.',
                'Qualifying cells are the union of uncapped winning-line cells, not a count of separately paid line positions.'])
        if n:
            assert math.isclose(base_mean+bonus_mean,total_mean,abs_tol=1e-10)
            assert math.isclose((paying/n)*(conditional['mean'] or 0),base_mean,abs_tol=1e-10)
            assert math.isclose((entries/n)*(bonus_report['payoutX']['mean'] or 0),bonus_mean,abs_tol=1e-10)
        metrics['screening']=self.screen(metrics)
        return metrics

    def configured(self):
        c=self.config;w=c['fixtureMath']['wildMultiplierWeights']
        return dict(reels={mode:[dict(length=len(strip),counts=dict(Counter(strip)),perRowProbabilities={s:k/len(strip) for s,k in Counter(strip).items()}) for strip in strips] for mode,strips in c['reels'].items()},
            wildValueProbabilities={str(i):v/sum(w) for i,v in enumerate(w,1)},goldenRates=c['goldenRates'],assignmentUnit='one value per reel with new Wilds per spin')

    def screen(self,m):
        c=self.criteria;actual={k:v['mean'] for k,v in m['returns'].items()}
        actual.update(baseShare=m['shares']['base'],basePositiveRate=m['base']['rates']['positive']['rate'],positiveBaseMeanX=m['base']['positivePayout']['mean'])
        fits={k:dict(actual=actual[k],target=t,tolerance=c['pointTolerances'][k],withinTolerance=actual[k] is not None and abs(actual[k]-t)<=c['pointTolerances'][k]) for k,t in c['selectedTargets'].items()}
        intervals={k:v['approx95'] for k,v in m['returns'].items()}
        intervals['basePositiveRate']=m['base']['rates']['positive']['wilson95']
        precision={k:dict(halfWidth=(v[1]-v[0])/2 if v else None,limit=c['maximum95HalfWidths'][k],sufficient=v is not None and (v[1]-v[0])/2<=c['maximum95HalfWidths'][k]) for k,v in intervals.items()}
        warnings=[];r=c['reviewThresholds'];b=m['bonus']
        for name,value,limits in [('bonusEntryRate',b['entryRate']['rate'],r['bonusEntryRateRange']),('meanBonusSpins',b['duration']['mean'],r['meanBonusSpinsRange'])]:
            if value is None or not limits[0]<=value<=limits[1]:warnings.append(name)
        for name,value,limit in [('zeroBonusRate',b['zeroRate']['rate'],r['maximumZeroBonusRate']),('weakBonusRate',b['weakRate']['rate'],r['maximumWeakBonusRate']),('largeRoundReturnShare',m['tail']['returnShare'],r['maximumLargeRoundReturnShare'])]:
            if value is None or value>limit:warnings.append(name)
        return dict(criteria=c,fit= fits,precision=precision,
            coverage=dict(paidRoundsSufficient=m['paidRounds']>=c['minimumPaidRounds'],bonusEntriesSufficient=b['entryRate']['hits']>=c['minimumBonusEntries']),
            reviewFlags=warnings,independentValidationSeedsRequired=c['independentValidationSeeds'],independentValidationComplete=False,
            releaseAccepted=False,note='Screening only. Provisional review flags are not user-approved rejection rules. Rare tails and independent validation remain unresolved.')

def markdown_report(report):
    m=report['metrics'];s=m['screening']
    def number(x):return 'No observations' if x is None else f'{x:.6f}'
    rows=['# Wild Pickins candidate metrics', '',f"Seed: {report['seed']}. Complete paid rounds: {report['rounds']}. RNG: {report.get('rngScheme','unspecified')}.",'',
        'Status: **screening only; not accepted release math**. Targets are user-selected; tolerances and review flags are provisional engineering criteria.','',
        '## Target fit','', '| Metric | Observed | Target | Tolerance | Within tolerance |','| --- | ---: | ---: | ---: | --- |']
    for name,r in s['fit'].items():rows.append(f"| {name} | {number(r['actual'])} | {number(r['target'])} | ±{number(r['tolerance'])} | {r['withinTolerance']} |")
    rows+=['','Returns and rates above are fractions: 0.967 means 96.7%. Positive-base mean is × original wager.','',
        '## Sample precision','', '| Metric | Approximate 95% interval half-width | Required maximum | Sufficient |','| --- | ---: | ---: | --- |']
    for name,r in s['precision'].items():rows.append(f"| {name} | {number(r['halfWidth'])} | {number(r['limit'])} | {r['sufficient']} |")
    rows+=['',f"Minimum paid-round coverage met: {s['coverage']['paidRoundsSufficient']}. Minimum bonus-entry coverage met: {s['coverage']['bonusEntriesSufficient']}.",
        '',f"Bonus entries: {m['bonus']['entryRate']['hits']}. Mean duration: {number(m['bonus']['duration']['mean'])} spins. Median bonus payout: {number(m['bonus']['payoutX']['quantiles']['0.5'])}×.",
        '',f"Provisional review flags: {', '.join(s['reviewFlags']) or 'none'}.",
        '',f"Cap hits: {m['capHitRate']['hits']}. Rare-tail analysis and {s['independentValidationSeedsRequired']} independent validation seeds remain outstanding.",
        '', 'The JSON report contains denominators, complete payout histograms, sticky/collision progression, symbol/value frequencies, configured probabilities and sufficient statistics for complete-round uncertainty.',
        '',*['- '+x for x in m['limitations']],'']
    attribution=m.get('paylineAttribution')
    if attribution:
        rows+=['', '## Spin categories (line wins)', '', '| Mode | Category | Spins | Frequency |', '| --- | --- | ---: | ---: |']
        for mode,categories in attribution.get('spinCategories',{}).items():
            for name,r in categories.items():
                rows.append(f"| {mode} | {name} | {r['count']} | {number(r['rate'])} |")
        rows+=['', '## Payline contributions before cap clipping', '', '| Mode | Line | Awarded hits | Return contribution |', '| --- | ---: | ---: | ---: |']
        for r in attribution['byPayline']:
            rows.append(f"| {r['mode']} | {r['lineId']} | {r['hits']} | {number(r['nominalReturnContribution'])} |")
        rows+=['', '| Mode | Symbol | Match length | Awarded lines | Return contribution |', '| --- | --- | ---: | ---: | ---: |']
        for r in attribution['bySymbolAndLength']:
            rows.append(f"| {r['mode']} | {r['symbol']} | {r['matchLength']} | {r['hits']} | {number(r['nominalReturnContribution'])} |")
        rows+=['', attribution['attribution'], '', 'Exact line/symbol/length/multiplier combinations and matched Wild positions are in the JSON report.']
    return '\n'.join(rows)
