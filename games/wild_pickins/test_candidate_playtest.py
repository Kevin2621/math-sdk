import json
import unittest
from candidate_playtest import assets,recorded,table
from serve_local import round_response

class CandidatePlaybackTests(unittest.TestCase):
    def test_profiles_and_deterministic_replay(self):
        m,_=assets()
        for profile in ('candidate-1','candidate-3'):
            ids,totals,payouts=table(profile)
            self.assertEqual(len(ids),211029)
            for i in range(20):
                r=round_response(9250,i,profile)
                self.assertEqual(r,round_response(9250,i,profile))
                self.assertEqual(r['lookupSha256'],m['profiles'][profile]['lookupSha256'])
                self.assertEqual(r['configSha256'],m['configSha256'])
                self.assertEqual(json.loads(r['bookJson'])['events'][-1]['amount'],payouts[ids.index(r['sourceBookId'])])
    def test_500k_candidate_and_added_caps(self):
        from generate_experimental import ROOT
        profile='candidate-500k-1'
        m,_=assets(profile)
        self.assertEqual(m['rounds'],512088)
        ids,totals,payouts=table(profile)
        self.assertEqual(len(ids),512088)
        for i in range(20):
            response=round_response(9251,i,profile)
            self.assertEqual(response['lookupSha256'],m['profiles'][profile]['lookupSha256'])
            self.assertEqual(json.loads(response['bookJson'])['events'][-1]['amount'],payouts[ids.index(response['sourceBookId'])])
        caps=json.loads((ROOT/'wild-pickins/reports/math/maxwin-88-packaged-analysis/metadata.json').read_text())
        for cap in caps:
            book,payout=recorded(profile,cap['id'])
            self.assertEqual(payout,500000)
            self.assertEqual(book['events'][-1]['amount'],500000)

    def test_targeted_entry_and_cap_records(self):
        from pathlib import Path
        from generate_experimental import ROOT
        root=ROOT/'wild-pickins/reports/math'
        for entry,folder in ((10,'targeted-entry10-10k-seed9224-analysis'),(15,'targeted-entry15-seed9222-analysis'),(20,'targeted-entry20-seed9222-analysis')):
            rows=json.loads((root/folder/'metadata.json').read_text())
            examples=[rows[0]]+[r for r in rows if r['cap']]
            for row in examples:
                book,payout=recorded('candidate-1',row['id'])
                self.assertEqual(payout,row['payout'])
                self.assertEqual([e['totalFs'] for e in book['events'] if e['type']=='freeSpinTrigger'],[entry])

if __name__=='__main__':unittest.main()
