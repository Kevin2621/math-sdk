"""Controlled bonus-frequency experiment; preserves base inputs and scatter density."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def candidates(baseline):
    for name, reduce_wild, reduce_golden in (
        ('baseline', False, False), ('golden-half', False, True),
        ('wild-half', True, False), ('both-half', True, True),
    ):
        config = copy.deepcopy(baseline)
        config['description'] = f'Experimental bonus-frequency comparison: {name}; not production math.'
        if reduce_golden:
            config['goldenRates']['freegame'][1] *= 2
        if reduce_wild:
            # Duplicate the cyclic strip, replacing Wilds only in its second copy.
            # This halves Wild density while preserving scatter positions/density.
            config['reels']['freegame'] = [strip + [
                f'C{(r % 8) + 1:02d}' if symbol == 'W' else symbol for symbol in strip
            ] for r, strip in enumerate(config['reels']['freegame'])]
        yield name, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=43)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((HERE/'experiments/plumbing.json').read_text())
    comparison = []
    for name, config in candidates(baseline):
        config_path = args.output/f'{name}.json'
        config_path.write_text(json.dumps(config, indent=2)+'\n')
        run = args.output/name
        subprocess.run([sys.executable, str(HERE/'generate_experimental.py'), '--config', str(config_path),
                        '--rounds', str(args.rounds), '--seed', str(args.seed), '--output', str(run)],
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(HERE/'evaluate_experimental.py'), str(run)],
                       check=True, stdout=subprocess.DEVNULL)
        report = json.loads((run/'evaluation.json').read_text())
        comparison.append(dict(candidate=name, **report))
        print(f"{name}: return {report['observedReturn']*100:.4f}%, "
              f"Full Harvests {report['fullHarvestRounds']}, bonuses {report['bonusRounds']}", flush=True)
    (args.output/'comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')


if __name__ == '__main__':
    main()
