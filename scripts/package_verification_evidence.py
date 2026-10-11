"""Package local verification evidence for independent inspection.

Creates ``artifacts/verification/<utc-stamp>/`` containing machine-generated:

  git-state.txt            git HEAD / branch / status / remote / config
  commit-ancestry.txt      full log with parents and parentage
  working-tree.diff        complete `git diff` of the working tree
  pytest-collection.txt    raw `pytest --collect-only -q` output
  pytest-results.txt       raw `pytest -q -ra` output + exit code
  dependency-versions.txt  python + key package versions
  artifact-hashes.txt      SHA-256 of key evidence artifacts
  reproduction.txt         exact commands to reproduce every result
  changed-files.txt        `git status --porcelain` + `git diff --stat`

and a ZIP of the directory next to it. The script never modifies repository
sources, datasets or committed history; it only writes under artifacts/ (which
is git-ignored) and reads everything else.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ART = REPO / "artifacts" / "verification"


def run(cmd: list[str], cwd: Path = REPO) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ART / stamp
    out.mkdir(parents=True, exist_ok=True)
    print(f"evidence dir: {out}")

    # git state and ancestry
    for name, cmd in (
        ("git-state.txt", ["git", "status", "--porcelain=v1", "--branch"]),
        ("git-head.txt", ["git", "rev-parse", "HEAD"]),
        ("commit-ancestry.txt", ["git", "log", "--all",
                                 "--format=%H|%P|%an <%ae>|%cn <%ce>|%s", "-12"]),
        ("working-tree.diff", ["git", "diff"]),
        ("staged.diff", ["git", "diff", "--cached"]),
        ("changed-files.txt", ["git", "status", "--porcelain"]),
        ("remote.txt", ["git", "remote", "-v"]),
        ("identity.txt", ["git", "config", "--local", "--list"]),
    ):
        rc, text = run(cmd)
        (out / name).write_text(text, encoding="utf-8")
        print(f"  {name}: rc={rc} ({len(text)} bytes)")

    # dependency versions
    try:
        import numpy, pandas, sklearn, scipy  # noqa
        deps = {
            "python": sys.version,
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "scikit-learn": sklearn.__version__,
            "scipy": scipy.__version__,
        }
    except Exception as e:  # pragma: no cover
        deps = {"python": sys.version, "error": repr(e)}
    (out / "dependency-versions.txt").write_text(json.dumps(deps, indent=2), encoding="utf-8")

    # test logs (heavy; opt-in via --with-tests)
    if "--with-tests" in sys.argv:
        rc, text = run([sys.executable, "-m", "pytest", "--collect-only", "-q"])
        (out / "pytest-collection.txt").write_text(text + f"\nEXIT CODE: {rc}\n", encoding="utf-8")
        print(f"  pytest-collection.txt: rc={rc}")
        rc, text = run([sys.executable, "-m", "pytest", "tests/", "-q", "-ra"])
        (out / "pytest-results.txt").write_text(text + f"\nEXIT CODE: {rc}\n", encoding="utf-8")
        print(f"  pytest-results.txt: rc={rc}")

    # artifact hashes
    hashed = []
    for rel in (
        "artifacts/reliability/evaluation/reliability_report_v2.json",
        "artifacts/reliability/evaluation/reliability_report.json",
        "artifacts/reliability/evaluation/alert_event_ledger.json",
        "artifacts/reliability/evaluation/scenario_ledger.json",
        "artifacts/reliability/evaluation/normal_scenario_audit.json",
        "artifacts/reliability/evaluation/conventional_comparison.json",
        "docs/reliability-research-report.md",
        "docs/reliability-evaluation-protocol.md",
        "decisions.md", "flow.md", "handoff.md",
    ):
        p = REPO / rel
        if p.exists():
            hashed.append({"path": rel, "sha256": sha256(p), "bytes": p.stat().st_size})
        else:
            hashed.append({"path": rel, "MISSING": True})
    (out / "artifact-hashes.txt").write_text(json.dumps(hashed, indent=2), encoding="utf-8")
    print(f"  artifact-hashes.txt: {sum(1 for h in hashed if 'sha256' in h)} present, "
          f"{sum(1 for h in hashed if h.get('MISSING'))} missing")

    (out / "reproduction.txt").write_text(
        "\n".join([
            "# Reproduction commands (run from the repository root)",
            "python -m pytest tests/ -q",
            "python scripts/evaluate_reliability.py          # writes reliability_report_v2.json + ledgers",
            "python scripts/evaluate_conventional_detector.py # writes conventional_comparison.json",
            "python scripts/audit_normal_scenarios.py         # writes normal_scenario_audit.json",
            "",
            "# The v1 artifact (reliability_report.json) is preserved and is NOT overwritten.",
        ]), encoding="utf-8")

    # zip
    zip_path = out.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, arcname=f.name)
    print(f"bundle: {zip_path}")
    print(f"sha256: {sha256(zip_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())