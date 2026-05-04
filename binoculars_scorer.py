"""binoculars_scorer.py — Binoculars detection (Hans et al., 2024).

Uses two LLMs:
  - observer (base model) — measures how surprising the text is
  - performer (instruct model) — predicts what should come next

Score = ln(PPL_observer(s)) / ln(X-PPL(s))

X-PPL is the cross-entropy of performer's predicted distribution against
observer's log-probabilities. AI text creates a characteristic gap between
observer perplexity and cross-perplexity that single-model detectors miss.

Lower score = more AI-like. Higher = more human-like.

Backend: MLX on Apple Silicon. Model pair (bf16, ~3GB each):
  observer:  mlx-community/Qwen2.5-1.5B-bf16
  performer: mlx-community/Qwen2.5-1.5B-Instruct-bf16
"""

import re
from typing import List, Tuple

DEFAULT_OBSERVER = "mlx-community/Qwen2.5-1.5B-bf16"
DEFAULT_PERFORMER = "mlx-community/Qwen2.5-1.5B-Instruct-bf16"

# Rough thresholds for the Qwen 1.5B pair. Recalibrate on a real corpus of
# known-AI vs known-human samples before trusting the human_score numerically.
AI_THRESHOLD = 0.82
HUMAN_THRESHOLD = 0.88

MAX_TOKENS = 2048

_observer = None
_performer = None
_tokenizer = None


def _ensure_loaded():
    global _observer, _performer, _tokenizer
    if _observer is not None:
        return _observer, _performer, _tokenizer

    from mlx_lm import load

    _observer, _tokenizer = load(DEFAULT_OBSERVER)
    _performer, _ = load(DEFAULT_PERFORMER)
    return _observer, _performer, _tokenizer


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def _encode(tokenizer, text: str):
    """Encode `text` to a 1xL mx.array of token ids, truncated to MAX_TOKENS."""
    import mlx.core as mx

    ids = tokenizer.encode(text)
    if len(ids) > MAX_TOKENS:
        ids = ids[:MAX_TOKENS]
    return mx.array([ids])


def binoculars_score(text: str) -> float:
    """Compute the Binoculars score for a text. Lower = AI, higher = human."""
    if not text.strip():
        return 0.0

    import mlx.core as mx

    obs, perf, tok = _ensure_loaded()
    input_ids = _encode(tok, text)
    if input_ids.shape[1] < 2:
        return 0.0

    obs_logits = obs(input_ids)
    perf_logits = perf(input_ids)

    obs_shift = obs_logits[..., :-1, :].astype(mx.float32)
    perf_shift = perf_logits[..., :-1, :].astype(mx.float32)
    labels = input_ids[..., 1:]

    obs_log_probs = obs_shift - mx.logsumexp(obs_shift, axis=-1, keepdims=True)
    perf_log_probs = perf_shift - mx.logsumexp(perf_shift, axis=-1, keepdims=True)
    perf_probs = mx.exp(perf_log_probs)

    gathered = mx.take_along_axis(obs_log_probs, labels[..., None], axis=-1).squeeze(-1)
    log_ppl = float(-gathered.mean())

    cross_entropy_per_token = -(perf_probs * obs_log_probs).sum(axis=-1)
    log_x_ppl = float(cross_entropy_per_token.mean())

    if log_x_ppl == 0:
        return 0.0
    return log_ppl / log_x_ppl


def per_sentence_binoculars(text: str) -> List[Tuple[str, float]]:
    return [(s, binoculars_score(s)) for s in _split_sentences(text)]


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


def _human_score(bino: float, burst: float) -> float:
    """Map Binoculars score + burstiness into a 0-1 'human_score'."""
    if bino == 0:
        return 0.0
    bino_score = min(1.0, max(0.0, (bino - AI_THRESHOLD) / (HUMAN_THRESHOLD - AI_THRESHOLD)))
    burst_score = min(1.0, max(0.0, burst / 25))
    return 0.7 * bino_score + 0.3 * burst_score


def score(text: str, top_k_worst: int = 5, with_sentences: bool = False) -> dict:
    """Full Binoculars score for a document.

    Per-sentence scoring runs the model pair once per sentence and dominates
    wall-clock time. Default with_sentences=False to keep badge updates fast;
    pass True only when worst_sentences is actually consumed.

    Returns:
        binoculars: overall Binoculars score (lower = AI)
        burstiness: sentence-length variance / mean
        human_score: 0-1 combined estimate
        sentences, worst_sentences: only when with_sentences=True
    """
    overall = binoculars_score(text)
    burst = burstiness(text)
    result = {
        "binoculars": overall,
        "burstiness": burst,
        "human_score": _human_score(overall, burst),
    }
    if with_sentences:
        sentences = per_sentence_binoculars(text)
        sorted_sents = sorted(sentences, key=lambda x: x[1])
        result["sentences"] = [{"sentence": s, "score": p} for s, p in sentences]
        result["worst_sentences"] = [s for s, _ in sorted_sents[:top_k_worst]]
    return result


if __name__ == "__main__":
    import json
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    if not text.strip():
        print("Usage: echo 'text' | python binoculars_scorer.py", file=sys.stderr)
        sys.exit(1)
    result = score(text)
    print(json.dumps({
        "binoculars": round(result["binoculars"], 4),
        "burstiness": round(result["burstiness"], 2),
        "human_score": round(result["human_score"], 3),
    }, indent=2))
