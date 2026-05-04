"""binoculars_scorer.py — Binoculars detection (Hans et al., 2024).

Uses two LLMs:
  - observer (base model) — measures how surprising the text is
  - performer (instruct model) — predicts what should come next

Score = ln(PPL_observer(s)) / ln(X-PPL(s))

X-PPL is the cross-entropy of performer's predicted distribution against
observer's log-probabilities. AI text creates a characteristic gap between
observer perplexity and cross-perplexity that single-model detectors miss.

Lower score = more AI-like. Higher = more human-like.

Default pair: Qwen2.5-1.5B + Qwen2.5-1.5B-Instruct (~3GB total).
Original paper used Falcon-7B + Falcon-7B-Instruct (~14GB).
"""

import re
from typing import List, Tuple

DEFAULT_OBSERVER = "Qwen/Qwen2.5-1.5B"
DEFAULT_PERFORMER = "Qwen/Qwen2.5-1.5B-Instruct"

# Rough thresholds for the Qwen 1.5B pair — empirical starting points from a
# short-text smoke test (AI ≈ 0.83, human ≈ 0.85). Recalibrate on a real corpus
# of known-AI vs known-human samples before trusting the human_score numerically.
AI_THRESHOLD = 0.82
HUMAN_THRESHOLD = 0.88

_observer = None
_performer = None
_tokenizer = None
_device = None
_dtype = None


def _ensure_loaded(observer_name: str = DEFAULT_OBSERVER, performer_name: str = DEFAULT_PERFORMER):
    global _observer, _performer, _tokenizer, _device, _dtype
    if _observer is not None:
        return _observer, _performer, _tokenizer, _device

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if torch.backends.mps.is_available():
        _device = "mps"
        _dtype = torch.float16
    elif torch.cuda.is_available():
        _device = "cuda"
        _dtype = torch.float16
    else:
        _device = "cpu"
        _dtype = torch.float32

    _tokenizer = AutoTokenizer.from_pretrained(observer_name)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    _observer = AutoModelForCausalLM.from_pretrained(observer_name, torch_dtype=_dtype).to(_device)
    _performer = AutoModelForCausalLM.from_pretrained(performer_name, torch_dtype=_dtype).to(_device)
    _observer.eval()
    _performer.eval()
    return _observer, _performer, _tokenizer, _device


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def binoculars_score(text: str) -> float:
    """Compute the Binoculars score for a text. Lower = AI, higher = human."""
    if not text.strip():
        return 0.0
    import torch
    import torch.nn.functional as F

    obs, perf, tok, device = _ensure_loaded()
    enc = tok(text, return_tensors="pt", truncation=True, max_length=2048).to(device)
    input_ids = enc.input_ids
    if input_ids.shape[1] < 2:
        return 0.0

    with torch.no_grad():
        obs_logits = obs(input_ids).logits
        perf_logits = perf(input_ids).logits

    # Shift so we're predicting position i+1 from position i
    obs_shift = obs_logits[..., :-1, :].float()
    perf_shift = perf_logits[..., :-1, :].float()
    labels = input_ids[..., 1:]

    # log(PPL_observer) = CE of true tokens under observer
    log_ppl = F.cross_entropy(obs_shift.reshape(-1, obs_shift.size(-1)), labels.reshape(-1), reduction="mean").item()

    # log(X-PPL) = mean over positions of -sum_v performer_prob[v] * log observer_prob[v]
    perf_probs = F.softmax(perf_shift, dim=-1)
    obs_log_probs = F.log_softmax(obs_shift, dim=-1)
    cross_entropy_per_token = -(perf_probs * obs_log_probs).sum(dim=-1)
    log_x_ppl = cross_entropy_per_token.mean().item()

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
