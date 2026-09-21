import json
from pathlib import Path
import unittest
from coverage_books import labels, audit

ROOT = Path(__file__).resolve().parents[3]


def fixture(name):
    data = json.loads((ROOT/f'wild-pickins/fixtures/v1/{name}-L20.json').read_text())
    return dict(id=0, payoutMultiplier=data['events'][-1]['amount'], events=data['events'])


class CoverageTests(unittest.TestCase):
    def test_retrigger_and_entry_labels(self):
        tags = labels(fixture('retrigger-5'))
        self.assertIn('entry-3', tags)
        self.assertIn('retrigger-5', tags)
        self.assertIn('normal-bonus-end', tags)

    def test_deduplicates_events_even_if_id_changes(self):
        first = fixture('base-loss')
        second = dict(first, id=1)
        report = audit([first, second], 2)
        self.assertEqual(report['books'], 2)
        self.assertEqual(report['distinctEventSequences'], 1)
        self.assertEqual(report['distinctFinalBoardSequences'], 1)
        self.assertEqual(report['mostRepeatedFinalBoardSequenceCount'], 2)
        self.assertEqual(report['coverage']['base-loss']['missingToQuota'], 1)

    def test_cap_suppression_is_not_budget_clipping(self):
        tags = labels(fixture('bonus-cap-suppresses-awards'))
        self.assertIn('round-cap', tags)
        self.assertNotIn('budget-clipping', tags)
