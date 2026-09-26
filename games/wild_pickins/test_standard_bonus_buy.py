import copy
import json
import unittest
from serve_local import round_response, MULTIPLIER_CONFIG
from generate_experimental import generate_round
from contract import validate, InvalidBook

class StandardBonusBuyTests(unittest.TestCase):
    def test_entry_accounting_and_reproducibility(self):
        for identity in range(100):
            response = round_response(925, identity, 'multiplier-wilds', 'bonus')
            self.assertEqual(response, round_response(925, identity, 'multiplier-wilds', 'bonus'))
            book = json.loads(response['bookJson'])
            summary = validate(book)
            self.assertEqual(book['events'][0], dict(index=0, type='freeSpinTrigger', spinId=-1, totalFs=10, positions=[], purchase=True))
            reveals = [e for e in book['events'] if e['type']=='reveal']
            self.assertTrue(all(e['gameType']=='freegame' for e in reveals))
            self.assertEqual(reveals[0]['stickyBefore'], [])
            self.assertEqual(summary['roundTotal'], summary['bonusTotal'])
            self.assertEqual(summary['stickyAfterExit'], [])
            self.assertLessEqual(len(reveals), 30)
            self.assertTrue(all(e.get('harvestTopUp', 0)==0 for e in book['events']))
            self.assertLessEqual(summary['roundTotal'], 500000)

    def test_rejects_tampered_entry(self):
        book = json.loads(round_response(925, 0, 'multiplier-wilds', 'bonus')['bookJson'])
        for field, value in [('totalFs', 15), ('positions', [dict(reel=0,row=1)]), ('purchase', False), ('spinId', 0)]:
            bad=copy.deepcopy(book);bad['events'][0][field]=value
            with self.assertRaises(InvalidBook): validate(bad)
        bad=copy.deepcopy(book);bad.pop('entryMode')
        with self.assertRaises(InvalidBook): validate(bad)

    def test_modes_are_explicit(self):
        for profile in ('natural','reference','candidate-1'):
            with self.assertRaises(ValueError): round_response(925,0,profile,'bonus')
        with self.assertRaises(ValueError): generate_round(MULTIPLIER_CONFIG,925,0,mode='unknown')
        sdk, book=generate_round(MULTIPLIER_CONFIG,925,0,mode='bonus')
        self.assertEqual(sdk['payoutMultiplier'],book['events'][-1]['amount'])
        self.assertNotIn('entryMode',generate_round(MULTIPLIER_CONFIG,925,0)[1])

if __name__=='__main__': unittest.main()
