"""Checkpointed rejection sample of valid 20-spin entries that reach the round cap."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import fcntl
import zstandard
from generate_targeted_entries import ConditionalEntry
from generate_experimental import generate_round
from experiment_evidence import archive_inputs, finish_evidence


def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value));temp.replace(path)


def worker(root, lane, target):
    root=Path(root);folder=root/f'worker{lane}';folder.mkdir(exist_ok=True)
    config=json.loads((root/'experiment-config.json').read_text())
    sampler=ConditionalEntry(config['reels']['basegame'],5)
    state=folder/'progress.json'
    progress=json.loads(state.read_text()) if state.exists() else dict(attempts=0,accepted=0)
    # Saved accepted books are authoritative even if interruption preceded progress commit.
    saved=list(folder.glob('book-*.json'))
    accepted=len(saved)
    attempt=max([progress['attempts']]+[int(p.stem.split('-')[1])-2000000-lane*10000000+1 for p in saved])
    while accepted<target:
        if attempt>=10000000:raise ValueError('Lane ID range exhausted')
        identity=2000000+lane*10000000+attempt
        book,_=generate_round(config,9223,identity,base_sample=sampler.draw(9223,identity))
        attempt+=1
        if book['payoutMultiplier']==config['roundCap']:
            atomic(folder/f'book-{identity}.json',book);accepted+=1
        if attempt%100==0 or accepted==target:
            atomic(state,dict(attempts=attempt,accepted=accepted,target=target))
        if attempt%1000==0 or accepted==target:
            print(f'Worker {lane}: {accepted}/{target} max wins, {attempt} attempts',flush=True)
    return dict(attempts=attempt,accepted=accepted)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=a.resume)
    with (a.output/'run.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signature={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [a.config]+list(Path(__file__).parent.glob('*.py'))}
        if a.resume:
            if json.loads((a.output/'signature.json').read_text())!=signature:raise ValueError('Source changed')
            provenance=json.loads((a.output/'run-provenance.json').read_text())
        else:
            provenance=archive_inputs(a.config.read_bytes(),a.output,9223,200,'collect_maxwin_samples.py')
            atomic(a.output/'run-provenance.json',provenance);atomic(a.output/'signature.json',signature)
            atomic(a.output/'sampling.json',dict(entry=20,seed=9223,target=200,
                sampling='Uniform valid five-scatter stops; natural bonus draws; reject non-cap rounds',
                warning='Conditional on 20-spin entry AND round cap. Not natural RTP or max-win probability. Attempts use disjoint ID lanes starting 2000000,12000000,22000000,32000000.'))
        atomic(a.output/'status.json',dict(status='running',target=200))
        with ProcessPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(worker,str(a.output.resolve()),i,50) for i in range(4)]
            results=[f.result() for f in futures]
        books=sorted([json.loads(f.read_text()) for f in a.output.glob('worker*/book-*.json')],key=lambda b:b['id'])
        assert len(books)==200 and len({b['id'] for b in books})==200
        with (a.output/'books_base.jsonl.zst').open('wb') as raw,zstandard.ZstdCompressor().stream_writer(raw) as out,(a.output/'lookUpTable_base.csv').open('w') as lookup:
            for b in books:
                out.write((json.dumps(b,separators=(',',':'))+'\n').encode());lookup.write(f"{b['id']},1,{b['payoutMultiplier']}\n")
        atomic(a.output/'report.json',dict(rounds=200,attempts=sum(r['attempts'] for r in results),workers=results,conditionalOnly=True))
        finish_evidence(a.output,provenance)
        atomic(a.output/'status.json',dict(status='complete',rounds=200))

if __name__=='__main__':main()
