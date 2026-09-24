"""Four-process paid-round pool generator with immutable 1,000-round checkpoints."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import os
import zstandard
from generate_experimental import generate_round
from experiment_evidence import archive_inputs, finish_evidence


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(root, start, count, seed):
    root=Path(root)
    config=json.loads((root/'experiment-config.json').read_text())
    for first in range(start,start+count,1000):
        end=min(first+1000,start+count)
        final=root/'chunks'/str(first)
        if final.exists():
            manifest=json.loads((final/'checkpoint.json').read_text())
            if manifest['start']!=first or manifest['end']!=end:
                raise ValueError('Checkpoint range mismatch')
            for name,digest in manifest['hashes'].items():
                if sha(final/name)!=digest:raise ValueError('Checkpoint changed')
            continue
        temp=root/'chunks'/f'{first}.partial'
        temp.mkdir(exist_ok=True)
        payout=entries=0
        with (temp/'books_base.jsonl.zst').open('wb') as raw, zstandard.ZstdCompressor().stream_writer(raw) as out, (temp/'lookUpTable_base.csv').open('w') as lookup:
            for identity in range(first,end):
                book,_=generate_round(config,seed,identity)
                out.write((json.dumps(book,separators=(',',':'))+'\n').encode())
                lookup.write(f"{identity},1,{book['payoutMultiplier']}\n")
                payout+=book['payoutMultiplier']
                entries+=any(e['type']=='freeSpinTrigger' for e in book['events'])
        checkpoint=dict(start=first,end=end,payout=payout,bonusEntries=entries,
            hashes={name:sha(temp/name) for name in ('books_base.jsonl.zst','lookUpTable_base.csv')})
        (temp/'checkpoint.json').write_text(json.dumps(checkpoint))
        temp.rename(final)
        print(f'Worker {start}: committed IDs {first}–{end-1}',flush=True)
    return start


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,default=9221);p.add_argument('--start',type=int,default=0)
    p.add_argument('--per-worker',type=int,default=25000);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.start<0 or min(a.workers,a.per_worker)<1:p.error('Invalid range')
    a.output.mkdir(parents=True,exist_ok=a.resume)
    with (a.output/'run.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signature=dict(seed=a.seed,start=a.start,perWorker=a.per_worker,workers=a.workers,
            configSha256=sha(a.config),sourceHashes={str(f.resolve()):sha(f) for folder in (Path(__file__).parent,Path(__file__).parents[2]/'src') for f in folder.rglob('*.py')})
        state=a.output/'batch.json'
        if a.resume:
            if json.loads(state.read_text())['signature']!=signature:raise ValueError('Resume source/config mismatch')
            provenance=json.loads((a.output/'batch-provenance.json').read_text())
        else:
            provenance=archive_inputs(a.config.read_bytes(),a.output,a.seed,a.workers*a.per_worker,'generate_pool_batch.py')
            (a.output/'batch-provenance.json').write_text(json.dumps(provenance))
            (a.output/'chunks').mkdir()
        state.write_text(json.dumps(dict(status='running',signature=signature),indent=2))
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            futures=[pool.submit(worker,str(a.output.resolve()),a.start+i*a.per_worker,a.per_worker,a.seed) for i in range(a.workers)]
            for future in futures:future.result()
        chunks=sorted((d for d in (a.output/'chunks').iterdir() if d.name.isdigit()),key=lambda d:int(d.name))
        for name in ('books_base.jsonl.zst','lookUpTable_base.csv'):
            with (a.output/(name+'.partial')).open('wb') as out:
                for chunk in chunks:
                    with (chunk/name).open('rb') as stream:shutil.copyfileobj(stream,out)
            os.replace(a.output/(name+'.partial'),a.output/name)
        with (a.output/'lookUpTable_base.csv').open() as f:
            for expected,row in enumerate(csv.reader(f),a.start):
                if int(row[0])!=expected:raise ValueError('Merged IDs not contiguous')
            if expected!=a.start+a.workers*a.per_worker-1:raise ValueError('Wrong merged count')
        reports=[json.loads((d/'checkpoint.json').read_text()) for d in chunks]
        report=dict(rounds=a.workers*a.per_worker,start=a.start,endExclusive=a.start+a.workers*a.per_worker,
            seed=a.seed,bonusEntries=sum(r['bonusEntries'] for r in reports),
            observedMeanReturn=sum(r['payout'] for r in reports)/(100*a.workers*a.per_worker),experimentalOnly=True)
        (a.output/'report.json').write_text(json.dumps(report,indent=2))
        finish_evidence(a.output,provenance)
        state.write_text(json.dumps(dict(status='complete',signature=signature),indent=2))
        print(json.dumps(report),flush=True)

if __name__=='__main__':main()
