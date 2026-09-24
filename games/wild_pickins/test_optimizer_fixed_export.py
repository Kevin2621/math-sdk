"""End-to-end check against the locally built Rust debug binary."""
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
BINARY=ROOT/'math-sdk/optimization_program/target/debug/PigFarmRust'

class FixedExportTests(unittest.TestCase):
    @unittest.skipUnless(BINARY.exists(),'Build optimizer debug binary first')
    def test_metadata_groups_export_requested_probabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);library=root/'games/probe/library'
            for folder in ('configs','forces','lookup_tables','publish_files','optimization_files'):
                (library/folder).mkdir(parents=True)
            (root/'src').mkdir()
            specs=[('zero10',0,.75),('zero20',0,.24),('cap10',5000,.009),('cap20',5000,.001)]
            fences=[];forces=[]
            for i,(name,payout,p) in enumerate(specs):
                search=[dict(name='group',value=name)]
                fences.append(dict(name=name,hr=str(1/p),rtp=str(p*payout),avg_win=str(payout),
                    identity_condition=dict(search=search,opposite=False,win_range_start=-1,win_range_end=-1)))
                forces.append(dict(search=search,timesTriggered=1,bookIds=[i]))
            config=dict(game_id='probe',bet_modes=[dict(bet_mode='base',cost=1,rtp=50,max_win=5000)],
                fences=[dict(bet_mode='base',fences=fences)],dresses=[dict(bet_mode='base',dresses=[])],
                bias=[dict(bet_mode='base',bias=[])])
            (library/'configs/math_config.json').write_text(json.dumps(config))
            (library/'forces/force_record_base.json').write_text(json.dumps(forces))
            (library/'lookup_tables/lookUpTable_base.csv').write_text(''.join(f'{i},1,{pay*100}\n' for i,(_,pay,_) in enumerate(specs)))
            setup=dict(game_name='probe',bet_type='base',path_to_games=str(root/'games'),
                num_show_pigs=4,num_pigs_per_fence=4,threads_for_fence_construction=1,
                threads_for_show_construction=1,score_type='rtp',test_spins=[1],test_spins_weights=[1.0],
                simulation_trials=2,run_1000_batch=False,min_mean_to_median=0.0,
                max_mean_to_median=1000000.0,pmb_rtp=0.0,max_trial_dist=5)
            (root/'src/setup.toml').write_text('\n'.join(f'{k} = {json.dumps(v)}' for k,v in setup.items()))
            result=subprocess.run([str(BINARY)],cwd=root,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            with (library/'publish_files/lookUpTable_base_0.csv').open() as f:
                rows=[tuple(map(int,r)) for r in csv.reader(f)]
            total=sum(w for _,w,_ in rows)
            self.assertEqual(len(rows),4)
            for i,w,payout in rows:
                self.assertEqual(payout,specs[i][1]*100)
                self.assertAlmostEqual(w/total,specs[i][2],places=12)
            self.assertAlmostEqual(sum(w*p for _,w,p in rows)/(total*100),50,places=10)

if __name__=='__main__':unittest.main()
