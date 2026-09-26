"""Authoritative rule core. Caller supplies underlying boards and explicit math inputs."""
from dataclasses import dataclass, field
from fractions import Fraction
from random import Random
from line_model import CROPS, evaluate_lines, MAX_SAFE_INTEGER

Position = tuple[int,int]

def choose_golden(board, sticky, probability: Fraction, rng: Random, target_rng=None):
    """Independent trigger draw, then uniform eligible-cell selection; no retries."""
    if not isinstance(probability,Fraction) or not 0 <= probability <= 1:
        raise ValueError('Explicit probability Fraction in [0,1] required')
    eligible=[(r,y) for r in range(5) for y in range(3)
              if (r,y) not in sticky and board[r][y] in CROPS]
    if not eligible: return None
    if rng.randrange(probability.denominator) >= probability.numerator: return None
    return eligible[(rng if target_rng is None else target_rng).randrange(len(eligible))]

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
    wild_multiplier_weights: tuple | None = None
    bonus_scatter_pays: dict | None = None
    collision_spins_per_hit: bool = False
    settlement_policy: str = 'fullHarvest'
    experiment_random: object | None = None
    sticky_multipliers: dict = field(default_factory=dict,init=False)
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
        if self.settlement_policy not in ('fullHarvest','accumulation'): raise ValueError('settlement policy')
        if type(self.collision_spins_per_hit) is not bool: raise ValueError('collision policy')
        if type(self.cap) is not int or not 0 < self.cap <= MAX_SAFE_INTEGER: raise ValueError('cap')
        if type(self.spin_budget) is not int or self.spin_budget < 20: raise ValueError('spin budget')
        if self.bonus_scatter_pays is not None:
            if set(self.bonus_scatter_pays)!={3,4,5} or any(type(v) is not int or not 0<=v<=MAX_SAFE_INTEGER for v in self.bonus_scatter_pays.values()):
                raise ValueError('Explicit bonus scatter 3/4/5 cash awards required')
        for p in (self.base_golden,self.bonus_golden):
            if not isinstance(p,Fraction) or not 0 <= p <= 1: raise ValueError('Golden probability')
        if self.wild_multiplier_weights is not None:
            if len(self.wild_multiplier_weights)!=3 or any(type(w) is not int or w<0 for w in self.wild_multiplier_weights) or not sum(self.wild_multiplier_weights):
                raise ValueError('Explicit nonnegative weights for 1x/2x/3x required')

    def start_standard_bonus(self):
        """Direct entry: ten spins, no paid base outcome or carried Wilds."""
        if self.spin_id != -1 or self.mode != 'basegame' or self.ended:
            raise ValueError('Bonus purchase requires a fresh round')
        if self.settlement_policy != 'accumulation':
            raise ValueError('Bonus purchase requires accumulation settlement')
        self.mode = 'freegame'
        self.granted = self.remaining = 10

    def spin(self, underlying, *, fixture_target=...):
        """Resolve one spin. fixture_target is a deterministic test override, not live input."""
        if self.ended: raise ValueError('Round already ended')
        # Validate shape/symbols/table without changing round state.
        active_paytable=self.bonus_paytable if self.mode=='freegame' and self.bonus_paytable is not None else self.paytable
        evaluate_lines(underlying,self.paths,active_paytable)
        if any(reel.count('S')>1 for reel in underlying): raise ValueError('Multiple scatters on reel')
        mode=self.mode; before=set(self.sticky)
        indexed=self.experiment_random
        spin_index=0 if mode=='basegame' else self.completed
        trigger_rng=self.rng if indexed is None else indexed.stream(mode,spin_index,'golden-trigger')
        target_rng=None if indexed is None else indexed.stream(mode,spin_index,'golden-target')
        target=choose_golden(underlying,before,self.base_golden if mode=='basegame' else self.bonus_golden,trigger_rng,target_rng) if fixture_target is ... else fixture_target
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
        multipliers=None
        if self.wild_multiplier_weights is not None:
            multipliers=dict(self.sticky_multipliers)
            # New Wilds on a reel share this spin's draw; retained Wilds never reroll.
            for r in range(5):
                fresh=[(r,y) for y in range(3) if visible[r][y]=='W' and (r,y) not in before]
                if fresh:
                    if indexed is not None:
                        value=indexed.weighted_value(self.wild_multiplier_weights,mode,spin_index,r)
                    else:
                        draw=self.rng.randrange(sum(self.wild_multiplier_weights))
                        value=1
                        for value,weight in enumerate(self.wild_multiplier_weights,1):
                            if draw<weight: break
                            draw-=weight
                    for p in fresh: multipliers[p]=value
        lines=evaluate_lines(visible,self.paths,active_paytable,multipliers)
        line_win=min(lines.total,self.cap-self.total)
        nominal_scatter=self.bonus_scatter_pays.get(len(scatters),0) if mode=='freegame' and self.bonus_scatter_pays is not None else 0
        scatter_win=min(nominal_scatter,self.cap-self.total-line_win)
        full=mode=='freegame' and len(sticky)==15
        harvest_ends=full and self.settlement_policy=='fullHarvest'
        topup=self.cap-self.total-line_win-scatter_win if harvest_ends else 0
        spin_win=line_win+scatter_win+topup
        self.total+=spin_win
        if mode=='freegame': self.bonus_total+=spin_win; self.completed+=1
        terminal=harvest_ends or self.total==self.cap
        collision_award=len(collisions) if self.collision_spins_per_hit else int(bool(collisions))
        retrigger={3:5,4:7,5:10}.get(len(scatters),0) if mode=='freegame' and self.bonus_scatter_pays is None else 0
        extra=min(collision_award+retrigger,self.spin_budget-self.granted) if mode=='freegame' and not terminal else 0
        if mode=='freegame':
            self.granted+=extra
            self.remaining=0 if terminal else self.granted-self.completed
        reason='fullHarvest' if harvest_ends else 'roundCap' if terminal else 'spinsExhausted' if mode=='freegame' and self.remaining==0 else None
        self.spin_id+=1
        result=dict(spinId=self.spin_id,gameType=mode,underlyingBoard=[list(r) for r in underlying],revealBoard=reveal,
            stickyBefore=sorted(before),goldenTarget=target,expectedCrop=expected,finalBoard=visible,
            stickyAfter=sorted(sticky),collisionPositions=collisions,scatterPositions=scatters,
            nominalCollisionAward=collision_award,nominalRetriggerAward=retrigger,grantedExtraSpins=extra,
            completedBonusSpins=self.completed,remaining=self.remaining,totalGranted=self.granted,
            lineWin=line_win,harvestTopUp=topup,spinWin=spin_win,bonusTotal=self.bonus_total,roundTotal=self.total,
            endReason=reason,lines=lines,entryAward=0)
        if multipliers is not None:
            result['nominalScatterWin']=nominal_scatter
            result['scatterWin']=scatter_win
            result['wildMultipliers']=dict(multipliers)
            result['revealWildMultipliers']={p:v for p,v in multipliers.items() if p!=target}
            self.sticky_multipliers=dict(multipliers) if mode=='freegame' else {}
        self.sticky=sticky
        if mode=='basegame' and not terminal and len(scatters)>=3:
            result['entryAward']={3:10,4:15,5:20}[len(scatters)]
            self.mode='freegame';self.granted=self.remaining=result['entryAward'];self.sticky=set()
        elif mode=='basegame' or terminal or self.remaining==0:
            self.ended=True;self.sticky=set();self.mode='basegame'
            self.sticky_multipliers={}
        return result
