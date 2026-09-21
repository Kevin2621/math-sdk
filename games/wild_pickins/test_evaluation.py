import copy
import unittest

from evaluate_experimental import summarize


def book(identity, base, bonus=0, topup=0):
    def result(spin, line, harvest):
        return dict(type='wildPickinsSpinResult', spinId=spin, lineWin=line,
                    harvestTopUp=harvest, endReason='fullHarvest' if harvest else None,
                    stickyAfter=[{}]*15 if harvest else [], nominalRetriggerAward=0,
                    nominalCollisionAward=0, grantedExtraSpins=0)
    events = [result(0, base, 0)]
    if bonus or topup:
        events.append(result(1, bonus, topup))
    total = base+bonus+topup
    events.append(dict(type='finalWin', amount=total))
    return dict(id=identity, payoutMultiplier=total, events=events)


class EvaluationTests(unittest.TestCase):
    def test_money_components_and_conditional_duration(self):
        books = [book(0, 0), book(1, 100), book(2, 100, 200, 600)]
        report = summarize(books, [(b['id'], 1, b['payoutMultiplier']) for b in books])
        self.assertAlmostEqual(report['observedReturn'], 10/3)
        self.assertAlmostEqual(sum(report['returnContributions'].values()), 10/3)
        self.assertEqual(report['fullHarvestRounds'], 1)
        self.assertEqual(report['bonusDuration']['p95'], 1)
        self.assertEqual(report['positiveWinRate'], 2/3)
        self.assertEqual(report['profitRate'], 1/3)

    def test_bad_lookup_and_component_totals_rejected(self):
        original = book(0, 100)
        for rows in ([], [(0, 2, 100)], [(0, 1, 101)], [(1, 1, 100)]):
            with self.assertRaises(ValueError):
                summarize([original], rows)
        bad = copy.deepcopy(original)
        bad['events'][0]['lineWin'] = 99
        with self.assertRaises(ValueError):
            summarize([bad], [(0, 1, 100)])

    def test_no_bonus_and_single_round_have_no_invented_statistics(self):
        report = summarize([book(0, 0)], [(0, 1, 0)])
        self.assertIsNone(report['samplePayoutStdDev'])
        self.assertIsNone(report['bonusDuration']['p95'])


if __name__ == '__main__':
    unittest.main()
