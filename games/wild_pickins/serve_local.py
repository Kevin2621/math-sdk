"""Loopback-only, no-money generated-round service for local frontend playtesting."""
import argparse
from functools import lru_cache
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from generate_experimental import generate_round
from weighted_playtest import load_profile, HASHES
from candidate_playtest import response as candidate_response

CONFIG_PATH=Path(__file__).parent/'experiments/wp25-separate-bonus.json'
CONFIG=json.loads(CONFIG_PATH.read_text())
CONFIG_HASH=hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
MULTIPLIER_PATH=Path(__file__).parent/'experiments/wp25-split4060-hit25.json'
MULTIPLIER_CONFIG=json.loads(MULTIPLIER_PATH.read_text())
MULTIPLIER_HASH=hashlib.sha256(MULTIPLIER_PATH.read_bytes()).hexdigest()

@lru_cache(maxsize=2)
def weighted_profile(profile):
    return load_profile(profile, CONFIG)

@lru_cache(maxsize=128)
def round_response(seed, identity, profile='natural'):
    if profile in ('candidate-1','candidate-3','candidate-500k-1'):
        return candidate_response(seed,identity,profile)
    source_id=identity
    config_hash=CONFIG_HASH
    if profile=='multiplier-wilds':
        _,book=generate_round(MULTIPLIER_CONFIG,seed,identity)
        config_hash=MULTIPLIER_HASH
    elif profile=='natural':
        _,book=generate_round(CONFIG,seed,identity)
    else:
        table,source_seed=weighted_profile(profile)
        source_id,expected=table.sample(seed,identity,profile)
        sdk,book=generate_round(CONFIG,source_seed,source_id)
        if sdk['payoutMultiplier']!=expected:raise ValueError('Weighted source payout mismatch')
    encoded=json.dumps(book,separators=(',',':'))
    return dict(protocol='wp-local-1',seed=seed,roundId=identity,profile=profile,sourceBookId=source_id,lookupSha256=HASHES.get(profile),configSha256=config_hash,
        bookJson=encoded,sha256=hashlib.sha256(encoded.encode()).hexdigest())

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        origin=self.headers.get('Origin')
        allowed={'http://localhost:6011','http://127.0.0.1:6011'}
        if origin and origin not in allowed:
            self.send_error(403,'Local Storybook origin required');return
        try:
            url=urlparse(self.path)
            if url.path=='/health':payload=dict(status='ready',configSha256=CONFIG_HASH)
            elif url.path=='/round':
                args=parse_qs(url.query,strict_parsing=True)
                if set(args) not in ({'seed','id'},{'seed','id','profile'}):raise ValueError('seed and id required')
                seed=int(args['seed'][0]);identity=int(args['id'][0])
                if not 0<=seed<=2**32-1 or not 0<=identity<1000000:raise ValueError('Invalid round identity')
                payload=round_response(seed,identity,args.get('profile',['natural'])[0])
            else:self.send_error(404);return
            encoded=json.dumps(payload,separators=(',',':')).encode()
            self.send_response(200)
            if origin:self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers();self.wfile.write(encoded)
        except (ValueError,KeyError):self.send_error(400,'Invalid round request')
    def log_message(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8025)
    a=p.parse_args()
    print(f'Wild Pickins local math: http://127.0.0.1:{a.port} (no money)',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
