"""Parity test: current fast_detectgpt_scorer.score() must match the captured
PyTorch baseline within tolerance.

Tolerances (from spec):
  fast_detectgpt discrepancy: ±0.05
  human_score:                ±0.02
  burstiness:                 exact
"""

import json
from pathlib import Path

import pytest

import fast_detectgpt_scorer

BASELINE = json.loads(
    (Path(__file__).parent / "baselines" / "fast_detectgpt_pytorch.json").read_text()
)

FDG_TOL = 0.05
HUMAN_TOL = 0.02


@pytest.mark.parametrize("label", ["ai", "human"])
def test_fast_detectgpt_parity(label, ai_text, human_text):
    text = ai_text if label == "ai" else human_text
    expected = BASELINE[label]["result"]

    actual = fast_detectgpt_scorer.score(text)

    assert abs(actual["fast_detectgpt"] - expected["fast_detectgpt"]) <= FDG_TOL, (
        f"fast_detectgpt drift on {label}: "
        f"actual={actual['fast_detectgpt']:.4f} expected={expected['fast_detectgpt']:.4f}"
    )
    assert abs(actual["human_score"] - expected["human_score"]) <= HUMAN_TOL, (
        f"human_score drift on {label}: "
        f"actual={actual['human_score']:.4f} expected={expected['human_score']:.4f}"
    )
    assert actual["burstiness"] == pytest.approx(expected["burstiness"], abs=1e-6)
