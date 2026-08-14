#!/usr/bin/env python3
"""Test vectorbt numerical primitives and repeatability without incorporating it."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/vectorbt_equivalence_batch_13"
IMAGE = "docker.io/library/python:3.12-bookworm"
REPOSITORY = "polakowo/vectorbt"
COMMIT = "34b6d5935e3ea3eccd549e2592bc0f455b8045f5"

INSTALL = r'''
import pathlib, shutil, subprocess, sys, tarfile, urllib.request
work=pathlib.Path('/work'); archive=work/'source.tar.gz'; parent=work/'source'; repo=work/'repository'
request=urllib.request.Request('https://github.com/polakowo/vectorbt/archive/34b6d5935e3ea3eccd549e2592bc0f455b8045f5.tar.gz',headers={'User-Agent':'portfolio-optimizer-2.0-vectorbt'})
with urllib.request.urlopen(request,timeout=120) as response, archive.open('wb') as output: shutil.copyfileobj(response,output)
parent.mkdir()
with tarfile.open(archive,'r:gz') as bundle:
    for member in bundle.getmembers():
        path=pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts: raise RuntimeError('unsafe archive')
    bundle.extractall(parent,filter='data')
root=next(path for path in parent.iterdir() if path.is_dir()); shutil.move(str(root),repo)
subprocess.run([sys.executable,'-m','venv','/work/venv'],check=True)
subprocess.run(['/work/venv/bin/pip','install','--disable-pip-version-check','--no-cache-dir','-e','.'],cwd=repo,check=True)
'''

PROBE = r'''
import json, time, numpy as np, pandas as pd, vectorbt as vbt
close=pd.Series([100,101,99,102,104,103,106,108,107,110,109,112],dtype=float)
started=time.perf_counter(); fast=vbt.MA.run(close,3).ma; slow=vbt.MA.run(close,5).ma; indicator_seconds=time.perf_counter()-started
reference_fast=close.rolling(3).mean(); reference_slow=close.rolling(5).mean()
error=max(float((fast-reference_fast).abs().fillna(0).max()),float((slow-reference_slow).abs().fillna(0).max()))
regime=(fast>slow).fillna(False); entries=regime & ~regime.shift(1,fill_value=False); exits=~regime & regime.shift(1,fill_value=False)
started=time.perf_counter(); first=vbt.Portfolio.from_signals(close,entries,exits,fees=0.001,init_cash=10000.0); first_seconds=time.perf_counter()-started
second=vbt.Portfolio.from_signals(close,entries,exits,fees=0.001,init_cash=10000.0)
first_value=[float(v) for v in first.value().values]; second_value=[float(v) for v in second.value().values]
payload={'indicator_max_abs_error':error,'indicator_equivalence_pass':error<=1e-12,'determinism_pass':first_value==second_value,'orders':int(first.orders.count()),'final_value':first_value[-1],'total_fees':float(first.orders.records_readable['Fees'].sum()),'indicator_seconds':indicator_seconds,'first_backtest_seconds':first_seconds}
print('PROBE_JSON='+json.dumps(payload,sort_keys=True))
'''


def limits():
    return ["--read-only","--cap-drop=all","--security-opt=no-new-privileges","--pids-limit=256","--memory=2g","--cpus=1","--tmpfs","/tmp:rw,exec,nosuid,size=1g"]


def main() -> int:
    volume="po2-vectorbt-equivalence"
    subprocess.run(["podman","volume","create",volume],check=True,capture_output=True)
    started=datetime.now(timezone.utc).isoformat()
    try:
        install_start=time.monotonic()
        install=subprocess.run(["podman","run","--rm","--interactive","--name",volume+"-install",*limits(),"--volume",f"{volume}:/work:rw","--entrypoint","python",IMAGE,"-"],input=INSTALL,text=True,capture_output=True,timeout=900,check=False)
        install_seconds=int(time.monotonic()-install_start)
        probe=None
        if install.returncode==0:
            probe_start=time.monotonic()
            probe=subprocess.run(["podman","run","--rm","--interactive","--name",volume+"-test","--network=none",*limits(),"--volume",f"{volume}:/work:rw","--workdir","/work/repository","--entrypoint","/work/venv/bin/python",IMAGE,"-"],input=PROBE,text=True,capture_output=True,timeout=900,check=False)
            probe_seconds=int(time.monotonic()-probe_start)
        else:
            probe_seconds=0
        marker="" if probe is None else next((line[11:] for line in probe.stdout.splitlines() if line.startswith('PROBE_JSON=')),"")
        status="passed" if install.returncode==0 and probe and probe.returncode==0 and marker else ("install_failed" if install.returncode else "probe_failed")
        result={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"started_at_utc":started,"batch":13,"track":"vectorbt_equivalence","repository":REPOSITORY,"commit":COMMIT,"license":"LicenseRef-Commons-Clause","incorporated_into_core":False,"status":status,"install_seconds":install_seconds,"probe_seconds":probe_seconds,"network_disabled_during_probe":True,"host_mounts":False,"probe":json.loads(marker) if marker else {},"install_log":(install.stdout+'\n'+install.stderr)[-12000:],"probe_log":"" if probe is None else (probe.stdout+'\n'+probe.stderr)[-12000:],"decision":"research_speed_tool_only_not_alpha_and_not_core_dependency"}
        OUTPUT.mkdir(parents=True,exist_ok=True); (OUTPUT/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps({key:result[key] for key in ['status','install_seconds','probe_seconds','probe','decision']},indent=2,sort_keys=True))
        return 0 if status=='passed' else 1
    finally:
        subprocess.run(["podman","volume","rm","--force",volume],capture_output=True)


if __name__=='__main__':
    raise SystemExit(main())
