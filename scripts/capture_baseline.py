"""One-shot: run current PyTorch scorers on the test fixtures and dump their
outputs to tests/baselines/*.json. Run BEFORE porting; the JSON becomes the
ground truth that the MLX port must match within tolerance.

Usage: uv run python scripts/capture_baseline.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import AI_SAMPLE, HUMAN_SAMPLE  # noqa: E402

import binoculars_scorer  # noqa: E402
import fast_detectgpt_scorer  # noqa: E402


def capture(label: str, text: str, scorer_module) -> dict:
    result = scorer_module.score(text)
    return {
        "label": label,
        "text_len": len(text),
        "result": {k: float(v) for k, v in result.items() if isinstance(v, (int, float))},
    }


def main() -> None:
    out_dir = ROOT / "tests" / "baselines"
    out_dir.mkdir(parents=True, exist_ok=True)

    bino = {
        "ai": capture("ai", AI_SAMPLE, binoculars_scorer),
        "human": capture("human", HUMAN_SAMPLE, binoculars_scorer),
    }
    (out_dir / "binoculars_pytorch.json").write_text(json.dumps(bino, indent=2))
    print("wrote", out_dir / "binoculars_pytorch.json")

    fdg = {
        "ai": capture("ai", AI_SAMPLE, fast_detectgpt_scorer),
        "human": capture("human", HUMAN_SAMPLE, fast_detectgpt_scorer),
    }
    (out_dir / "fast_detectgpt_pytorch.json").write_text(json.dumps(fdg, indent=2))
    print("wrote", out_dir / "fast_detectgpt_pytorch.json")


if __name__ == "__main__":
    main()
