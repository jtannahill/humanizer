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

Default model: Qwen2.5-1.5B (~3GB). Same family as Binoculars 1.5B so the
HuggingFace cache is shared — no extra disk cost if Binoculars 1.5B is loaded.
"""

import re
from typing import List, Tuple

DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B"

# Empirical starting points — calibrate on a real corpus before trusting numeric
# scores. Higher discrepancy = more AI-like. Inverted in _human_score below.
AI_THRESHOLD = 1.5      # discrepancy >= this looks AI
HUMAN_THRESHOLD = 0.5   # discrepancy <= this looks human

_model = None
_tokenizer = None
_device = None
_dtype = None


def _ensure_loaded(model_name: str = DEFAULT_MODEL):
    global _model, _tokenizer, _device, _dtype
    if _model is not None:
        return _model, _tokenizer, _device

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

    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    _model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=_dtype).to(_device)
    _model.eval()
    return _model, _tokenizer, _device


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def fast_detectgpt_score(text: str) -> float:
    """Compute the Fast-DetectGPT discrepancy. Higher = more AI-like."""
    if not text.strip():
        return 0.0
    import torch
    import torch.nn.functional as F

    model, tok, device = _ensure_loaded()
    enc = tok(text, return_tensors="pt", truncation=True, max_length=2048).to(device)
    input_ids = enc.input_ids
    if input_ids.shape[1] < 2:
        return 0.0

    with torch.no_grad():
        logits = model(input_ids).logits

    # Predict position i+1 from position i
    logits_shift = logits[..., :-1, :].float()    # (1, L-1, V)
    labels = input_ids[..., 1:]                    # (1, L-1)
    log_probs = F.log_softmax(logits_shift, dim=-1)
    probs = log_probs.exp()

    # Actual log p(x_t)
    actual = log_probs.gather(-1, labels.unsqueeze(-1)).squeeze(-1)  # (1, L-1)

    # Closed-form moments under p_t
    expected = (probs * log_probs).sum(dim=-1)              # E[log p(x̃)] per position
    expected_sq = (probs * log_probs.pow(2)).sum(dim=-1)    # E[(log p(x̃))^2] per position
    variance = (expected_sq - expected.pow(2)).clamp_min(0)

    mu = actual.sum(dim=-1)
    mu_tilde = expected.sum(dim=-1)
    sigma = variance.sum(dim=-1).sqrt()

    if sigma.item() == 0:
        return 0.0
    return ((mu - mu_tilde) / sigma).item()


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
