"""Boundary coverage for accumulation-only settlement and complete book replay."""
import copy
import json
from fractions import Fraction
from pathlib import Path
from random import Random
import unittest
from round_model import RoundModel
from book_export import BookExporter
from generate_experimental import generate_round
from contract import validate

CONFIG=json.loads((Path(__file__).parent/'experiments/wp25-multiplier-wilds.json').read_text())

def dry():
    return [[f'C{r+1:02}']*3 for r in range(5)]

class AccumulationTests(unittest.TestCase):
    def make(self,value=1,base_win=False):
        fm=CONFIG['fixtureMath']
        pay={(s,int(n)):v for s,pays in fm['paytable'].items() for n,v in pays.items()}
        self.model=RoundModel(dict(enumerate(fm['paths'],1)),pay,500000,30,Fraction(0),Fraction(0),Random(42),
            bonus_paytable=pay,wild_multiplier_weights=tuple(int(v==value) for v in (1,2,3)),
            bonus_scatter_pays={3:200,4:500,5:1000},collision_spins_per_hit=True,settlement_policy='accumulation')
        self.exporter=BookExporter()
        board=[['S','C01','C02'] for _ in range(5)] if base_win else dry()
        for reel in board:reel[0]='S'
        entry=self.spin(board)
        self.assertEqual(entry['entryAward'],20)
        if base_win:self.assertGreater(entry['spinWin'],0)
        else:self.assertEqual(entry['spinWin'],0)
        return self.model

    def spin(self,board):
        r=self.model.spin(board)
        self.assertEqual(r['harvestTopUp'],0)
        self.assertEqual(r['spinWin'],r['lineWin']+r['scatterWin'])
        self.exporter.append(r,finished=self.model.ended,win_level=1)
        return r

    def finish_and_validate(self):
        while not self.model.ended:self.spin(dry())
        book={k:copy.deepcopy(CONFIG[k]) for k in ('schemaVersion','gameId','lineSetId','mathVersion','assetMapVersion','spinBudget','roundCap','fixtureMath')}
        # Tests force different draw distributions without changing settlement.
        book['fixtureMath']['wildMultiplierWeights']=[1,1,1]
        book.update(fixtureOnly=True,events=self.exporter.events)
        result=validate(book)
        self.assertEqual(result['roundTotal'],self.model.total)
        self.assertEqual(self.model.sticky,set());self.assertEqual(self.model.sticky_multipliers,{})
        with self.assertRaises(ValueError):self.model.spin(dry())
        return book

    def test_full_3x_board_pays_three_spins_with_exact_cap_clip(self):
        self.make(3)
        first=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((first['spinWin'],first['remaining'],first['endReason']),(187500,19,None))
        # Hidden scatters are not counted; no Golden target is available.
        self.model.bonus_golden=Fraction(1)
        hidden=[['S','C01','C02'] for _ in range(5)]
        second=self.spin(hidden)
        self.assertEqual((second['spinWin'],second['scatterWin'],second['goldenTarget']),(187500,0,None))
        last=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((last['lineWin'],last['roundTotal'],last['endReason']),(125000,500000,'roundCap'))
        self.assertEqual((last['nominalCollisionAward'],last['grantedExtraSpins']),(15,0))
        book=self.finish_and_validate()
        for mutate in (lambda b:next(e for e in b['events'] if e['type']=='wildPickinsSpinResult').__setitem__('harvestTopUp',1),
                       lambda b:b.__setitem__('schemaVersion',3),
                       lambda b:b['fixtureMath'].__setitem__('settlementPolicy','fullHarvest')):
            bad=copy.deepcopy(book);mutate(bad)
            with self.assertRaises(ValueError):validate(bad)
        result=next(e for e in book['events'] if e['type']=='wildPickinsSpinResult' and e['spinId']==1)
        bad=copy.deepcopy(book);bad['events'][result['index']]['endReason']='fullHarvest'
        with self.assertRaises(ValueError):validate(bad)

    def test_full_1x_board_continues_for_eight_paying_spins(self):
        self.make(1)
        self.assertEqual(self.spin([['W']*3 for _ in range(5)])['lineWin'],62500)
        for _ in range(6):
            result=self.spin(dry());self.assertEqual(result['lineWin'],62500);self.assertIsNone(result['endReason'])
        self.assertEqual(self.spin(dry())['roundTotal'],500000)
        self.finish_and_validate()

    def test_triggering_base_win_counts_toward_the_same_cap(self):
        self.make(3,base_win=True)
        base=self.model.total
        self.spin([['W']*3 for _ in range(5)])
        self.spin(dry())
        final=self.spin(dry())
        self.assertEqual(final['lineWin'],125000-base)
        self.assertEqual(final['roundTotal'],500000)
        self.assertEqual(final['bonusTotal'],500000-base)
        self.finish_and_validate()

    def test_mixed_values_are_retained_on_full_board(self):
        self.make()
        values=[1,2,3,1,2]
        for r,value in enumerate(values):
            self.model.wild_multiplier_weights=tuple(int(v==value) for v in (1,2,3))
            board=dry();board[r]=['W']*3
            result=self.spin(board)
        self.assertEqual(result['lineWin'],25*500*sum(values))
        stored=dict(result['wildMultipliers'])
        result=self.spin(dry())
        self.assertEqual(result['wildMultipliers'],stored)
        self.assertEqual(result['lineWin'],112500)
        self.finish_and_validate()

    def test_first_full_board_on_last_spin_does_not_get_free_extension(self):
        self.make()
        for _ in range(19):self.spin(dry())
        last=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((last['roundTotal'],last['endReason'],last['grantedExtraSpins']),(62500,'spinsExhausted',0))
        self.finish_and_validate()

    def test_last_spin_collision_extends_first_full_board(self):
        self.make()
        board=dry();board[0][0]='W';self.spin(board)
        for _ in range(18):self.spin(dry())
        full=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((full['nominalCollisionAward'],full['grantedExtraSpins'],full['remaining'],full['endReason']),(1,1,1,None))
        # Fifteen hits, only nine lifetime grants remain.
        next_spin=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((next_spin['nominalCollisionAward'],next_spin['grantedExtraSpins'],next_spin['totalGranted'],next_spin['remaining']),(15,9,30,9))
        capped_budget=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((capped_budget['grantedExtraSpins'],capped_budget['remaining']),(0,8))
        self.finish_and_validate()

    def test_thirty_grants_play_out_and_last_full_board_can_finish_below_cap(self):
        self.make()
        board=dry();board[0][0]='W';self.spin(board)
        for _ in range(10):self.spin(board)
        self.assertEqual(self.model.granted,30)
        while self.model.completed<29:self.spin(dry())
        last=self.spin([['W']*3 for _ in range(5)])
        self.assertEqual((last['grantedExtraSpins'],last['remaining'],last['endReason']),(0,0,'spinsExhausted'))
        self.assertLess(last['roundTotal'],500000)
        self.finish_and_validate()

    def test_scatter_cash_clips_after_lines_and_prevents_extra_spins(self):
        self.make()
        # Small cap chosen after a zero-win entry, consistent in the replay envelope.
        self.model.cap=650
        r=self.spin([['C01','S',f'C{r+2:02}'] for r in range(5)])
        self.assertEqual((r['lineWin'],r['nominalScatterWin'],r['scatterWin'],r['spinWin']),(600,1000,50,650))
        self.assertEqual(r['endReason'],'roundCap')
        book=self.finish_and_validate_with_cap(650)
        self.assertEqual(validate(book)['roundTotal'],650)

    def finish_and_validate_with_cap(self,cap):
        book={k:copy.deepcopy(CONFIG[k]) for k in ('schemaVersion','gameId','lineSetId','mathVersion','assetMapVersion','spinBudget','roundCap','fixtureMath')}
        book.update(roundCap=cap,fixtureOnly=True,events=self.exporter.events)
        validate(book)
        self.assertTrue(self.model.ended)
        self.assertEqual(self.model.sticky_multipliers,{})
        return book

    def test_generated_rounds_use_new_policy_and_validate(self):
        for i in range(100):
            sdk,book=generate_round(CONFIG,9031,i)
            self.assertEqual(validate(book)['roundTotal'],sdk['payoutMultiplier'])
            self.assertEqual(book['schemaVersion'],4)
            self.assertTrue(all(e.get('harvestTopUp',0)==0 and e.get('endReason')!='fullHarvest' for e in book['events']))

if __name__=='__main__':unittest.main()
