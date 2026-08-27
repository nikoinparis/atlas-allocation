#!/usr/bin/env python3
"""Reproducible, fail-closed source and capability probes for third-party tools."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PROGRAM / "manifest.json"
DEFAULT_OUTPUT = ROOT / "evidence/third_party_tool_evaluation_v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
USER_AGENT = "portfolio-optimizer-2.0-third-party-evaluator/1.0"


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("program_id") != "third_party_tool_evaluation_v1":
        raise ValueError("unexpected program_id")
    tools = data.get("tools")
    if not isinstance(tools, list) or len(tools) != 7:
        raise ValueError("manifest must declare exactly seven discussed tools")
    ids = [tool.get("id") for tool in tools]
    if len(set(ids)) != len(ids):
        raise ValueError("tool ids must be unique")
    for tool in tools:
        if tool.get("kind") == "github":
            if not SHA40.fullmatch(str(tool.get("commit", ""))):
                raise ValueError(f"{tool.get('id')} must pin a 40-character commit")
            if not tool.get("license_expected") or not tool.get("required_paths"):
                raise ValueError(f"{tool.get('id')} is missing source-screening fields")
        if not tool.get("blockers") or not tool.get("verdict"):
            raise ValueError(f"{tool.get('id')} must have a fail-closed verdict and blockers")
    return data


def _request_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _request_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def detect_license(text: str) -> str:
    normalized = " ".join(text.lower().split())
    if "gnu affero general public license" in normalized:
        return "AGPL-3.0"
    if "gnu lesser general public license" in normalized:
        return "LGPL-3.0"
    if "bsd 3-clause license" in normalized or "neither the name of the copyright holder" in normalized:
        return "BSD-3-Clause"
    if "mit license" in normalized and "permission is hereby granted, free of charge" in normalized:
        return "MIT"
    return "UNKNOWN"


def _github_probe(tool: dict[str, Any], live: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repository": tool["repository"],
        "pinned_commit": tool["commit"],
        "pin_is_immutable_sha": bool(SHA40.fullmatch(tool["commit"])),
        "expected_license": tool["license_expected"],
        "required_paths": tool["required_paths"],
        "live_probe_attempted": live,
    }
    if not live:
        result["source_status"] = "not_checked_offline"
        return result
    repo = tool["repository"]
    try:
        metadata = _request_json(f"https://api.github.com/repos/{repo}")
        commit = _request_json(f"https://api.github.com/repos/{repo}/commits/{tool['commit']}")
        tree = _request_json(f"https://api.github.com/repos/{repo}/git/trees/{tool['commit']}?recursive=1")
        license_bytes = _request_bytes(f"https://raw.githubusercontent.com/{repo}/{tool['commit']}/LICENSE")
        detected_license = detect_license(license_bytes.decode("utf-8", errors="replace"))
        paths = {entry.get("path", "") for entry in tree.get("tree", [])}
        missing = [required for required in tool["required_paths"] if required not in paths and not any(path.startswith(required.rstrip("/") + "/") for path in paths)]
        result.update({
            "source_status": "reachable",
            "resolved_commit": commit.get("sha"),
            "commit_matches_pin": commit.get("sha") == tool["commit"],
            "archived": bool(metadata.get("archived")),
            "default_branch": metadata.get("default_branch"),
            "github_license_spdx": (metadata.get("license") or {}).get("spdx_id"),
            "license_detected_from_pinned_source": detected_license,
            "license_matches_expected": detected_license == tool["license_expected"],
            "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
            "required_paths_present": not missing,
            "missing_required_paths": missing,
            "tree_truncated": bool(tree.get("truncated")),
        })
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result.update({"source_status": "network_probe_failed", "error": f"{type(exc).__name__}: {exc}"})
    return result


def _website_probe(tool: dict[str, Any], live: bool) -> dict[str, Any]:
    result = {"url": tool["url"], "live_probe_attempted": live}
    if not live:
        result["source_status"] = "not_checked_offline"
        return result
    try:
        request = urllib.request.Request(tool["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            result.update({"source_status": "reachable", "http_status": response.status, "final_url": response.url})
    except (urllib.error.URLError, TimeoutError) as exc:
        result.update({"source_status": "network_probe_failed", "error": f"{type(exc).__name__}: {exc}"})
    return result


def _load_kronos_contract():
    path = PROGRAM / "adapters/kronos_feature_contract.py"
    spec = importlib.util.spec_from_file_location("kronos_feature_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Kronos feature contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kronos_clone_smoke(tool: dict[str, Any], *, live: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": live,
        "repository": tool["repository"],
        "pinned_commit": tool["commit"],
        "host_install_performed": False,
        "model_weights_downloaded": False,
    }
    contract = _load_kronos_contract()
    contract_result = contract.smoke_fixture()
    result["feature_contract_smoke"] = {
        "status": "passed",
        "contract_version": contract_result["contract_version"],
        "features": contract_result["features"],
        "usage_constraints": contract_result["usage_constraints"],
    }
    if not live:
        result["source_smoke"] = "not_checked_offline"
        return result
    with tempfile.TemporaryDirectory(prefix="po2-kronos-eval-") as directory:
        checkout = Path(directory) / "Kronos"
        clone = subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-tags", "--no-checkout", tool["url"] + ".git", str(checkout)],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if clone.returncode != 0:
            result.update({"source_smoke": "clone_failed", "clone_log": (clone.stdout + clone.stderr)[-4000:]})
            return result
        checkout_result = subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--detach", tool["commit"]],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if checkout_result.returncode != 0:
            result.update({"source_smoke": "pinned_checkout_failed", "checkout_log": (checkout_result.stdout + checkout_result.stderr)[-4000:]})
            return result
        resolved = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        source_files = sorted((checkout / "model").glob("*.py"))
        compile_errors = []
        for source_file in source_files:
            try:
                py_compile.compile(str(source_file), cfile=str(Path(directory) / (source_file.name + ".pyc")), doraise=True)
            except py_compile.PyCompileError as exc:
                compile_errors.append(str(exc))
        requirements = [line.strip() for line in (checkout / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        result.update({
            "source_smoke": "passed" if resolved == tool["commit"] and not compile_errors else "failed",
            "resolved_commit": resolved,
            "commit_matches_pin": resolved == tool["commit"],
            "model_python_files": [path.name for path in source_files],
            "static_compile_passed": not compile_errors,
            "compile_errors": compile_errors,
            "declared_requirements": requirements,
            "runtime_inference_status": "blocked_missing_isolated_runtime_and_weights",
            "external_artifacts": tool.get("external_artifacts", []),
            "license_detected_from_pinned_source": detect_license((checkout / "LICENSE").read_text(encoding="utf-8", errors="replace")),
            "license_sha256": hashlib.sha256((checkout / "LICENSE").read_bytes()).hexdigest(),
        })
    return result


def evaluate(manifest: dict[str, Any], *, live: bool) -> list[dict[str, Any]]:
    rows = []
    for tool in manifest["tools"]:
        if tool["kind"] == "github":
            probe = _github_probe(tool, live)
        elif tool["kind"] == "website":
            probe = _website_probe(tool, live)
        else:
            probe = {"source_status": "blocked_missing_exact_url", "live_probe_attempted": False}
        row = {
            "id": tool["id"],
            "name": tool["name"],
            "capability": tool["capability"],
            "verdict": tool["verdict"],
            "isolation": tool["isolation"],
            "blockers": tool["blockers"],
            "probe": probe,
            "approved_for_core_import": False,
            "approved_for_live_trading": False,
        }
        if tool["id"] == "kronos":
            row["kronos_smoke"] = kronos_clone_smoke(tool, live=live)
            if row["probe"].get("source_status") == "network_probe_failed" and row["kronos_smoke"].get("source_smoke") == "passed":
                row["probe"].update({
                    "source_status": "reachable_via_pinned_clone",
                    "resolved_commit": row["kronos_smoke"]["resolved_commit"],
                    "commit_matches_pin": row["kronos_smoke"]["commit_matches_pin"],
                    "license_detected_from_pinned_source": row["kronos_smoke"]["license_detected_from_pinned_source"],
                    "license_matches_expected": row["kronos_smoke"]["license_detected_from_pinned_source"] == tool["license_expected"],
                    "license_sha256": row["kronos_smoke"]["license_sha256"],
                })
        rows.append(row)
    return rows


def _write_report(output: Path, manifest_path: Path, manifest: dict[str, Any], rows: list[dict[str, Any]], live: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "raw").mkdir(exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    inference_path = output / "kronos_inference_smoke.json"
    if inference_path.is_file():
        inference = json.loads(inference_path.read_text(encoding="utf-8"))
        kronos_row = next(row for row in rows if row["id"] == "kronos")
        kronos_row["kronos_inference_smoke"] = inference
        if inference.get("status") == "passed":
            kronos_row["kronos_smoke"]["runtime_inference_status"] = "passed_isolated_cpu_regression"
            kronos_row["kronos_smoke"]["model_weights_downloaded"] = True
    manifest_bytes = manifest_path.read_bytes()
    report = {
        "program_id": manifest["program_id"],
        "generated_at_utc": generated,
        "live_network_probe": live,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "policy": manifest["policy"],
        "summary": {
            "tools_declared": len(rows),
            "core_imports_approved": sum(row["approved_for_core_import"] for row in rows),
            "live_trading_approved": sum(row["approved_for_live_trading"] for row in rows),
            "blocked_or_conditional": len(rows),
        },
        "results": rows,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for row in rows:
        (output / "raw" / f"{row['id']}.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    kronos = next(row for row in rows if row["id"] == "kronos")
    (output / "kronos_contract_smoke.json").write_text(json.dumps(kronos["kronos_smoke"]["feature_contract_smoke"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Third-party tool evaluation v1",
        "",
        f"Generated: `{generated}`",
        f"Manifest SHA-256: `{report['manifest_sha256']}`",
        "",
        "No tool is approved for direct core import or live trading. Verdicts describe the narrowest allowed next experiment.",
        "",
        "| Tool | Source probe | Verdict | Allowed boundary |",
        "|---|---|---|---|",
    ]
    for row in rows:
        source_status = row["probe"].get("source_status", "unknown")
        lines.append(f"| {row['name']} | {source_status} | `{row['verdict']}` | {row['isolation']} |")
    lines.extend(["", "## Blocking reasons", ""])
    for row in rows:
        lines.append(f"### {row['name']}")
        lines.append("")
        lines.extend(f"- {blocker}" for blocker in row["blockers"])
        lines.append("")
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--live", action="store_true", help="perform bounded source and website probes plus disposable Kronos clone")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    rows = evaluate(manifest, live=args.live)
    _write_report(args.output_dir, args.manifest, manifest, rows, args.live)
    print(json.dumps({"program_id": manifest["program_id"], "results": {row["id"]: row["verdict"] for row in rows}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
