"""Exact integer-weight sampling for the two reviewed local-only optimizer tables."""
from array import array
from bisect import bisect_right
import csv
import hashlib
import json
from pathlib import Path
from random import Random

ROOT=Path(__file__).resolve().parents[3]
HASHES={'reference':'d9be36cc8c295ea75c9589f11cf919f9a11d0597a2870da13827a7d46a896de0',
        'quieter-base':'dbf9181a1bbba7c68b922796c61002fc30d8f328f208eee99826cf590e3f4c72'}

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

class WeightedTable:
    def __init__(self,path,expected_hash):
        if sha(path)!=expected_hash:raise ValueError('Weighted lookup hash mismatch')
        self.ids=array('I');self.amounts=array('I');self.cumulative=array('Q');total=0
        with path.open() as f:
            for row in csv.reader(f):
                identity,weight,amount=map(int,row)
                if identity!=len(self.ids) or weight<0 or amount<0:raise ValueError('Invalid weighted lookup')
                total+=weight;self.ids.append(identity);self.amounts.append(amount);self.cumulative.append(total)
        if total<=0:raise ValueError('Empty weighted table')
        self.total=total
    def at(self,ticket):
        if not 0<=ticket<self.total:raise ValueError('Invalid ticket')
        index=bisect_right(self.cumulative,ticket)
        return self.ids[index],self.amounts[index]
    def sample(self,seed,round_id,profile):
        return self.at(Random(f'wp-weighted:{profile}:{seed}:{round_id}').randrange(self.total))

def load_profile(profile,config):
    if profile not in HASHES:raise ValueError('Unknown profile')
    run=ROOT/'wild-pickins/reports/optimizer-ready'/profile
    manifest=json.loads((run/'manifest.json').read_text())
    source=ROOT/'wild-pickins/reports/optimizer-handoff/wild-pickins-optimizer/runs/pool-2000000-seed60'
    if json.loads((source/'experiment-config.json').read_text())!=config:raise ValueError('Source configuration mismatch')
    for name,expected in manifest['sourceHashes'].items():
        if sha(source/name)!=expected:raise ValueError('Source hash mismatch')
    report=json.loads((source/'report.json').read_text())
    table=WeightedTable(run/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv',HASHES[profile])
    if len(table.ids)!=report['rounds']:raise ValueError('Source count mismatch')
    return table,report['seed']
