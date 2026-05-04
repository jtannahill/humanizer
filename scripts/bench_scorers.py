"""Benchmark warm-call latency for the MLX scorers. Prints one line per
backend with first-call (cold) and median-of-5 (warm) timings in ms.

Usage: uv run python scripts/bench_scorers.py
"""

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import AI_SAMPLE  # noqa: E402

import binoculars_scorer  # noqa: E402
import fast_detectgpt_scorer  # noqa: E402


def time_call(fn, text, n_warm=5):
    t0 = time.perf_counter()
    fn(text)
    cold_ms = (time.perf_counter() - t0) * 1000

    warms = []
    for _ in range(n_warm):
        t0 = time.perf_counter()
        fn(text)
        warms.append((time.perf_counter() - t0) * 1000)

    return cold_ms, statistics.median(warms)


def main():
    print("backend             cold_ms     warm_ms")
    print("-" * 45)

    cold, warm = time_call(binoculars_scorer.binoculars_score, AI_SAMPLE)
    print(f"binoculars          {cold:8.0f}    {warm:8.0f}")

    cold, warm = time_call(fast_detectgpt_scorer.fast_detectgpt_score, AI_SAMPLE)
    print(f"fast_detectgpt      {cold:8.0f}    {warm:8.0f}")


if __name__ == "__main__":
    main()
