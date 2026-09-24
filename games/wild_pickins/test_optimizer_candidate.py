import copy
import unittest
import tempfile
import json
from pathlib import Path
from optimizer_candidate import labels, summarize, check_targets, band, load_prepared, digest


def book(i, base, awards=(), entry=0):
    events=[]
    for n, amount in enumerate((base,)+tuple(awards)):
        events.append(dict(type='wildPickinsSpinResult',spinWin=amount,harvestTopUp=0,
            endReason=None,stickyAfter=[{}]*n,nominalCollisionAward=0,grantedExtraSpins=0))
        if n==0 and entry: events.append(dict(type='freeSpinTrigger',totalFs=entry))
    events.append(dict(type='finalWin',amount=base+sum(awards)))
    return dict(id=i,payoutMultiplier=base+sum(awards),events=events)


class CandidateTests(unittest.TestCase):
    def test_boundaries_zero_bonus_and_cap_entry(self):
        self.assertEqual([band(x) for x in (999,1000,2999,3000,9999,10000,50000)],
            ['below10','10to30','10to30','30to100','30to100','100to500','500plus'])
        self.assertEqual(labels(book(0,0,[0],10),500000)['group'],'entry10_below10')
        r=labels(book(1,100,[499900],20),500000)
        self.assertEqual(r['group'],'entry20_cap')
        self.assertEqual(r['bonus'],499900)
        bad=book(2,0);bad['payoutMultiplier']=1
        with self.assertRaises(ValueError): labels(bad,500000)

    def test_component_cash_and_weighted_conditionals(self):
        rows=[labels(book(0,0),500000),labels(book(1,50),500000),
              labels(book(2,100,[2000,3000],10),500000),labels(book(3,0,[0],20),500000)]
        result=summarize(rows,[(0,5,0),(1,2,50),(2,2,5100),(3,1,0)])
        self.assertAlmostEqual(result['baseReturn'],.3)
        self.assertAlmostEqual(result['bonusReturn'],10)
        self.assertAlmostEqual(result['totalReturn'],10.3)
        self.assertEqual(result['bonus']['medianX'],50)
        self.assertAlmostEqual(result['bonus']['bands']['30to100'],2/3)
        self.assertAlmostEqual(result['baseHitRate'],.4)
        self.assertEqual(result['entries']['15']['meanX'],None)
        self.assertAlmostEqual(result['bonus']['progressionConditionalOnReachingSpin'][1]['reachProbability'],2/3)
        for lookup in ([(0,1,0)],[(r['id'],1,r['payout']+1) for r in rows],
                       [(r['id'],0,r['payout']) for r in rows]):
            with self.assertRaises(ValueError):summarize(rows,lookup)

    def test_changed_prepared_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'metadata.json').write_text('[]')
            manifest=dict(source=directory,sourceHashes={},
                artifactHashes={'metadata.json':digest(root/'metadata.json')})
            (root/'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(load_prepared(root),[])
            (root/'metadata.json').write_text('[{}]')
            with self.assertRaisesRegex(ValueError,'Changed evidence'):
                load_prepared(root)

    def test_support_and_probability_budget(self):
        rows=[labels(book(0,0),500000),labels(book(1,200),500000)]
        targets=dict(totalReturn=.5,groups={'base_zero':dict(probability=.75,meanTotalX=0),
            'base_profit':dict(probability=.25,meanTotalX=2)})
        result=check_targets(rows,targets)
        self.assertEqual(result['totalReturn'],.5)
        self.assertEqual(result['fences'][1]['identity_condition']['win_range_start'],-1)
        for key,value in [('probability',.3),('meanTotalX',3)]:
            bad=copy.deepcopy(targets);bad['groups']['base_profit'][key]=value
            with self.assertRaises(ValueError): check_targets(rows,bad)

if __name__=='__main__': unittest.main()
