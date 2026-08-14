#!/usr/bin/env python3
"""Install and test selected Python candidates in disposable Podman volumes."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "evidence/batch_01_backtest_execution/smoke_test_queue.csv"
SOURCE_RUNS = ROOT / "evidence/batch_01_backtest_execution/source_smoke/runs"
OUTPUT = ROOT / "evidence/batch_01_backtest_execution/python_execution"
POLICY = ROOT / "config/sandbox_policy.json"

PREP_SCRIPT = r"""
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request

work = pathlib.Path('/work')
archive = work / 'source.tar.gz'
source_parent = work / 'source'
repository = work / 'repository'
build_tmp = work / 'tmp'
build_tmp.mkdir()
home = work / 'home'
home.mkdir()
os.environ['TMPDIR'] = str(build_tmp)
os.environ['HOME'] = str(home)
url = f"https://github.com/{os.environ['REPOSITORY']}/archive/{os.environ['HEAD_COMMIT']}.tar.gz"
request = urllib.request.Request(url, headers={'User-Agent': 'portfolio-optimizer-2.0-source-test'})
with urllib.request.urlopen(request, timeout=120) as response, archive.open('wb') as output:
    shutil.copyfileobj(response, output)
source_parent.mkdir()
with tarfile.open(archive, 'r:gz') as bundle:
    for member in bundle.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError(f'unsafe archive member: {member.name}')
    bundle.extractall(source_parent, filter='data')
roots = [path for path in source_parent.iterdir() if path.is_dir()]
if len(roots) != 1:
    raise RuntimeError(f'expected one archive root, found {len(roots)}')
shutil.move(str(roots[0]), repository)
subprocess.run([sys.executable, '-m', 'venv', '/work/venv'], check=True)
pip = '/work/venv/bin/pip'
python = '/work/venv/bin/python'
if os.environ.get('REPOSITORY') == 'microsoft/qlib':
    os.environ['SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYQLIB'] = '0.0.0'
subprocess.run(
    [pip, 'install', '--disable-pip-version-check', '--no-cache-dir', '-e', '.[dev,test,tests]'],
    cwd=repository,
    check=True,
)
test_packages = ['pytest', 'setuptools']
if os.environ.get('EXTRA_TEST_PACKAGE'):
    test_packages.append(os.environ['EXTRA_TEST_PACKAGE'])
subprocess.run([pip, 'install', '--disable-pip-version-check', '--no-cache-dir', *test_packages], check=True)
with (work / 'pip-freeze.txt').open('w') as output:
    subprocess.run([pip, 'freeze', '--all'], stdout=output, text=True, check=True)
