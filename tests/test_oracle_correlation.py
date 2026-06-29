"""Unit tests for the Spearman helper in scripts/oracle_correlation.py.

The harness itself (subprocess scoring + GPTZero network) is operator tooling
verified by running it, but the rank-correlation math is exactly the kind of
thing that silently flips sign or mishandles ties, so it gets real tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from oracle_correlation import spearman


def test_perfect_positive():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0


def test_perfect_negative():
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0


def test_one_adjacent_swap():
    # Swapping the top two of four items: d^2 sum = 2, rho = 1 - 6*2/(4*15) = 0.8
    assert abs(spearman([1, 2, 3, 4], [1, 2, 4, 3]) - 0.8) < 1e-9


def test_zero_variance_returns_zero():
    # One variable constant -> correlation undefined; defined here as 0.0
    assert spearman([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0


def test_handles_ties_with_average_ranks():
    # Monotonic but with a tie in xs; still strongly positive, within [−1, 1].
    rho = spearman([1, 1, 2, 3], [10, 11, 20, 30])
    assert 0.9 <= rho <= 1.0
