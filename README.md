# HÜMÄNIẞAHHH

Strips LLM fingerprints from text. Rewrites AI-generated prose to read as authentically human-written — removes hedging language, em dashes, over-structured bullets, filler openers, and other telltale patterns. Preserves all original meaning, facts, and sentential logic.

## Features

- Matter-of-fact voice: no opinion, no slang, no first-person additions
- Input-grounded language: never introduces vocabulary not in the original
- Sentential logic preservation: causality, conditionals, negation, and hedge level all intact
- Multi-pass rewriting: structural, perplexity, sentence, and nuclear (fact-extract → rewrite-from-scratch) passes
- Nuclear rewrite is on by default and runs first in the loop; output capped at +20% of original word count
- Combined-oracle loop: tracks best output by `0.7 × GPTZero + 0.3 × (1 − local_human_score)`; final badge still reports the GPTZero number
- Subtle error injection to break statistical AI signatures
- Pluggable local detector (oracle): GPT-2 perplexity, Binoculars (Qwen 2.5-1.5B), or Fast-DetectGPT (Qwen 2.5-1.5B)
- Prompt caching on the main system prompt (1h TTL) to keep API cost down on repeat runs
- Explicit `temperature=1.0` on all Claude calls (Anthropic's max) for documented sampling behavior

## Usage

```bash
# Web UI
./start.sh
# open http://localhost:5757

# CLI — rewrites a file (saves to input_humanized.txt)
python3 humanize.py input.txt

# CLI — specify output path
python3 humanize.py input.txt output.txt
```

## Stack

- Python 3.10+, Flask, `anthropic` SDK
- All prompt logic in `prompt.py` — edit there to update all passes
- Local detectors in `scorer.py` (dispatcher), `binoculars_scorer.py`, `fast_detectgpt_scorer.py`
- GPT-2 and Binoculars run on PyTorch+MPS; Fast-DetectGPT runs on MLX (Apple Silicon native, bf16). Weights download to the HuggingFace cache on first use — separate cache slots for the PyTorch (`Qwen/Qwen2.5-1.5B`, `Qwen/Qwen2.5-1.5B-Instruct`) and MLX (`mlx-community/Qwen2.5-1.5B-bf16`) variants.

## Detector backends

Switch via the dropdown in the header. The selected backend feeds the loop oracle alongside GPTZero (70% GPTZero / 30% local). Thresholds in `binoculars_scorer.py` and `fast_detectgpt_scorer.py` are rough starting points — calibrate on a real corpus before trusting the numeric `human_score`.

| Backend | Runtime | Model | Memory | Warm latency | Notes |
|---|---|---|---|---|---|
| `gpt2` | PyTorch+MPS | GPT-2 large | ~2GB | ~150ms | Default; fastest cold-start; weakest signal |
| `binoculars` | PyTorch+MPS | Qwen 2.5-1.5B + Instruct (pair) | ~6GB | ~250ms | Stronger signal; closer to paper-quality |
| `fast_detectgpt` | MLX (bf16) | Qwen 2.5-1.5B | ~3GB | ~70–120ms | Single model, often beats Binoculars on out-of-distribution text |

> **Pick one backend per session.** Each backend lazy-loads its weights on first use and stays resident. Switching mid-session leaves all selected backends in unified memory; on a 16GB Mac, GPT-2 + Binoculars + Fast-DetectGPT together (~11GB) will trigger heavy swap. Restart the server to flush.

## Loop strategy rotation

When you click HUMANIZE the loop runs up to 4 iterations, rotating through these strategies:

1. **Nuclear** (default on) — extract every fact, claim, number, name, date as a bullet list, then write fresh prose from those bullets. Most fingerprint-breaking pass. Hard-capped at +20% of original word count (prompt + post-processing).
2. **Sentence rewrite** — rewrites only sentences flagged by GPTZero, with diagnostic context (burstiness, paraphrased vs. pure-AI subclass) baked into the prompt.
3. **Perplexity injection** — replaces high-probability words with lower-probability but natural alternatives in flagged sentences.
4. **Structural rewrite** — full-document restructure: clause reordering, paragraph splits/merges, sentence-length extremes for burstiness.

The loop tracks the lowest combined-oracle score across all iterations and restores that version at the end if the final pass regressed. The final status line and score badge always show the GPTZero score for the best output, since that's the user-facing number.

Toggle nuclear off (header button) to fall back to the 3-strategy rotation.

## Setup

```bash
uv sync                       # installs from pyproject.toml + uv.lock
cp start.sh.example start.sh  # add your ANTHROPIC_API_KEY (or use a .env file)
chmod +x start.sh
./start.sh
```

> `start.sh` is gitignored — it contains your API key. The `mlx` and `mlx-lm` deps are Apple Silicon only; on non-Mac hosts `uv sync` will fail there. Fast-DetectGPT is the only backend that requires them.

## Tests

```bash
uv run pytest tests/ -v       # parity tests (~30s warm, ~2 min cold)
uv run python scripts/bench_scorers.py  # warm-call latency per backend
```