subprocess.run([python, '-c', 'import sys; print(sys.version)'], check=True)
print('PREPARATION_COMPLETE')
"""


@dataclass
class ExecutionResult:
    entry_id: str
    name: str
    repository: str
    head_commit: str
    image: str
    status: str
    install_exit_code: int
    test_exit_code: int
    install_seconds: int
    test_seconds: int
    test_network: str
    host_mounts: bool
    started_at: str
    install_log: str
    test_log: str


def load_candidates(
    entry_ids: set[str], *, queue: Path = QUEUE, source_runs: Path = SOURCE_RUNS
) -> list[dict[str, str]]:
    with queue.open(newline='', encoding='utf-8') as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row['queue_status'] == 'ready'
            and row['planned_environment'] == 'python_container'
            and (not entry_ids or row['entry_id'] in entry_ids)
        ]
    eligible = []
    for row in rows:
        source_path = source_runs / f"{row['entry_id']}.json"
        if not source_path.exists():
            continue
        source = json.loads(source_path.read_text(encoding='utf-8'))
        names = {Path(item).name for item in source['dependency_manifests']}
        if names & {'pyproject.toml', 'setup.py', 'setup.cfg'}:
            eligible.append(row)
    return eligible


def base_limits(policy: dict[str, object]) -> list[str]:
    limits = policy['limits']
    assert isinstance(limits, dict)
    return [
        '--read-only', '--cap-drop=all', '--security-opt=no-new-privileges',
        f"--pids-limit={limits['pids']}", '--memory=2g', f"--cpus={limits['cpus']}",
        '--tmpfs', '/tmp:rw,exec,nosuid,size=2g',
    ]


def candidate_image(row: dict[str, str], policy: dict[str, object]) -> str:
    if row['entry_id'] == 'ast-0039':
        return str(policy['python_legacy_test_image'])
    return str(policy['python_test_image'])


def install_command(row: dict[str, str], policy: dict[str, object], volume: str) -> list[str]:
    safe_id = re.sub(r'[^a-z0-9_.-]', '-', row['entry_id'].lower())
    command = [
        'podman', 'run', '--rm', '--interactive', '--name', f'po2-python-install-{safe_id}',
        *base_limits(policy), '--volume', f'{volume}:/work:rw',
        '--env', f"REPOSITORY={row['repository']}", '--env', f"HEAD_COMMIT={row['head_commit']}",
        '--env', 'HOME=/work/home',
        '--entrypoint', 'python', candidate_image(row, policy), '-',
    ]
    if row['entry_id'] == 'ast-0043':
        command[command.index('--entrypoint'):command.index('--entrypoint')] = [
            '--env', 'EXTRA_TEST_PACKAGE=setuptools<81',
        ]
    return command


def test_command(row: dict[str, str], policy: dict[str, object], volume: str) -> list[str]:
    safe_id = re.sub(r'[^a-z0-9_.-]', '-', row['entry_id'].lower())
    return [
        'podman', 'run', '--rm', '--name', f'po2-python-test-{safe_id}',
        '--network=none', *base_limits(policy), '--volume', f'{volume}:/work:rw',
        '--env', 'HOME=/work/home',
        '--workdir', '/work/repository', '--entrypoint', '/work/venv/bin/python',
        candidate_image(row, policy), '-m', 'pytest', '-q', '--disable-warnings', '--maxfail=1',
    ]


def compact_log(completed: subprocess.CompletedProcess[str], limit: int = 12000) -> str:
    combined = (completed.stdout + '\n' + completed.stderr).strip()
    return combined[-limit:]


def run_candidate(row: dict[str, str], policy: dict[str, object], timeout: int) -> ExecutionResult:
    safe_id = re.sub(r'[^a-z0-9_.-]', '-', row['entry_id'].lower())
    volume = f'po2-python-{safe_id}'
    subprocess.run(['podman', 'volume', 'create', volume], check=True, capture_output=True, text=True)
    install_started = time.monotonic()
    test_seconds = 0
    test_exit = -1
    test_log = ''
    try:
        try:
            install = subprocess.run(
                install_command(row, policy, volume), input=PREP_SCRIPT, text=True,
                capture_output=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(['podman', 'rm', '--force', f'po2-python-install-{safe_id}'], capture_output=True)
            return ExecutionResult(
                row['entry_id'], row['name'], row['repository'], row['head_commit'],
                candidate_image(row, policy), 'install_timed_out', 124, -1,
                int(time.monotonic() - install_started), 0, 'not_run', False,
                datetime.now(timezone.utc).isoformat(), str(exc), '',
            )
        install_seconds = int(time.monotonic() - install_started)
        if install.returncode == 0:
            test_started = time.monotonic()
            try:
                test = subprocess.run(
                    test_command(row, policy, volume), text=True, capture_output=True,
                    timeout=timeout, check=False,
                )
                test_seconds = int(time.monotonic() - test_started)
                test_exit = test.returncode
                test_log = compact_log(test)
                status = 'passed' if test.returncode == 0 else 'tests_failed'
            except subprocess.TimeoutExpired as exc:
                subprocess.run(['podman', 'rm', '--force', f'po2-python-test-{safe_id}'], capture_output=True)
                test_seconds = int(time.monotonic() - test_started)
                test_exit = 124
                test_log = str(exc)
                status = 'tests_timed_out'
        else:
            status = 'install_failed'
        return ExecutionResult(
            row['entry_id'], row['name'], row['repository'], row['head_commit'],
            candidate_image(row, policy), status, install.returncode, test_exit,
            install_seconds, test_seconds, 'disabled_during_tests', False,
            datetime.now(timezone.utc).isoformat(), compact_log(install), test_log,
        )
    finally:
        subprocess.run(['podman', 'volume', 'rm', '--force', volume], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--entry-id', action='append', default=[])
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--queue', type=Path, default=QUEUE)
    parser.add_argument('--source-runs', type=Path, default=SOURCE_RUNS)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    rows = load_candidates(
        set(args.entry_id), queue=args.queue, source_runs=args.source_runs
    )
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        raise SystemExit('No eligible Python candidates selected')
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for row in rows:
        result = run_candidate(row, policy, args.timeout)
        results.append(result)
        result_path = output / f"{result.entry_id}.json"
        attempt = 2
        while result_path.exists():
            result_path = output / f"{result.entry_id}-attempt-{attempt}.json"
            attempt += 1
        result_path.write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True) + '\n', encoding='utf-8'
        )
        print(f'{result.entry_id} {result.status} install={result.install_seconds}s test={result.test_seconds}s', flush=True)
    aggregate = [
        json.loads(path.read_text(encoding='utf-8'))
        for path in sorted(output.glob('ast-*.json'))
    ]
    summary = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total': len(aggregate),
        'passed': sum(item['status'] == 'passed' for item in aggregate),
        'install_failed': sum(item['status'].startswith('install_') for item in aggregate),
        'tests_failed': sum(item['status'].startswith('tests_') for item in aggregate),
        'network_disabled_during_tests': True,
        'host_mounts': False,
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0 if all(item.status == 'passed' for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
