"""Authoritative rule core. Caller supplies underlying boards and explicit math inputs."""
from dataclasses import dataclass, field
from fractions import Fraction
from random import Random
from line_model import CROPS, evaluate_lines, MAX_SAFE_INTEGER

Position = tuple[int,int]

def choose_golden(board, sticky, probability: Fraction, rng: Random):
    """Independent trigger draw, then uniform eligible-cell selection; no retries."""
    if not isinstance(probability,Fraction) or not 0 <= probability <= 1:
        raise ValueError('Explicit probability Fraction in [0,1] required')
    eligible=[(r,y) for r in range(5) for y in range(3)
              if (r,y) not in sticky and board[r][y] in CROPS]
    if not eligible: return None
    if rng.randrange(probability.denominator) >= probability.numerator: return None
    return eligible[rng.randrange(len(eligible))]

@dataclass
class RoundModel:
    paths: dict
    paytable: dict
    cap: int
    spin_budget: int
    base_golden: Fraction
    bonus_golden: Fraction
    rng: Random
    bonus_paytable: dict | None = None
    mode: str = field(default='basegame',init=False)
    sticky: set = field(default_factory=set,init=False)
    total: int = field(default=0,init=False)
    bonus_total: int = field(default=0,init=False)
    granted: int = field(default=0,init=False)
    completed: int = field(default=0,init=False)
    remaining: int = field(default=0,init=False)
    ended: bool = field(default=False,init=False)
    spin_id: int = field(default=-1,init=False)

    def __post_init__(self):
        if type(self.cap) is not int or not 0 < self.cap <= MAX_SAFE_INTEGER: raise ValueError('cap')
        if type(self.spin_budget) is not int or self.spin_budget < 20: raise ValueError('spin budget')
        for p in (self.base_golden,self.bonus_golden):
            if not isinstance(p,Fraction) or not 0 <= p <= 1: raise ValueError('Golden probability')

    def spin(self, underlying, *, fixture_target=...):
        """Resolve one spin. fixture_target is a deterministic test override, not live input."""
        if self.ended: raise ValueError('Round already ended')
        # Validate shape/symbols/table without changing round state.
        active_paytable=self.bonus_paytable if self.mode=='freegame' and self.bonus_paytable is not None else self.paytable
        evaluate_lines(underlying,self.paths,active_paytable)
        if any(reel.count('S')>1 for reel in underlying): raise ValueError('Multiple scatters on reel')
        mode=self.mode; before=set(self.sticky)
        target=choose_golden(underlying,before,self.base_golden if mode=='basegame' else self.bonus_golden,self.rng) if fixture_target is ... else fixture_target
        if target is not None:
            if not isinstance(target,tuple) or len(target)!=2 or any(type(v) is not int for v in target): raise ValueError('target shape')
            r,y=target
            if not 0<=r<5 or not 0<=y<3 or target in before or underlying[r][y] not in CROPS: raise ValueError('ineligible target')
        visible=[list(reel) for reel in underlying]
        for r,y in before: visible[r][y]='W'
        reveal=[list(reel) for reel in visible]
        expected=visible[target[0]][target[1]] if target is not None else None
        if target is not None: visible[target[0]][target[1]]='W'
        collisions=sorted(p for p in before if underlying[p[0]][p[1]]=='W')
        sticky={(r,y) for r in range(5) for y in range(3) if visible[r][y]=='W'} if mode=='freegame' else set()
        scatters=[(r,y) for r in range(5) for y in range(3) if visible[r][y]=='S']
        lines=evaluate_lines(visible,self.paths,active_paytable)
        line_win=min(lines.total,self.cap-self.total)
        full=mode=='freegame' and len(sticky)==15
        topup=self.cap-self.total-line_win if full else 0
        spin_win=line_win+topup
        self.total+=spin_win
        if mode=='freegame': self.bonus_total+=spin_win; self.completed+=1
        terminal=full or self.total==self.cap
        collision_award=int(bool(collisions))
        retrigger={3:5,4:7,5:10}.get(len(scatters),0) if mode=='freegame' else 0
        extra=min(collision_award+retrigger,self.spin_budget-self.granted) if mode=='freegame' and not terminal else 0
        if mode=='freegame':
            self.granted+=extra
            self.remaining=0 if terminal else self.granted-self.completed
        reason='fullHarvest' if full else 'roundCap' if terminal else 'spinsExhausted' if mode=='freegame' and self.remaining==0 else None
        self.spin_id+=1
        result=dict(spinId=self.spin_id,gameType=mode,underlyingBoard=[list(r) for r in underlying],revealBoard=reveal,
            stickyBefore=sorted(before),goldenTarget=target,expectedCrop=expected,finalBoard=visible,
            stickyAfter=sorted(sticky),collisionPositions=collisions,scatterPositions=scatters,
            nominalCollisionAward=collision_award,nominalRetriggerAward=retrigger,grantedExtraSpins=extra,
            completedBonusSpins=self.completed,remaining=self.remaining,totalGranted=self.granted,
            lineWin=line_win,harvestTopUp=topup,spinWin=spin_win,bonusTotal=self.bonus_total,roundTotal=self.total,
            endReason=reason,lines=lines,entryAward=0)
        self.sticky=sticky
        if mode=='basegame' and not terminal and len(scatters)>=3:
            result['entryAward']={3:10,4:15,5:20}[len(scatters)]
            self.mode='freegame';self.granted=self.remaining=result['entryAward'];self.sticky=set()
        elif mode=='basegame' or terminal or self.remaining==0:
            self.ended=True;self.sticky=set();self.mode='basegame'
        return result
