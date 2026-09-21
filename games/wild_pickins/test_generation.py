import json
from pathlib import Path
from random import Random
import unittest
from reel_source import ReelSource
from generate_experimental import generate_round
CONFIG=json.loads((Path(__file__).parent/'experiments/plumbing.json').read_text())

class ReelTests(unittest.TestCase):
    def test_wraparound_scatter_violation_rejected(self):
        with self.assertRaises(ValueError): ReelSource([['S','C01','C02','S']]*5)
    def test_stops_padding_and_visible_window_agree(self):
        source=ReelSource(CONFIG['reels']['basegame']);sample=source.draw(Random(42))
        for r,strip in enumerate(source.strips):
            stop=sample.stops[r]
            self.assertEqual(sample.board[r],[strip[(stop+i)%len(strip)] for i in range(3)])
            self.assertEqual(sample.top[r],strip[(stop-1)%len(strip)])
            self.assertEqual(sample.bottom[r],strip[(stop+3)%len(strip)])
    def test_seed_reproduces_complete_sdk_book(self):
        first=generate_round(CONFIG,42,0);second=generate_round(CONFIG,42,0)
        self.assertEqual(first,second)
    def test_round_ids_do_not_depend_on_batch_order(self):
        expected=generate_round(CONFIG,42,4)
        generate_round(CONFIG,42,2)
        self.assertEqual(generate_round(CONFIG,42,4),expected)
    def test_generated_rounds_reconcile_and_terminate(self):
        seen=set()
        for i in range(100):
            book,envelope=generate_round(CONFIG,42,i)
            seen.add(json.dumps(book['events'][0]['board']))
            self.assertEqual(book['payoutMultiplier'],book['events'][-1]['amount'])
            reveals=[e for e in book['events'] if e['type']=='reveal']
            self.assertLessEqual(len(reveals),31)
        self.assertGreater(len(seen),1)

if __name__=='__main__':unittest.main()
