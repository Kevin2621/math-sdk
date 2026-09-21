import json
from pathlib import Path
import tempfile
import unittest
from remote_optimizer import prepare, evaluate, ROOT

class RemoteOptimizerTests(unittest.TestCase):
    def test_profiles_preserve_entry_and_move_only_selected_base_probability(self):
        source=ROOT/'wild-pickins/reports/math/separate-bonus-seed58-20000'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            manifests=[]
            for profile in ('reference','quieter-base'):
                out=root/profile
                prepare(source,out,profile,1,10,2,2)
                m=json.loads((out/'manifest.json').read_text());manifests.append(m)
                self.assertAlmostEqual(sum(v['returnContribution'] for v in m['targets'].values()),.967)
                self.assertAlmostEqual(sum(v['probability'] for v in m['targets'].values()),1)
                self.assertIn('path_to_games = "./games"',(out/'src/setup.toml').read_text())
                config=json.loads((out/'games/wild_pickins/library/configs/math_config.json').read_text())
                self.assertEqual(config['fences'][0]['fences'][0]['name'], 'bonus')
            a,b=[m['targets'] for m in manifests]
            self.assertEqual(a['bonus']['probability'],b['bonus']['probability'])
            self.assertEqual(a['base_other'],b['base_other'])
            self.assertAlmostEqual(b['base_2_to_3']['probability'],a['base_2_to_3']['probability']*.8)
            self.assertGreater(b['bonus']['meanX'],a['bonus']['meanX'])
            # A source tamper must fail before any optimizer output is admitted.
            m=manifests[0];m['sourceHashes']['experiment-config.json']='wrong'
            (root/'reference/manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'Source changed'):
                evaluate(source,root/'reference')
