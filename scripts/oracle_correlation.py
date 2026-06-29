"""Which local backend best predicts GPTZero? — oracle correlation harness.

The local oracle's only job inside the rewrite loop is to anticipate GPTZero.
So the backend to default to is the one whose human_score ranks texts the same
way GPTZero does. This scores a spectrum corpus (corporate-AI -> casual) with
every local backend plus GPTZero and reports the Spearman rank correlation
between each backend's human_score and GPTZero's human probability.

Each backend runs in its own subprocess (RAM isolation, as in calibrate.py /
compare_backends.py). GPTZero (1 call per text) runs in this process and needs
GPTZERO_KEY in the environment.

Usage:
  GPTZERO_KEY=... uv run python scripts/oracle_correlation.py
  uv run python scripts/oracle_correlation.py --no-gptzero   # local scores only
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spectrum_corpus import CORPUS  # noqa: E402

BACKENDS = ["gpt2", "binoculars", "fast_detectgpt", "roberta"]


# --- Spearman rank correlation (pure; unit-tested) ---

def _ranks(xs):
    """Average ranks (1-based), ties share the mean of their positions."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return 0.0
    return cov / ((va * vb) ** 0.5)


def spearman(xs, ys):
    """Spearman rank correlation. 0.0 if undefined (len<2 or constant input)."""
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    return _pearson(_ranks(xs), _ranks(ys))


# --- scoring ---

PROBE = r"""
import json, sys
sys.path.insert(0, {root!r})
from scorer import score
texts = json.loads(sys.stdin.read())
print("===RESULT===")
print(json.dumps([score(t, backend={backend!r})["human_score"] for t in texts]))
"""


def score_backend(backend, texts):
    code = PROBE.format(root=str(ROOT), backend=backend)
    res = subprocess.run([PY, "-c", code], input=json.dumps(texts),
                         capture_output=True, text=True, cwd=ROOT)
    if res.returncode != 0 or "===RESULT===" not in res.stdout:
        print(f"--- {backend} STDERR ---\n{res.stderr}", file=sys.stderr)
        raise SystemExit(f"{backend} subprocess failed")
    return json.loads(res.stdout.split("===RESULT===", 1)[1].strip().splitlines()[0])


def score_gptzero(texts):
    """GPTZero human probability (1 - P(AI)) per text."""
    import requests
    key = os.environ.get("GPTZERO_KEY")
    if not key:
        raise SystemExit("GPTZERO_KEY not set (use --no-gptzero for local-only)")
    out = []
    for i, t in enumerate(texts):
        resp = requests.post(
            "https://api.gptzero.me/v2/predict/text",
            json={"document": t},
            headers={"x-api-key": key, "Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        out.append(1.0 - resp.json()["documents"][0]["completely_generated_prob"])
        print(f"  gptzero {i + 1}/{len(texts)}", end="\r", flush=True)
    print()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gptzero", action="store_true")
    args = ap.parse_args()

    texts = [r["text"] for r in CORPUS]
    print(f">> {len(texts)} spectrum docs\n", flush=True)

    local = {}
    for b in BACKENDS:
        print(f">> scoring {b} ...", flush=True)
        local[b] = score_backend(b, texts)

    if args.no_gptzero:
        print("\n=== local backends only (no GPTZero target) ===")
        print("inter-backend Spearman vs gpt2 (default):")
        for b in BACKENDS:
            print(f"  {b:<16}{spearman(local['gpt2'], local[b]):+.3f}")
        return

    print(">> scoring gptzero ...", flush=True)
    gz = score_gptzero(texts)

    rows = sorted(
        ((b, spearman(local[b], gz)) for b in BACKENDS),
        key=lambda r: -r[1],
    )
    print("\n=== Spearman correlation with GPTZero (higher = better loop oracle) ===")
    print(f"{'backend':<16}{'rho':>8}")
    for b, rho in rows:
        print(f"{b:<16}{rho:>+8.3f}")
    best = rows[0]
    print(f"\n>> best predictor of GPTZero: {best[0]} (rho={best[1]:+.3f})")
    spread = best[1] - rows[-1][1]
    if spread < 0.1:
        print(f">> spread is small ({spread:.3f}) — backend choice is ~cosmetic for the loop.")


if __name__ == "__main__":
    main()
