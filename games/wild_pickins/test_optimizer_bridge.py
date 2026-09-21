import csv
import json
from pathlib import Path
import tempfile
import unittest

from optimize_experimental import category, evaluate_weights, prepare
from test_evaluation import book


class OptimizerTests(unittest.TestCase):
    def test_categories_are_exclusive_with_cap_and_zero_priority(self):
        bonus = book(0, 0, 100)
        bonus['events'].insert(0, dict(type='freeSpinTrigger'))
        self.assertEqual(category(bonus, 100), 'maximum')
        self.assertEqual(category(bonus, 1000), 'bonus')
        bonus['payoutMultiplier'] = 0
        self.assertEqual(category(bonus, 1000), 'zero')
        self.assertEqual(category(book(1, 100), 1000), 'base')

    def test_exact_weighted_money_and_invalid_rows(self):
        books = [book(0, 0), book(1, 200)]
        report = evaluate_weights(books, [(0, 3, 0), (1, 1, 200)], 100000)
        self.assertEqual(report['weightedRtp'], .5)
        self.assertEqual(report['positiveWinRate'], .25)
        self.assertEqual(report['exactRtpDenominator'], 2)
        self.assertAlmostEqual(report['weightedPayoutStdDev'], 3**.5/2)
        for rows in ([(0, 1, 0)], [(0, -1, 0), (1, 2, 200)],
                     [(0, 1, 0), (1, 1, 201)], [(0, 1, 0), (0, 1, 0)],
                     [(0, 0, 0), (1, 0, 200)]):
            with self.assertRaises(ValueError):
                evaluate_weights(books, rows, 100000)

    def test_prepared_sdk_inputs_partition_source_ids(self):
        root = Path(__file__).resolve().parents[3]
        source = root/'wild-pickins/reports/math/frequency-sweep-seed43/wild-half'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'isolated'
            books, _ = prepare(source, output)
            library = output/'games/wild_pickins/library'
            forces = json.loads((library/'forces/force_record_base.json').read_text())
            ids = [identity for group in forces for identity in group['bookIds']]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(set(ids), {b['id'] for b in books})
            config = json.loads((library/'configs/math_config.json').read_text())
            self.assertEqual([b['bet_mode'] for b in config['bet_modes']], ['base'])
            self.assertAlmostEqual(sum(float(f['rtp']) for f in config['fences'][0]['fences']), .967)
            with self.assertRaises(FileExistsError):
                prepare(source, output)
