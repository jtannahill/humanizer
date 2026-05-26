"""Run each new Qwen3-1.7B backend in its own subprocess (to isolate RAM)
and dump raw scorer outputs for the conftest AI_SAMPLE and HUMAN_SAMPLE.

Used during model-bump recalibration. Prints JSON the operator can read off
to set AI_THRESHOLD / HUMAN_THRESHOLD in each scorer file.

Usage: uv run python scripts/calibrate.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


PROBE = r"""
import json, sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
from conftest import AI_SAMPLE, HUMAN_SAMPLE
import {module} as m
ai = m.score(AI_SAMPLE)
hu = m.score(HUMAN_SAMPLE)
print("===RESULT===")
print(json.dumps({{"ai": ai, "human": hu}}))
"""


def probe(module: str) -> dict:
    code = PROBE.format(root=str(ROOT), tests=str(ROOT / "tests"), module=module)
    result = subprocess.run(
        [PY, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        print(f"--- {module} STDERR ---", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{module} subprocess failed (exit {result.returncode})")
    out = result.stdout
    marker = "===RESULT==="
    if marker not in out:
        print(f"--- {module} STDOUT ---", file=sys.stderr)
        print(out, file=sys.stderr)
        raise SystemExit(f"{module} did not emit a result line")
    payload = out.split(marker, 1)[1].strip().splitlines()[0]
    return json.loads(payload)


def main() -> None:
    print(">> probing binoculars_scorer (PyTorch+MPS, downloads Qwen3-1.7B-Base + Qwen3-1.7B if missing)", flush=True)
    bino = probe("binoculars_scorer")
    print(json.dumps(bino, indent=2), flush=True)

    print(">> probing fast_detectgpt_scorer (MLX, downloads mlx-community/Qwen3-1.7B-bf16 if missing)", flush=True)
    fdg = probe("fast_detectgpt_scorer")
    print(json.dumps(fdg, indent=2), flush=True)

    out_path = ROOT / "tests" / "baselines" / "qwen3_raw_calibration.json"
    out_path.write_text(json.dumps({"binoculars": bino, "fast_detectgpt": fdg}, indent=2))
    print(f">> wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
