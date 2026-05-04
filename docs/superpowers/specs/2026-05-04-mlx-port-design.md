# MLX port: Binoculars + Fast-DetectGPT

**Status:** approved 2026-05-04
**Owner:** James Tannahill

## Problem

The two Qwen-based local detectors run on PyTorch+MPS at roughly 1–2 seconds per warm call, with cold loads occasionally hitting 50+ seconds. They are the slowest of the three detector backends and the only ones whose latency is felt during a full `/humanize` run. Apple's MLX framework is purpose-built for unified memory on Apple Silicon and typically delivers 2–3× faster transformer inference than PyTorch+MPS at equivalent precision.

## Goals

- Drop in MLX implementations of Binoculars and Fast-DetectGPT scoring.
- Preserve the public function signatures so the dispatcher (`scorer.py`), the Flask server, and the CLI entrypoints do not change.
- Keep the scoring math numerically equivalent within float-kernel tolerance (no recalibration of thresholds expected).

## Non-goals

- Porting the GPT-2 scorer (`scorer.py`). It is already fast on MPS and `mlx-lm` does not target the GPT-2 family.
- Quantization. The first port targets bf16 parity. 4-bit / 8-bit quantization is a one-line follow-up if more speed is wanted.
- Removing PyTorch. `torch` and `transformers` remain in `pyproject.toml` because the GPT-2 scorer still uses them.
- Cross-platform fallback. This is a Mac-only personal tool; if MLX is unavailable the scorer raises ImportError.

## Architecture

Two files are rewritten end-to-end while keeping their imports stable:

- `binoculars_scorer.py`
- `fast_detectgpt_scorer.py`

Public API preserved in each file:

- `binoculars_score(text) -> float` / `fast_detectgpt_score(text) -> float`
- `per_sentence_binoculars(text)` / `per_sentence_fast_detectgpt(text)`
- `burstiness(text)`
- `score(text, top_k_worst=5, with_sentences=False) -> dict`

The dispatcher in `scorer.py:109-114` continues to import these by module path. No change to `scorer.py`, `humanize_server.py`, `humanize.py`, or `prompt.py`.

## Model loading

Loaded lazily inside `_ensure_loaded`, mirroring the existing pattern. Source from HuggingFace community-converted bf16 weights:

- Observer + Fast-DetectGPT base: `mlx-community/Qwen2.5-1.5B-bf16`
- Performer: `mlx-community/Qwen2.5-1.5B-Instruct-bf16`

Loaded via `mlx_lm.load(repo_id)`, which returns `(model, tokenizer)` and caches under `~/.cache/huggingface`. This is a separate cache slot from the existing PyTorch Qwen weights — there is no way to share them, since the formats differ.

## Math layer

All arithmetic stays in MLX (`mx.array`) until the function returns. Conversions happen only at JSON boundaries via `float(arr)`.

Operator mapping:

| Current (PyTorch) | MLX equivalent |
|---|---|
| `F.softmax(x, dim=-1)` | `mx.softmax(x, axis=-1)` |
| `F.log_softmax(x, dim=-1)` | `mx.log(mx.softmax(x, axis=-1))` (or `mx.log_softmax` if available) |
| `F.cross_entropy(...)` | manual: `-mx.take_along_axis(log_softmax, labels[..., None], -1).mean()` |
| `tensor.gather(-1, idx.unsqueeze(-1)).squeeze(-1)` | `mx.take_along_axis(arr, idx[..., None], -1).squeeze(-1)` |
| `tensor.pow(2)` | `arr ** 2` |
| `tensor.clamp_min(0)` | `mx.maximum(arr, 0)` |
| `tensor.item()` | `float(arr)` |

The Binoculars scoring formula `log_ppl / log_x_ppl` and the Fast-DetectGPT formula `(mu - mu_tilde) / sigma` translate directly. No exotic ops.

## Dependencies

Add to `pyproject.toml`:

- `mlx` (core arrays + ops)
- `mlx-lm` (model loading + Qwen architecture)

Keep:

- `torch`, `transformers` (used by `scorer.py` for GPT-2)
- `anthropic`, `flask`, `python-docx` (unchanged)

Install via `uv add mlx mlx-lm`.

## Error handling

If `mlx` or `mlx-lm` import fails, `_ensure_loaded` raises ImportError with a hint to run `uv sync`. No silent fall-through to PyTorch — that defeats the purpose of the port and would mask install regressions.

If model download fails (no network on first cold load), the underlying `mlx_lm.load` exception propagates. Same behavior as the current PyTorch path.

## Verification

1. **Numerical parity smoke test.** Pick one known-AI paragraph and one known-human paragraph (~150 words each). Run each scorer before and after the port. Acceptance:
   - Binoculars score within ±0.01
   - Fast-DetectGPT discrepancy within ±0.05
   - `human_score` within ±0.02
   If drift exceeds these bounds, investigate before merging — most likely cause is a shape or axis mismatch in the math port.

2. **Wall-clock test.** Same input, warm call (after one priming call). Expect ≥ 2× speedup on the document-level call:
   - Binoculars: ~1.5s → ≤ 750ms
   - Fast-DetectGPT: ~1.0s → ≤ 500ms

3. **Cold-load test.** Restart the server, run a single `/local-score`. Expect MLX cold load ≤ PyTorch+MPS cold load (MLX skips the kernel-compile step that PyTorch does on first call).

4. **End-to-end test.** Full `/humanize` run on a 200-word input with `binoculars` backend selected. No regressions vs. the current Haiku-default + MAX_LOOPS=4 baseline.

## Risks

- **`mlx-community/Qwen2.5-1.5B-bf16` repository availability.** Both repos exist on HuggingFace today. If either is removed before deploy, the fallback is a one-time local convert: `python -m mlx_lm convert --hf-path Qwen/Qwen2.5-1.5B -q false`.
- **Threshold drift.** AI/HUMAN_THRESHOLD constants in both scorers were calibrated on PyTorch float16. If MLX bf16 produces a measurably different distribution, thresholds may need a small recalibration. The smoke test catches this.
- **`mlx-lm` API surface.** The library is younger than `transformers`; minor API differences (e.g., model `__call__` shape, tokenizer attribute names) may need adapter code. Expected impact: a handful of lines per file.

## Out of scope (deferred)

- 4-bit / 8-bit quantization
- GPT-2 MLX port
- Removing PyTorch
- Cross-platform / CUDA support
