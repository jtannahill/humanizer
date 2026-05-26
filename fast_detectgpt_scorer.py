"""fast_detectgpt_scorer.py — Fast-DetectGPT (Bao et al., 2024).

White-box, single-model variant: replaces DetectGPT's perturbation step with
conditional sampling, using closed-form expectation and variance over each
position's predictive distribution.

For each token position t:
  mu(x)     = sum_t log p(x_t | x_<t)            actual log-likelihood
  mu_tilde  = sum_t E_{x̃ ~ p}[log p(x̃ | x_<t)]   = -sum_t H(p_t)
  sigma^2   = sum_t Var_{x̃ ~ p}[log p(x̃ | x_<t)]
  d(x)      = (mu - mu_tilde) / sigma

Higher d(x) = more AI-like. Human text scores near 0; AI text scores positive.
This is the opposite convention from Binoculars/GPT-2 perplexity, so the
human_score mapping inverts the discrepancy.

Backend: MLX on Apple Silicon.
Default model: mlx-community/Qwen3-1.7B-bf16 (~3.4GB).
"""

import re
from typing import List, Tuple

DEFAULT_MODEL = "mlx-community/Qwen3-1.7B-bf16"

# Thresholds calibrated on the conftest AI_SAMPLE / HUMAN_SAMPLE pair using
# Qwen3-1.7B (MLX bf16) on 2026-05-26. Higher discrepancy = more AI-like.
# Inverted in _human_score below. Gap on these samples is ~0.5, much wider
# than the ~0.04 gap the Qwen2.5-1.5B port produced — Qwen3-1.7B is the
# stronger detector for this backend. Recalibrate on a richer corpus before
# trusting numeric human_score.
AI_THRESHOLD = -6.08    # discrepancy >= this looks AI
HUMAN_THRESHOLD = -6.60 # discrepancy <= this looks human

MAX_TOKENS = 2048

_model = None
_tokenizer = None


def _ensure_loaded():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    from mlx_lm import load

    _model, _tokenizer = load(DEFAULT_MODEL)
    return _model, _tokenizer


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def _encode(tokenizer, text: str):
    """Encode `text` to a 1xL mx.array of token ids, truncated to MAX_TOKENS."""
    import mlx.core as mx

    ids = tokenizer.encode(text)
    if len(ids) > MAX_TOKENS:
        ids = ids[:MAX_TOKENS]
    return mx.array([ids])


def fast_detectgpt_score(text: str) -> float:
    """Compute the Fast-DetectGPT discrepancy. Higher = more AI-like."""
    if not text.strip():
        return 0.0

    import mlx.core as mx

    model, tok = _ensure_loaded()
    input_ids = _encode(tok, text)
    if input_ids.shape[1] < 2:
        return 0.0

    logits = model(input_ids)

    logits_shift = logits[..., :-1, :].astype(mx.float32)
    labels = input_ids[..., 1:]

    log_probs = logits_shift - mx.logsumexp(logits_shift, axis=-1, keepdims=True)
    probs = mx.exp(log_probs)

    actual = mx.take_along_axis(log_probs, labels[..., None], axis=-1).squeeze(-1)

    expected = (probs * log_probs).sum(axis=-1)
    expected_sq = (probs * (log_probs ** 2)).sum(axis=-1)
    variance = mx.maximum(expected_sq - expected ** 2, 0)

    mu = float(actual.sum(axis=-1))
    mu_tilde = float(expected.sum(axis=-1))
    sigma = float(mx.sqrt(variance.sum(axis=-1)))

    if sigma == 0:
        return 0.0
    return (mu - mu_tilde) / sigma


def per_sentence_fast_detectgpt(text: str) -> List[Tuple[str, float]]:
    return [(s, fast_detectgpt_score(s)) for s in _split_sentences(text)]


def burstiness(text: str) -> float:
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return 0.0
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    return var / mean


def _human_score(disc: float, burst: float) -> float:
    """Map Fast-DetectGPT discrepancy + burstiness into a 0-1 human_score.

    Discrepancy is inverted: higher disc = more AI, so disc >= AI_THRESHOLD
    maps to 0, disc <= HUMAN_THRESHOLD maps to 1.
    """
    disc_score = (AI_THRESHOLD - disc) / (AI_THRESHOLD - HUMAN_THRESHOLD)
    disc_score = min(1.0, max(0.0, disc_score))
    burst_score = min(1.0, max(0.0, burst / 25))
    return 0.7 * disc_score + 0.3 * burst_score


def score(text: str, top_k_worst: int = 5, with_sentences: bool = False) -> dict:
    """Full Fast-DetectGPT score for a document.

    Per-sentence scoring runs the model once per sentence and dominates
    wall-clock time. Default with_sentences=False to keep badge updates fast;
    pass True only when worst_sentences is actually consumed.

    Returns:
        fast_detectgpt: overall discrepancy (higher = AI)
        burstiness: sentence-length variance / mean
        human_score: 0-1 combined estimate (1 = human)
        sentences, worst_sentences: only when with_sentences=True
    """
    overall = fast_detectgpt_score(text)
    burst = burstiness(text)
    result = {
        "fast_detectgpt": overall,
        "burstiness": burst,
        "human_score": _human_score(overall, burst),
    }
    if with_sentences:
        sentences = per_sentence_fast_detectgpt(text)
        sorted_sents = sorted(sentences, key=lambda x: -x[1])  # highest disc first
        result["sentences"] = [{"sentence": s, "score": d} for s, d in sentences]
        result["worst_sentences"] = [s for s, _ in sorted_sents[:top_k_worst]]
    return result


if __name__ == "__main__":
    import json
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    if not text.strip():
        print("Usage: echo 'text' | python fast_detectgpt_scorer.py", file=sys.stderr)
        sys.exit(1)
    result = score(text)
    print(json.dumps({
        "fast_detectgpt": round(result["fast_detectgpt"], 4),
        "burstiness": round(result["burstiness"], 2),
        "human_score": round(result["human_score"], 3),
    }, indent=2))
