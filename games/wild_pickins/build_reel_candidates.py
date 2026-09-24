"""Build controlled Wild Pickins candidates without changing the active game."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from src.reels.generator import construct, trigger_probability

HERE = Path(__file__).parent


def counts(reel, wilds, skew):
    # Rotating abundant low symbols reduce common matches across adjacent reels.
    result = {f'C{i:02}': 8 for i in range(1, 9)}
    result.update(S=8, W=wilds)
    remaining = 240 - sum(result.values())
    lows = [f'C{i:02}' for i in range(4, 9)]
    heavy = lows[reel % 5]
    extra = round(remaining * skew)
    result[heavy] += extra
    for i in range(remaining-extra):
        result[lows[i % 5]] += 1
    return result


def build(output, seed=9060, max_visible_scatters=1):
    if output.exists():
        raise ValueError('Output exists; use a new directory')
    if max_visible_scatters != 1:
        raise ValueError('Generator supports other limits; Wild Pickins runtime currently requires one')
    baseline = json.loads((HERE/'experiments/wp25-comparison-picks-off.json').read_text())
    # 8 scatters / 240 stops * 3 rows = 10% per reel; >=3 of 5 = .00856.
    specs = [('reference', 4, .5, 6, 0),
             ('base-skew-low', 4, .25, 6, 0), ('base-skew-high', 4, .75, 6, 0),
             ('base-wild-low', 3, .5, 6, 0), ('base-wild-high', 5, .5, 6, 0),
             ('base-spacing', 4, .5, 6, 1),
             ('bonus-wild-low', 4, .5, 4, 0), ('bonus-wild-high', 4, .5, 8, 0)]
    prepared = []
    for name, base_wilds, skew, bonus_wilds, order in specs:
        config = deepcopy(baseline)
        for mode, wilds, mix in [('basegame', base_wilds, skew), ('freegame', bonus_wilds, .25)]:
            config['reels'][mode] = [construct(counts(r, wilds, mix),
                seed=seed+r+(100 if mode == 'freegame' else order*1000),
                visible_limits={'S': max_visible_scatters}) for r in range(5)]
        p = trigger_probability(config['reels']['basegame'], 'S', 3)
        assert 1/150 <= p <= 1/100
        config['mathVersion'] = 'experimental-strips-' + name
        config['description'] = 'Step 4 candidate; unbalanced and not selected for playback.'
        prepared.append((name, config, dict(name=name, baseWilds=base_wilds,
            baseSkew=skew, bonusWilds=bonus_wilds, baseOrderVariant=order,
            bonusEntryProbability=p, meanEntryInterval=1/p)))
    output.mkdir(parents=True)
    manifest = dict(seed=seed, stripLength=240, maxVisibleScatters=max_visible_scatters,
        status='Construction candidates only; not fitted or approved', candidates=[])
    for name, config, record in prepared:
        data = (json.dumps(config, indent=2)+'\n').encode()
        (output/(name+'.json')).write_bytes(data)
        record['sha256'] = hashlib.sha256(data).hexdigest()
        record['counts'] = {m: [dict(Counter(s)) for s in strips] for m, strips in config['reels'].items()}
        manifest['candidates'].append(record)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=9060)
    parser.add_argument('--max-visible-scatters', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.seed, args.max_visible_scatters), indent=2))
