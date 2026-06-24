"""scorer.py — local perplexity + burstiness scoring.

Runs GPT-2 locally to compute the same signals AI detectors lean on:
- perplexity (how predictable each token is — AI = low, human = high)
- burstiness (variance / mean of sentence lengths — AI = uniform, human = varied)

Used as a free, fast oracle inside the rewrite loop. No API calls.
"""

import math
import re
from typing import List, Tuple

_model = None
_tokenizer = None
_device = None


def _ensure_loaded(model_name: str = "gpt2-large"):
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer, _device

    import torch
    from transformers import GPT2LMHeadModel, GPT2TokenizerFast

    if torch.backends.mps.is_available():
        _device = "mps"
    elif torch.cuda.is_available():
        _device = "cuda"
    else:
        _device = "cpu"

    _tokenizer = GPT2TokenizerFast.from_pretrained(model_name)
    _model = GPT2LMHeadModel.from_pretrained(model_name).to(_device)
    _model.eval()
    return _model, _tokenizer, _device


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def perplexity(text: str) -> float:
    """GPT-2 perplexity over `text`. Lower = more predictable = more AI-like."""
    if not text.strip():
        return 0.0
    import torch
    model, tok, device = _ensure_loaded()
    enc = tok(text, return_tensors="pt", truncation=True, max_length=1024).to(device)
    if enc["input_ids"].shape[1] < 2:
        return 0.0
    with torch.no_grad():
        out = model(**enc, labels=enc["input_ids"])
    loss = out.loss.item()
    if loss > 20:
        return float("inf")
    return float(math.exp(loss))


def per_sentence_perplexity(text: str) -> List[Tuple[str, float]]:
    return [(s, perplexity(s)) for s in _split_sentences(text)]


def burstiness(text: str) -> float:
    """Variance / mean of sentence word counts. Higher = more human."""
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return 0.0
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    return var / mean


def _human_score(perp: float, burst: float) -> float:
    """Rough 0-1 score combining perplexity and burstiness.

    Calibrated for gpt2-large:
    AI text typically: perp 15-30, burst <10
    Human text typically: perp 40-70+, burst 15+
    """
    if perp == float("inf"):
        perp_score = 1.0
    else:
        perp_score = min(1.0, max(0.0, (perp - 15) / 40))
    burst_score = min(1.0, max(0.0, burst / 25))
    return 0.6 * perp_score + 0.4 * burst_score


def score(text: str, top_k_worst: int = 5, backend: str = "gpt2", with_sentences: bool = False) -> dict:
    """Full local score for a document.

    Args:
        backend: "gpt2" — fast, single-model perplexity (default)
                 "binoculars" — two-model Qwen3-1.7B pair, stronger signal
                 "fast_detectgpt" — single-model Qwen3-1.7B, often beats
                 Binoculars on out-of-distribution text
        with_sentences: if False (default), skip per-sentence inference.
                 Per-sentence scoring runs the model once per sentence and
                 dominates wall-clock time on the Qwen backends. The
                 doc-level metric and human_score are unaffected.

    All backends return: burstiness, human_score. When with_sentences=True,
    also returns sentences and worst_sentences.
    """
    if backend == "binoculars":
        from binoculars_scorer import score as bino_score
        return bino_score(text, top_k_worst=top_k_worst, with_sentences=with_sentences)
    if backend == "fast_detectgpt":
        from fast_detectgpt_scorer import score as fdg_score
        return fdg_score(text, top_k_worst=top_k_worst, with_sentences=with_sentences)

    overall = perplexity(text)
    burst = burstiness(text)
    result = {
        "perplexity": overall,
        "burstiness": burst,
        "human_score": _human_score(overall, burst),
    }
    if with_sentences:
        sentences = per_sentence_perplexity(text)
        sorted_sents = sorted(sentences, key=lambda x: x[1])
        result["sentences"] = [{"sentence": s, "perplexity": p} for s, p in sentences]
        result["worst_sentences"] = [s for s, _ in sorted_sents[:top_k_worst]]
    return result


if __name__ == "__main__":
    import json
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    if not text.strip():
        print("Usage: echo 'text' | python scorer.py  OR  python scorer.py 'text'", file=sys.stderr)
        sys.exit(1)
    result = score(text)
    print(json.dumps({
        "perplexity": round(result["perplexity"], 2),
        "burstiness": round(result["burstiness"], 2),
        "human_score": round(result["human_score"], 3),
    }, indent=2))
