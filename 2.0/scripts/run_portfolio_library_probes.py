#!/usr/bin/env python3
"""Run minimal portfolio-library capability probes in disposable Podman volumes."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "evidence/challenger_program_v1/source_queue.csv"
OUTPUT = ROOT / "evidence/portfolio_libraries_batch_11/capability_probes"
IMAGE = "docker.io/library/python:3.12-bookworm"

INSTALL = r'''
import os, pathlib, shutil, subprocess, sys, tarfile, urllib.request
work=pathlib.Path('/work'); archive=work/'source.tar.gz'; parent=work/'source'; repo=work/'repository'
request=urllib.request.Request(f"https://github.com/{os.environ['REPOSITORY']}/archive/{os.environ['HEAD_COMMIT']}.tar.gz",headers={'User-Agent':'portfolio-optimizer-2.0-probe'})
with urllib.request.urlopen(request,timeout=120) as response, archive.open('wb') as output: shutil.copyfileobj(response,output)
parent.mkdir()
with tarfile.open(archive,'r:gz') as bundle:
    for member in bundle.getmembers():
        path=pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts: raise RuntimeError('unsafe archive')
    bundle.extractall(parent,filter='data')
root=next(path for path in parent.iterdir() if path.is_dir()); shutil.move(str(root),repo)
subprocess.run([sys.executable,'-m','venv','/work/venv'],check=True)
environment=os.environ.copy()
if os.environ.get('REPOSITORY')=='cvxgrp/cvxportfolio':
    environment['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CVXPORTFOLIO']='0.0.0'
if os.environ.get('REPOSITORY')=='robertmartin8/PyPortfolioOpt':
    subprocess.run(['/work/venv/bin/pip','install','--disable-pip-version-check','--no-cache-dir','packaging'],check=True)
subprocess.run(['/work/venv/bin/pip','install','--disable-pip-version-check','--no-cache-dir','-e','.'],cwd=repo,env=environment,check=True)
with (work/'pip-freeze.txt').open('w') as output: subprocess.run(['/work/venv/bin/pip','freeze','--all'],stdout=output,text=True,check=True)
print('MINIMAL_INSTALL_COMPLETE')
'''

COMMON_DATA = r'''
import json, numpy as np, pandas as pd
rng=np.random.default_rng(20260809)
base=rng.normal(0.001,0.02,size=(160,4))
base[:,1]=0.35*base[:,0]+0.65*base[:,1]
X=pd.DataFrame(base,columns=['A','B','C','D'])
'''

PROBES = {
    "ast-0187": COMMON_DATA + r'''
from pypfopt import EfficientFrontier, expected_returns, risk_models
mu=expected_returns.mean_historical_return(100*(1+X).cumprod(),frequency=52)
cov=risk_models.CovarianceShrinkage(100*(1+X).cumprod(),frequency=52).ledoit_wolf()
ef=EfficientFrontier(mu,cov,weight_bounds=(0,0.35)); ef.min_volatility(); weights=ef.clean_weights()
print('PROBE_JSON='+json.dumps({'capability':'minimum_variance','weights':weights,'sum':sum(weights.values()),'max':max(weights.values())},sort_keys=True))
''',
    "ast-0184": COMMON_DATA + r'''
from skfolio.optimization import MeanRisk
from skfolio import RiskMeasure
model=MeanRisk(risk_measure=RiskMeasure.VARIANCE,min_weights=0.0,max_weights=0.35)
model.fit(X)
weights={name:float(value) for name,value in zip(X.columns,model.weights_,strict=True)}
print('PROBE_JSON='+json.dumps({'capability':'minimum_variance','weights':weights,'sum':sum(weights.values()),'max':max(weights.values())},sort_keys=True))
''',
    "ast-0185": COMMON_DATA + r'''
import riskfolio as rp
portfolio=rp.Portfolio(returns=X); portfolio.upperlng=0.35; portfolio.assets_stats(method_mu='hist',method_cov='hist')
weights_frame=portfolio.optimization(model='Classic',rm='MV',obj='MinRisk',rf=0,hist=True)
weights={name:float(weights_frame.loc[name].iloc[0]) for name in X.columns}
print('PROBE_JSON='+json.dumps({'capability':'minimum_variance','weights':weights,'sum':sum(weights.values()),'max':max(weights.values())},sort_keys=True))
''',
    "ast-0183": COMMON_DATA + r'''
import cvxportfolio as cp
sigma=X.cov()*52
r_hat=X.mean()*52
objective=cp.ReturnsForecast(r_hat=r_hat)-5.0*cp.FullCovariance(Sigma=sigma)
policy=cp.SinglePeriodOptimization(objective,[cp.LongOnly(),cp.LeverageLimit(1)])
print('PROBE_JSON='+json.dumps({'capability':'policy_construction','policy_type':type(policy).__name__,'assets':list(X.columns)},sort_keys=True))
''',
}


def limits() -> list[str]:
    return ["--read-only", "--cap-drop=all", "--security-opt=no-new-privileges", "--pids-limit=256", "--memory=2g", "--cpus=1", "--tmpfs", "/tmp:rw,exec,nosuid,size=1g"]


def run(row: dict[str, str], timeout: int) -> dict[str, object]:
    entry = row["entry_id"]
    safe = re.sub(r"[^a-z0-9_.-]", "-", entry.lower())
    volume = f"po2-library-probe-{safe}"
    subprocess.run(["podman", "volume", "create", volume], check=True, capture_output=True)
    started = datetime.now(timezone.utc).isoformat()
    try:
        install_started = time.monotonic()
        install = subprocess.run([
            "podman", "run", "--rm", "--interactive", "--name", f"{volume}-install",
            *limits(), "--volume", f"{volume}:/work:rw", "--env", f"REPOSITORY={row['repository']}",
            "--env", f"HEAD_COMMIT={row['head_commit']}", "--entrypoint", "python", IMAGE, "-",
        ], input=INSTALL, text=True, capture_output=True, timeout=timeout, check=False)
        install_seconds = int(time.monotonic()-install_started)
        if install.returncode != 0:
            return {"entry_id":entry,"repository":row["repository"],"commit":row["head_commit"],"status":"minimal_install_failed","started_at":started,"install_seconds":install_seconds,"probe_seconds":0,"network_disabled_during_probe":True,"host_mounts":False,"result":{},"install_log":(install.stdout+'\n'+install.stderr)[-12000:],"probe_log":""}
        probe_started = time.monotonic()
        probe = subprocess.run([
            "podman", "run", "--rm", "--interactive", "--name", f"{volume}-test", "--network=none",
            *limits(), "--volume", f"{volume}:/work:rw", "--workdir", "/work/repository",
            "--entrypoint", "/work/venv/bin/python", IMAGE, "-",
        ], input=PROBES[entry], text=True, capture_output=True, timeout=timeout, check=False)
        probe_seconds = int(time.monotonic()-probe_started)
        marker = next((line[11:] for line in probe.stdout.splitlines() if line.startswith("PROBE_JSON=")), "")
        parsed = json.loads(marker) if marker else {}
        status = "passed" if probe.returncode == 0 and marker else "probe_failed"
        if status == "passed" and parsed.get("capability") == "minimum_variance":
            if abs(float(parsed.get("sum", 0.0)) - 1.0) > 1e-8 or float(parsed.get("max", 1.0)) > 0.350001:
                status = "constraint_failed"
        return {"entry_id":entry,"repository":row["repository"],"commit":row["head_commit"],"status":status,"started_at":started,"install_seconds":install_seconds,"probe_seconds":probe_seconds,"network_disabled_during_probe":True,"host_mounts":False,"result":parsed,"install_log":(install.stdout+'\n'+install.stderr)[-12000:],"probe_log":(probe.stdout+'\n'+probe.stderr)[-12000:]}
    finally:
        subprocess.run(["podman", "volume", "rm", "--force", volume], capture_output=True)


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--entry-id',action='append',default=[]); parser.add_argument('--timeout',type=int,default=900); args=parser.parse_args()
    wanted=set(args.entry_id) or set(PROBES)
    with QUEUE.open(newline='',encoding='utf-8') as handle:
        rows=[row for row in csv.DictReader(handle) if row['entry_id'] in wanted]
    OUTPUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for row in rows:
        result=run(row,args.timeout); results.append(result)
        path = OUTPUT / f"{row['entry_id']}.json"
        attempt = 2
        while path.exists():
            path = OUTPUT / f"{row['entry_id']}-attempt-{attempt}.json"
            attempt += 1
        path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(row['entry_id'],result['status'],flush=True)
    aggregate=[json.loads(path.read_text()) for path in sorted(OUTPUT.glob('ast-*.json'))]
    summary={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"total":len(aggregate),"passed":sum(row['status']=='passed' for row in aggregate),"failed":sum(row['status']!='passed' for row in aggregate),"network_disabled_during_probes":True,"host_mounts":False}
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0 if all(row['status']=='passed' for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
