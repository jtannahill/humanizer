"""Parity test: current binoculars_scorer.score() must match the captured
PyTorch baseline within tolerance.

Tolerances (from spec):
  binoculars score: ±0.01
  human_score:      ±0.02
  burstiness:       exact (no model involvement)
"""

import json
from pathlib import Path

import pytest

import binoculars_scorer

BASELINE = json.loads(
    (Path(__file__).parent / "baselines" / "binoculars_pytorch.json").read_text()
)

BINO_TOL = 0.01
HUMAN_TOL = 0.02


@pytest.mark.parametrize("label", ["ai", "human"])
def test_binoculars_parity(label, ai_text, human_text):
    text = ai_text if label == "ai" else human_text
    expected = BASELINE[label]["result"]

    actual = binoculars_scorer.score(text)

    assert abs(actual["binoculars"] - expected["binoculars"]) <= BINO_TOL, (
        f"binoculars drift on {label}: "
        f"actual={actual['binoculars']:.4f} expected={expected['binoculars']:.4f}"
    )
    assert abs(actual["human_score"] - expected["human_score"]) <= HUMAN_TOL, (
        f"human_score drift on {label}: "
        f"actual={actual['human_score']:.4f} expected={expected['human_score']:.4f}"
    )
    assert actual["burstiness"] == pytest.approx(expected["burstiness"], abs=1e-6)
