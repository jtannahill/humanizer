"""roberta_scorer.py — supervised RoBERTa AI-text classifier.

Unlike the other three backends (gpt2 perplexity, binoculars, fast_detectgpt),
which are zero-shot / white-box detectors that read a model's own perplexity or
curvature, this one is a *trained classifier*: a RoBERTa sequence-classification
head fine-tuned to label text as human- vs AI-written. It emits a calibrated
P(AI) directly, so it needs no hand-tuned threshold the way the perplexity
backends do — and it fails in a different, complementary way, which is the
point of adding it to the oracle ensemble.

Default model: Hello-SimpleAI/chatgpt-detector-roberta (~500MB, HC3-trained).
Swap DEFAULT_MODEL for roberta-base-openai-detector (GPT-2 era) if preferred;
both expose a 2-class AutoModelForSequenceClassification with a human/AI split,
and the class orientation is detected from config.id2label at load time.

Runs on PyTorch + MPS (fp32 — the model is tiny, and fp16 softmax on a
classifier buys nothing). RoBERTa's context is 512 tokens, far shorter than a
typical humanizer document, so long inputs are split into 510-token windows and
the per-window P(AI) is averaged, weighted by window length.
"""

import re
from typing import List, Tuple

DEFAULT_MODEL = "Hello-SimpleAI/chatgpt-detector-roberta"

# RoBERTa context limit is 512; reserve 2 slots for <s>/</s>.
WINDOW = 510

_model = None
_tokenizer = None
_device = None
_ai_idx = None
_human_idx = None


def _resolve_class_indices(config) -> Tuple[int, int]:
    """Find (ai_idx, human_idx) from config.id2label by label text.

    Falls back to the HC3/openai-detector convention (0=human, 1=AI) if the
    labels are uninformative (e.g. 'LABEL_0'/'LABEL_1').
    """
    id2label = getattr(config, "id2label", None) or {0: "human", 1: "ai"}
    ai_idx = human_idx = None
    for idx, label in id2label.items():
        text = str(label).lower()
        if any(k in text for k in ("human", "real")):
            human_idx = int(idx)
        elif any(k in text for k in ("chatgpt", "ai", "fake", "machine", "gpt")):
            ai_idx = int(idx)
    if ai_idx is None or human_idx is None:
        human_idx, ai_idx = 0, 1  # documented fallback
    return ai_idx, human_idx


def _ensure_loaded(model_name: str = DEFAULT_MODEL):
    global _model, _tokenizer, _device, _ai_idx, _human_idx
    if _model is not None:
        return _model, _tokenizer, _device

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if torch.backends.mps.is_available():
        _device = "mps"
    elif torch.cuda.is_available():
        _device = "cuda"
    else:
        _device = "cpu"

    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSequenceClassification.from_pretrained(model_name).to(_device)
    _model.eval()
    _ai_idx, _human_idx = _resolve_class_indices(_model.config)
    return _model, _tokenizer, _device


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]


def _windows(token_ids: List[int]) -> List[List[int]]:
    """Split a list of content token ids into <=WINDOW chunks."""
    if not token_ids:
        return []
    return [token_ids[i:i + WINDOW] for i in range(0, len(token_ids), WINDOW)]


def p_ai(text: str) -> float:
    """Probability the text is AI-written, 0-1.

    Long inputs are windowed at 510 content tokens; the per-window P(AI) is
    averaged weighted by window length.
    """
    if not text.strip():
        return 0.0
    import torch

    model, tok, device = _ensure_loaded()
    content = tok(text, add_special_tokens=False)["input_ids"]
    windows = _windows(content)
    if not windows:
        return 0.0

    bos, eos = tok.bos_token_id, tok.eos_token_id
    weighted_sum = 0.0
    total = 0
    with torch.no_grad():
        for win in windows:
            ids = [bos] + win + [eos]
            input_ids = torch.tensor([ids], device=device)
            logits = model(input_ids=input_ids).logits.float()
            probs = torch.softmax(logits, dim=-1)[0]
            weighted_sum += probs[_ai_idx].item() * len(win)
            total += len(win)
    return weighted_sum / total if total else 0.0


def per_sentence_p_ai(text: str) -> List[Tuple[str, float]]:
    return [(s, p_ai(s)) for s in _split_sentences(text)]


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


def _human_score(p: float, burst: float) -> float:
    """Map P(AI) + burstiness into a 0-1 human_score (1 = human).

    The classifier probability is already calibrated, so it goes in directly as
    P(human) = 1 - P(AI); burstiness keeps the same 0.7/0.3 blend the other
    backends use so the combined-oracle weighting stays comparable.
    """
    cls_score = min(1.0, max(0.0, 1.0 - p))
    burst_score = min(1.0, max(0.0, burst / 25))
    return 0.7 * cls_score + 0.3 * burst_score


def score(text: str, top_k_worst: int = 5, with_sentences: bool = False) -> dict:
    """Full RoBERTa-classifier score for a document.

    Per-sentence scoring runs the model once per sentence and dominates
    wall-clock time. Default with_sentences=False to keep badge updates fast;
    pass True only when worst_sentences is actually consumed.

    Returns:
        roberta: overall P(AI), 0-1 (higher = AI)
        burstiness: sentence-length variance / mean
        human_score: 0-1 combined estimate (1 = human)
        sentences, worst_sentences: only when with_sentences=True
    """
    overall = p_ai(text)
    burst = burstiness(text)
    result = {
        "roberta": overall,
        "burstiness": burst,
        "human_score": _human_score(overall, burst),
    }
    if with_sentences:
        sentences = per_sentence_p_ai(text)
        sorted_sents = sorted(sentences, key=lambda x: -x[1])  # highest P(AI) first
        result["sentences"] = [{"sentence": s, "score": p} for s, p in sentences]
        result["worst_sentences"] = [s for s, _ in sorted_sents[:top_k_worst]]
    return result


if __name__ == "__main__":
    import json
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    if not text.strip():
        print("Usage: echo 'text' | python roberta_scorer.py", file=sys.stderr)
        sys.exit(1)
    result = score(text)
    print(json.dumps({
        "roberta": round(result["roberta"], 4),
        "burstiness": round(result["burstiness"], 2),
        "human_score": round(result["human_score"], 3),
    }, indent=2))
