"""Compare every local detector backend against GPTZero on a labeled corpus.

Answers two questions:
  1. How accurate is each local backend on its own? (vs gold labels)
  2. Where does each backend AGREE / DISAGREE with GPTZero? (the production
     primary the loop trusts at 70%)

Each backend runs in its own subprocess so their weights never coexist in
unified memory (gpt2 + binoculars + fast_detectgpt + roberta together would
swap a 16GB Mac — same reason scripts/calibrate.py isolates). GPTZero is a
network call and runs in this process.

Corpus format: JSONL, one object per line: {"text": "...", "label": "ai"|"human"}
With no --corpus, falls back to the two conftest fixtures — enough to smoke-test
the wiring, NOT enough to trust the accuracy numbers.

Usage:
  uv run python scripts/compare_backends.py --corpus mydata.jsonl
  uv run python scripts/compare_backends.py --no-gptzero        # local only, offline
  GPTZERO_KEY=... uv run python scripts/compare_backends.py     # include GPTZero
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

BACKENDS = ["gpt2", "binoculars", "fast_detectgpt", "roberta"]

# Backend-native key carrying the raw signal, for display alongside human_score.
RAW_KEY = {
    "gpt2": "perplexity",
    "binoculars": "binoculars",
    "fast_detectgpt": "fast_detectgpt",
    "roberta": "roberta",
}


# --- pure decision logic (a high human_score means "human") ---

def call_of(human_score: float) -> str:
    """Binary AI/human call from a 0-1 human_score."""
    return "human" if human_score >= 0.5 else "ai"


def accuracy(calls, golds) -> float:
    if not golds:
        return 0.0
    hits = sum(1 for c, g in zip(calls, golds) if c == g)
    return hits / len(golds)


def agreement(calls_a, calls_b) -> float:
    """Fraction of docs where two backends make the same AI/human call."""
    if not calls_a:
        return 0.0
    same = sum(1 for a, b in zip(calls_a, calls_b) if a == b)
    return same / len(calls_a)


# --- backend scoring (subprocess-isolated) ---

PROBE = r"""
import json, sys
sys.path.insert(0, {root!r})
from scorer import score
texts = json.loads(sys.stdin.read())
out = [score(t, backend={backend!r}) for t in texts]
print("===RESULT===")
print(json.dumps(out))
"""


def score_backend(backend: str, texts) -> list:
    """Run one backend over all texts in a fresh subprocess. Returns the list
    of result dicts (one per text)."""
    code = PROBE.format(root=str(ROOT), backend=backend)
    result = subprocess.run(
        [PY, "-c", code],
        input=json.dumps(texts),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0 or "===RESULT===" not in result.stdout:
        print(f"--- {backend} STDERR ---", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{backend} subprocess failed")
    payload = result.stdout.split("===RESULT===", 1)[1].strip().splitlines()[0]
    return json.loads(payload)


def score_gptzero(texts) -> list:
    """Return P(AI) per text from GPTZero, or None if unavailable."""
    import requests

    key = os.environ.get("GPTZERO_KEY")
    if not key:
        return None
    out = []
    for t in texts:
        resp = requests.post(
            "https://api.gptzero.me/v2/predict/text",
            json={"document": t},
            headers={"x-api-key": key, "Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        out.append(resp.json()["documents"][0]["completely_generated_prob"])
    return out


# --- corpus ---

def load_corpus(path: str):
    if path:
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        return [r["text"] for r in rows], [r["label"] for r in rows]
    sys.path.insert(0, str(ROOT / "tests"))
    from conftest import AI_SAMPLE, HUMAN_SAMPLE  # noqa: E402
    print("!! no --corpus given: using 2 conftest fixtures (smoke test only)\n", file=sys.stderr)
    return [AI_SAMPLE, HUMAN_SAMPLE], ["ai", "human"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="", help="JSONL of {text,label}")
    ap.add_argument("--no-gptzero", action="store_true", help="skip GPTZero, local only")
    args = ap.parse_args()

    texts, golds = load_corpus(args.corpus)
    n = len(texts)
    print(f">> {n} docs ({golds.count('ai')} ai / {golds.count('human')} human)\n", flush=True)

    # GPTZero first (cheap to fail fast on a bad key / offline).
    gpt_ai = None if args.no_gptzero else score_gptzero(texts)
    gpt_calls = [call_of(1 - p) for p in gpt_ai] if gpt_ai is not None else None

    # Each local backend, isolated.
    backend_calls = {}
    rows = []
    for b in BACKENDS:
        print(f">> scoring {b} ...", flush=True)
        results = score_backend(b, texts)
        calls = [call_of(r["human_score"]) for r in results]
        backend_calls[b] = calls
        row = {
            "backend": b,
            "accuracy": accuracy(calls, golds),
            "agree_gptzero": agreement(calls, gpt_calls) if gpt_calls else None,
        }
        rows.append(row)

    # --- report ---
    print("\n=== per-backend ===")
    print(f"{'backend':<16}{'accuracy':>10}{'agree w/ GPTZero':>20}")
    for r in rows:
        ag = f"{r['agree_gptzero']*100:.0f}%" if r["agree_gptzero"] is not None else "-"
        print(f"{r['backend']:<16}{r['accuracy']*100:>9.0f}%{ag:>20}")
    if gpt_calls:
        print(f"{'gptzero':<16}{accuracy(gpt_calls, golds)*100:>9.0f}%{'(primary)':>20}")

    if gpt_calls:
        print("\n=== disagreements with GPTZero (doc#: gold | gptzero vs backend) ===")
        for b in BACKENDS:
            diffs = [
                (i, golds[i], gpt_calls[i], backend_calls[b][i])
                for i in range(n)
                if backend_calls[b][i] != gpt_calls[i]
            ]
            if not diffs:
                print(f"{b}: none")
                continue
            print(f"{b}:")
            for i, gold, gz, bk in diffs:
                print(f"  #{i} gold={gold:<6} gptzero={gz:<6} {b}={bk}")


if __name__ == "__main__":
    main()
