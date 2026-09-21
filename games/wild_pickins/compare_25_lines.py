"""Controlled 25-line experiment: one bonus Golden-rate factor, independent seeds."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=10000)
    parser.add_argument('--seeds', type=int, nargs='+', default=[47,48])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    comparison = []
    for seed in args.seeds:
        for candidate in ('golden20','golden10','golden05'):
            run = args.output/f'{candidate}-seed{seed}'
            with (args.output/f'{candidate}-seed{seed}.log').open('w') as log:
                subprocess.run([sys.executable,str(HERE/'generate_experimental.py'),
                    '--config',str(HERE/f'experiments/wp25-{candidate}.json'),
                    '--rounds',str(args.rounds),'--seed',str(seed),'--output',str(run)],
                    stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(HERE/'evaluate_experimental.py'),str(run)],
                    stdout=log,stderr=subprocess.STDOUT,check=True)
            report = json.loads((run/'evaluation.json').read_text())
            comparison.append(dict(candidate=candidate,**report))
            (args.output/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
            print(f"{candidate} seed {seed}: RTP {report['observedReturn']*100:.4f}%, Harvest {report['fullHarvestRounds']}, bonuses {report['bonusRounds']}",flush=True)

if __name__ == '__main__':
    main()
