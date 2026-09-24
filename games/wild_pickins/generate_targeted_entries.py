"""Conditional natural reel-stop sampling; bonus mechanics remain unchanged."""
import argparse
from itertools import product
from math import prod
from pathlib import Path
import json
import zstandard
from experiment_random import ExperimentRandom
from reel_source import ReelSource, ReelSample
from generate_experimental import generate_round
from experiment_evidence import archive_inputs, finish_evidence

class ConditionalEntry:
    def __init__(self, strips, scatters):
        self.source=ReelSource(strips)
        self.stops=[[[i for i in range(len(s)) if sum(s[(i+y)%len(s)]=='S' for y in range(3))==n]
            for n in (0,1)] for s in self.source.strips]
        self.patterns=[]
        for pattern in product((0,1),repeat=5):
            if sum(pattern)==scatters:
                count=prod(len(self.stops[r][v]) for r,v in enumerate(pattern))
                if count:self.patterns.append((pattern,count))
        self.count=sum(count for _,count in self.patterns)
        if not self.count:raise ValueError('Requested scatter count has no valid reel stops')
    def draw(self, seed, identity):
        rng=ExperimentRandom(seed,identity).stream('basegame',0,'conditional-entry-stops')
        ticket=rng.randrange(self.count)
        for pattern,count in self.patterns:
            if ticket<count:break
            ticket-=count
        stops=tuple(rng.choice(self.stops[r][v]) for r,v in enumerate(pattern))
        strips=self.source.strips
        return ReelSample([[s[(i+y)%len(s)] for y in range(3)] for s,i in zip(strips,stops)],stops,
            tuple(s[(i-1)%len(s)] for s,i in zip(strips,stops)),tuple(s[(i+3)%len(s)] for s,i in zip(strips,stops)))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds',type=int,default=1000);p.add_argument('--seed',type=int,default=9222)
    p.add_argument('--entry',type=int,choices=(15,20),required=True);p.add_argument('--start',type=int,required=True)
    a=p.parse_args()
    if a.rounds<1 or a.start<0:p.error('Invalid count or ID')
    config=json.loads(a.config.read_text());sampler=ConditionalEntry(config['reels']['basegame'],4 if a.entry==15 else 5)
    a.output.mkdir(parents=True,exist_ok=False)
    provenance=archive_inputs(a.config.read_bytes(),a.output,a.seed,a.rounds,'generate_targeted_entries.py')
    note=dict(sampling='uniform reel-stop tuples conditioned on exact scatter count',entry=a.entry,
        start=a.start,endExclusive=a.start+a.rounds,seed=a.seed,conditionalStopTuples=sampler.count,
        naturalStopTuples=prod(len(s) for s in sampler.source.strips),
        warning='Deliberately sampled entry stratum; uniform pool weights are NOT natural paid-game probabilities.')
    (a.output/'sampling.json').write_text(json.dumps(note,indent=2))
    with (a.output/'books_base.jsonl.zst').open('wb') as raw,zstandard.ZstdCompressor().stream_writer(raw) as out,(a.output/'lookUpTable_base.csv').open('w') as lookup:
        for offset in range(a.rounds):
            identity=a.start+offset
            book,_=generate_round(config,a.seed,identity,base_sample=sampler.draw(a.seed,identity))
            triggers=[e['totalFs'] for e in book['events'] if e['type']=='freeSpinTrigger']
            if triggers!=[a.entry]:raise ValueError('Unexpected entry award')
            out.write((json.dumps(book,separators=(',',':'))+'\n').encode())
            lookup.write(f"{identity},1,{book['payoutMultiplier']}\n")
            if (offset+1)%100==0:print(f'{a.entry}-spin: {offset+1}/{a.rounds}',flush=True)
    (a.output/'report.json').write_text(json.dumps(dict(note,rounds=a.rounds,status='complete'),indent=2))
    finish_evidence(a.output,provenance)

if __name__=='__main__':main()
