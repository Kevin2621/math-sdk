"""C01 serializer for resolved rule-core spins. No platform/wallet operations."""
def positions(cells,padding=0): return [dict(reel=r,row=y+padding) for r,y in sorted(cells)]
def multiplier_cells(values): return [dict(reel=r,row=y,multiplier=v) for (r,y),v in sorted(values.items())]

class BookExporter:
    def __init__(self): self.events=[]; self.closed=False
    def append(self,result,*,finished,win_level,reel_sample=None):
        if self.closed: raise ValueError('Book already closed')
        if type(win_level) is not int or win_level<0: raise ValueError('Explicit win level required')
        def emit(kind,**fields):
            self.events.append(dict(index=len(self.events),type=kind,spinId=result['spinId'],**fields))
        padded=[[{'name':reel_sample.top[r] if reel_sample else 'C08'}]+[{'name':s} for s in reel]+[{'name':reel_sample.bottom[r] if reel_sample else 'C08'}] for r,reel in enumerate(result['revealBoard'])]
        if 'wildMultipliers' in result:
            for (r,y),v in result['revealWildMultipliers'].items(): padded[r][y+1]['multiplier']=v
        emit('reveal',board=padded,
             paddingPositions=list(reel_sample.stops) if reel_sample else [0]*5,anticipation=[0]*5,gameType=result['gameType'],
             underlyingBoard=result['underlyingBoard'],stickyBefore=positions(result['stickyBefore']),
             goldenTarget=positions([result['goldenTarget']])[0] if result['goldenTarget'] is not None else None)
        if result['goldenTarget'] is not None:
            emit('goldenCropPick',target=positions([result['goldenTarget']])[0],expectedCrop=result['expectedCrop'],result='W',
                 persistent=result['gameType']=='freegame',visibleAfterPick=result['finalBoard'])
            if 'wildMultipliers' in result: self.events[-1]['wildMultipliers']=multiplier_cells(result['wildMultipliers'])
        fields={k:result[k] for k in ('finalBoard','nominalCollisionAward','nominalRetriggerAward','grantedExtraSpins',
            'completedBonusSpins','remaining','totalGranted','lineWin','harvestTopUp','spinWin','bonusTotal','roundTotal','endReason')}
        for k in ('stickyAfter','collisionPositions','scatterPositions'): fields[k]=positions(result[k])
        if 'wildMultipliers' in result:
            fields.update(wildMultipliers=multiplier_cells(result['wildMultipliers']),scatterWin=result['scatterWin'],nominalScatterWin=result['nominalScatterWin'])
        emit('wildPickinsSpinResult',**fields)
        allowance=result['lineWin'];wins=[]
        for award in result['lines'].awards:
            paid=min(award.amount,allowance);allowance-=paid
            wins.append(dict(symbol=award.crop,kind=award.count,uncappedWin=award.amount,win=paid,
                positions=positions(award.positions,padding=1),meta=dict(lineIndex=award.line_id,multiplier=award.multiplier,
                winWithoutMult=award.base_amount,globalMult=1,lineMultiplier=award.multiplier)))
        if wins: emit('winInfo',totalWin=result['lineWin'],wins=wins)
        if result['spinWin']: emit('setWin',amount=result['spinWin'],winLevel=win_level)
        emit('setTotalWin',amount=result['roundTotal'])
        if result['entryAward']: emit('freeSpinTrigger',totalFs=result['entryAward'],positions=positions(result['scatterPositions'],padding=1))
        if finished:
            if result['gameType']=='freegame': emit('freeSpinEnd',amount=result['bonusTotal'],winLevel=win_level,endReason=result['endReason'],roundTotal=result['roundTotal'])
            emit('finalWin',amount=result['roundTotal']);self.closed=True
