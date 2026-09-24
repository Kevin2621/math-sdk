"""Immutable recorded-book playback for expanded candidates 1 and 3; local only."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zlib
from bisect import bisect_right
from random import Random
from functools import lru_cache
import zstandard
from generate_experimental import ROOT
from contract import validate

PACKAGE=ROOT/'wild-pickins/reports/math/candidate-playtests-1-3'

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def package(run_name=None,profile=None):
    global PACKAGE
    if run_name:
        PACKAGE=ROOT/'wild-pickins/reports/math'/f'{profile}-playtest'
    PACKAGE.mkdir(parents=True,exist_ok=False)
    math=ROOT/'wild-pickins/reports/math'
    manifest=json.loads((math/(run_name or 'rust-expanded-base1')/'manifest.json').read_text())
    sources=[(Path(s['manifest']['source']),False,s['manifest']) for s in manifest['sources']]
    extra=manifest['additionalBase']
    if extra:sources.append((Path(extra['manifest']['source']),True,extra['manifest']))
    sources.extend((Path(s['manifest']['source']),False,s['manifest']) for s in manifest.get('supplements',[]))
    profiles={};expected=None
    for number in ((1,) if run_name else (1,3)):
        run=math/(run_name or f'rust-expanded-base{number}')
        key=profile or f'candidate-{number}'
        other=json.loads((run/'manifest.json').read_text())
        assert other['sources']==manifest['sources'] and other['additionalBase']==extra
        lookup=run/'games/wild_pickins/library/publish_files/lookUpTable_base_0.csv'
        assert sha(lookup)==json.loads((run/'evaluation.json').read_text())['lookupSha256']
        with lookup.open() as f:
            rows=[tuple(map(int,r)) for r in csv.reader(f)]
        mapping={i:p for i,w,p in rows}
        assert len(mapping)==len(rows) and all(w>=0 for i,w,p in rows)
        if expected is None:expected=mapping
        else:assert expected==mapping
        target=PACKAGE/f'{key}.csv';target.write_bytes(lookup.read_bytes())
        profiles[key]=dict(lookup=target.name,lookupSha256=sha(target))
    config_path=sources[0][0]/'experiment-config.json'
    config=json.loads(config_path.read_text());config_hash=sha(config_path)
    (PACKAGE/'experiment-config.json').write_bytes(config_path.read_bytes())
    connection=sqlite3.connect(PACKAGE/'books.sqlite')
    connection.execute('CREATE TABLE books (id INTEGER PRIMARY KEY,payout INTEGER NOT NULL,data BLOB NOT NULL)')
    count=0
    for source,base_only,evidence in sources:
        for name,digest in evidence['sourceHashes'].items():
            if sha(source/name)!=digest:raise ValueError('Source changed')
        assert sha(source/'experiment-config.json')==config_hash
        with (source/'books_base.jsonl.zst').open('rb') as raw,zstandard.ZstdDecompressor().stream_reader(raw) as stream,io.TextIOWrapper(stream) as lines:
            for line in lines:
                b=json.loads(line)
                if base_only and any(e['type']=='freeSpinTrigger' for e in b['events']):continue
                if expected.pop(b['id'],None)!=b['payoutMultiplier']:raise ValueError('Book ID/payout mismatch')
                connection.execute('INSERT INTO books VALUES (?,?,?)',(b['id'],b['payoutMultiplier'],zlib.compress(line.encode())))
                count+=1
        connection.commit();print(f'Packaged {count} books',flush=True)
    assert not expected
    connection.close()
    result=dict(status='complete',rounds=count,profiles=profiles,configSha256=config_hash,booksSha256=sha(PACKAGE/'books.sqlite'),
        note='Local experimental playtests. Original strict component gates remain unmet; no production approval. Immutable source pool for the selected run; no payout or probability changes during packaging.')
    (PACKAGE/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

def package_path(profile):
    return ROOT/'wild-pickins/reports/math/candidate-500k-1-playtest' if profile=='candidate-500k-1' else ROOT/'wild-pickins/reports/math/candidate-playtests-1-3'

@lru_cache(maxsize=3)
def assets(profile='candidate-1'):
    PACKAGE=package_path(profile)
    m=json.loads((PACKAGE/'manifest.json').read_text())
    if m['status']!='complete' or sha(PACKAGE/'books.sqlite')!=m['booksSha256'] or sha(PACKAGE/'experiment-config.json')!=m['configSha256']:
        raise ValueError('Candidate package integrity mismatch')
    return m,json.loads((PACKAGE/'experiment-config.json').read_text())

@lru_cache(maxsize=3)
def table(profile):
    m,_=assets(profile);PACKAGE=package_path(profile);info=m['profiles'][profile];path=PACKAGE/info['lookup']
    if sha(path)!=info['lookupSha256']:raise ValueError('Candidate lookup changed')
    ids=[];totals=[];payouts=[];total=0
    with path.open() as f:
        for i,w,p in csv.reader(f):
            total+=int(w);ids.append(int(i));totals.append(total);payouts.append(int(p))
    if total<=0:raise ValueError('Empty candidate weights')
    return ids,totals,payouts

def recorded(profile,identity):
    m,config=assets(profile)
    PACKAGE=package_path(profile)
    with sqlite3.connect(f'file:{PACKAGE}/books.sqlite?mode=ro',uri=True) as db:
        row=db.execute('SELECT payout,data FROM books WHERE id=?',(identity,)).fetchone()
    if row is None:raise ValueError('Missing recorded round')
    sdk=json.loads(zlib.decompress(row[1]));assert sdk['payoutMultiplier']==row[0]
    book={k:config[k] for k in ('schemaVersion','gameId','lineSetId','mathVersion','assetMapVersion','spinBudget','roundCap','fixtureMath')}
    book.update(fixtureOnly=True,events=sdk['events']);validate(book)
    return book,row[0]

def response(seed,round_id,profile):
    m,_=assets(profile);ids,totals,payouts=table(profile)
    ticket=Random(f'wp-candidate:{profile}:{seed}:{round_id}').randrange(totals[-1])
    index=bisect_right(totals,ticket);identity=ids[index]
    book,payout=recorded(profile,identity)
    if payout!=payouts[index]:raise ValueError('Candidate payout mismatch')
    encoded=json.dumps(book,separators=(',',':'))
    return dict(protocol='wp-local-1',seed=seed,roundId=round_id,profile=profile,sourceBookId=identity,
        lookupSha256=m['profiles'][profile]['lookupSha256'],configSha256=m['configSha256'],bookJson=encoded,
        sha256=hashlib.sha256(encoded.encode()).hexdigest())

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run');p.add_argument('--profile');a=p.parse_args()
    if bool(a.run)!=bool(a.profile):p.error('Specify both run and profile')
    package(a.run,a.profile)
