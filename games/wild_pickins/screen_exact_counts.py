"""Archive and screen proposed high-count / low-concentration grid."""
import json
from copy import deepcopy
from pathlib import Path
from exact_base_return import calculate
from build_reel_candidates import counts
from src.reels.generator import construct
from experiment_evidence import archive_inputs,finish_evidence

if __name__=='__main__':
    root=Path('wild-pickins/reports/math/exact-counts-step4');root.mkdir(parents=True,exist_ok=False)
    base_path=Path('wild-pickins/reports/math/strips-step4/candidates/reference.json')
    raw=base_path.read_bytes();base=json.loads(raw);snapshot=root/'inputs';snapshot.mkdir()
    provenance=archive_inputs(raw,snapshot,9110,0,'screen_exact_counts.py')
    configs={}
    for name,path in [('original','math-sdk/games/wild_pickins/experiments/wp25-comparison-picks-off.json'),('reference',str(base_path)),('concentrated','wild-pickins/reports/math/strips-step4/candidates/base-skew-high.json')]:configs[name]=json.loads(Path(path).read_text())
    for copies in (16,20,24):
        for skew in (.25,.5,.75):
            c=deepcopy(base)
            for r in range(5):
                counts_map={f'C{i:02}':copies if i<=3 else 8 for i in range(1,9)};counts_map.update(W=4,S=8)
                remaining=240-sum(counts_map.values());heavy=round(remaining*skew)
                counts_map[f'C{4+r:02}']+=heavy
                for i in range(remaining-heavy):counts_map[f'C{4+i%5:02}']+=1
                c['reels']['basegame'][r]=construct(counts_map,seed=9110+r,visible_limits={'S':1})
            name=f'high-{copies}-skew-{skew}';c['mathVersion']='experimental-exact-'+name;c['description']='Exact count screen; not selected';configs[name]=c
    results={}
    for name,c in configs.items():
        (root/(name+'-config.json')).write_text(json.dumps(c,indent=2)+'\n')
        results[name]=calculate(c)
        print(name,results[name]['baseReturn'],flush=True)
    (root/'report.json').write_text(json.dumps(results,indent=2)+'\n')
    for p in root.glob('*.json'):(snapshot/p.name).write_bytes(p.read_bytes())
    finish_evidence(snapshot,provenance)
