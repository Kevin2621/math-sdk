"""Wild Pickins candidate line evaluation in integer book units.

Caller supplies approved or explicitly experimental paytable and line paths.
No reel weights, RTP, production cap or probability defaults live here.
"""
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

CROPS = tuple(f'C{i:02}' for i in range(1, 9))
MAX_SAFE_INTEGER = 2**53 - 1

@dataclass(frozen=True)
class LineAward:
    line_id: int
    crop: str
    count: int
    amount: int
    positions: tuple[tuple[int, int], ...]

@dataclass(frozen=True)
class LineResult:
    total: int
    awards: tuple[LineAward, ...]

def evaluate_lines(board: Sequence[Sequence[str]], paths: Mapping[int, Sequence[int]],
                   paytable: Mapping[tuple[str, int], int]) -> LineResult:
    """Highest crop/length award once per line; tie display uses crop ID then length.

    Board is reel-major, unpadded 5x3. Positions use zero-based visible rows.
    No clipping here: whole-round settlement owns the cap.
    """
    if len(board) != 5 or any(len(reel) != 3 for reel in board):
        raise ValueError('Expected unpadded reel-major 5x3 board')
    if any(symbol not in (*CROPS, 'W', 'S') for reel in board for symbol in reel):
        raise ValueError('Unknown semantic symbol')
    if not paths or any(type(k) is not int or k < 1 for k in paths):
        raise ValueError('Positive integer line IDs required')
    if any(len(p) != 5 or any(type(y) is not int or y not in (0,1,2) for y in p) for p in paths.values()):
        raise ValueError('Invalid line path')
    if len({tuple(p) for p in paths.values()}) != len(paths):
        raise ValueError('Duplicate line paths')
    expected={(crop,n) for crop in CROPS for n in (3,4,5)}
    if set(paytable) != expected:
        raise ValueError('Explicit 3/4/5 paytable required for each crop')
    if any(type(v) is not int or not 0 <= v <= MAX_SAFE_INTEGER for v in paytable.values()):
        raise ValueError('Payouts must be nonnegative safe integers')
    awards=[]
    for line_id in sorted(paths):
        path=paths[line_id]
        best=None
        for crop in CROPS:
            for count in (3,4,5):
                if not all(board[r][path[r]] in (crop,'W') for r in range(count)):
                    continue
                amount=paytable[crop,count]
                if amount and (best is None or amount > best.amount):
                    best=LineAward(line_id,crop,count,amount,tuple((r,path[r]) for r in range(count)))
        if best is not None: awards.append(best)
    total=sum(a.amount for a in awards)
    if total>MAX_SAFE_INTEGER:
        raise ValueError('Total exceeds safe book integer range')
    return LineResult(total,tuple(awards))
