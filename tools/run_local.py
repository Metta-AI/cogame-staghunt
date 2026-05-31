"""Local end-to-end harness for the stag_hunt grader + reporter.

Wraps a game-written ``scores.json`` (the results artifact) in a minimal Coworld
episode bundle zip, then runs the grader and reporter against it over ``file://``
URIs — the same contract the platform uses. Outputs land next to the input.

Usage:
    python tools/run_local.py <scores.json> <out_dir>

Set STAGHUNT_REPORTER_NO_LLM=1 to force the reporter's deterministic narrative
(no Bedrock call); leave it unset to attempt Bedrock if AWS creds are present.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from staghunt_tools.grader import run as run_grader  # noqa: E402
from staghunt_tools.reporter import run as run_reporter  # noqa: E402


def build_bundle(results_path: Path, bundle_path: Path, ereq_id: str = "ereq_local") -> None:
    results_bytes = results_path.read_bytes()
    inner = {
        "ereq_id": ereq_id,
        "status": "success",
        "include": ["results"],
        "files": {"results": "results.json"},
    }
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(inner, indent=2))
        zf.writestr("results.json", results_bytes)


def main() -> None:
    results_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = out_dir / "bundle.zip"
    build_bundle(results_path, bundle_path)
    bundle_uri = bundle_path.resolve().as_uri()

    grade_uri = (out_dir / "grade.json").resolve().as_uri()
    report_uri = (out_dir / "report.zip").resolve().as_uri()

    print("== grader ==")
    grade = run_grader(bundle_uri, grade_uri)
    print(json.dumps({"score": grade.score, "components": grade.components}, indent=2))

    print("\n== reporter ==")
    source = run_reporter(bundle_uri, report_uri)
    print(f"narration source: {source}")

    # Echo the rendered report for convenience.
    with zipfile.ZipFile(out_dir / "report.zip") as zf:
        print("\n== report.md ==\n")
        print(zf.read("report.md").decode("utf-8"))


if __name__ == "__main__":
    main()
