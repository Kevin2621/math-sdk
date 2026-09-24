"""Archive exact local experiment inputs and hash completed output artifacts."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

ROOT=Path(__file__).resolve().parents[3]

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def archive_inputs(config_bytes,output,seed,rounds,runner):
    config=json.loads(config_bytes)
    (output/'experiment-config.json').write_bytes(config_bytes)
    paths=list((ROOT/'math-sdk/games/wild_pickins').glob('*.py'))
    paths.append(ROOT/'math-sdk/games/wild_pickins/balance_criteria.json')
    paths+=list((ROOT/'math-sdk/src').rglob('*.py'))
    paths+=[ROOT/'wild-pickins/tools/contract.py',ROOT/'wild-pickins/docs/rules.md']
    hashes={}
    for source in sorted(paths):
        name=source.relative_to(ROOT).as_posix()
        data=source.read_bytes();hashes[name]=hashlib.sha256(data).hexdigest()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    manifest=dict(seed=seed,rounds=rounds,runner=runner,rngScheme=config.get('rngScheme','legacy'),
        configSha256=hashlib.sha256(config_bytes).hexdigest(),sourceHashes=hashes,
        sourceDigest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        pythonVersion=platform.python_version(),pythonImplementation=platform.python_implementation(),
        zstandardVersion=version('zstandard'))
    (output/'reproducibility.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def finish_evidence(output,manifest):
    manifest['artifactHashes']={p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name!='reproducibility.json'}
    (output/'reproducibility.json').write_text(json.dumps(manifest,indent=2)+'\n')
