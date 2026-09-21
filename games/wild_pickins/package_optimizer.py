"""Create a self-contained source handoff, excluding binaries, caches and credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import io

ROOT=Path(__file__).resolve().parents[3]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    paths=[]
    for directory,pattern in [('math-sdk/games/wild_pickins','*.py'),('math-sdk/src','*.py'),('math-sdk/optimization_program/src','*.rs')]:
        paths.extend((ROOT/directory).rglob(pattern))
    paths.extend((ROOT/'math-sdk/games/wild_pickins/experiments').glob('*.json'))
    for name in ['math-sdk/optimization_program/Cargo.toml','math-sdk/optimization_program/Cargo.lock','wild-pickins/tools/contract.py','wild-pickins/docs/rules.md','wild-pickins/docs/remote-optimizer.md']:
        paths.append(ROOT/name)
    sample=ROOT/'wild-pickins/reports/math/separate-bonus-seed58-20000'
    paths.extend(sample/name for name in ('books_base.jsonl.zst','lookUpTable_base.csv','experiment-config.json','report.json','evaluation.json'))
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('xb') as raw,tarfile.open(fileobj=raw,mode='w:gz') as archive:
        for name in manifest:archive.add(ROOT/name,arcname='wild-pickins-optimizer/'+name,recursive=False)
        for name,data in [('MANIFEST.json',json.dumps(manifest,indent=2)+'\n'),('requirements-optimizer.txt','zstandard==0.23.0\n'),('README.md','Start with wild-pickins/docs/remote-optimizer.md. No optimizer results are included.\n')]:
            encoded=data.encode();info=tarfile.TarInfo('wild-pickins-optimizer/'+name);info.size=len(encoded);archive.addfile(info,io.BytesIO(encoded))
    print(a.output)
    print('sha256',hashlib.sha256(a.output.read_bytes()).hexdigest())

if __name__=='__main__':main()
