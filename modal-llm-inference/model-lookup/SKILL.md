---
name: modal-llm-inference-model-lookup
description: Discover open-weight LLMs on HuggingFace and assess whether they're deployable on Modal with vLLM or SGLang before the user commits to a deployment. Surfaces trending/recent releases by provider or keyword, reports weight formats (safetensors vs gguf vs mlx), parameter count, license, and which inference engines can actually run it (vLLM vs SGLang vs llama.cpp vs MLX). Use this skill whenever the user asks about a specific open-source model they haven't deployed yet, says "what's new" or "what should I try" in the LLM space, mentions a provider by name (DeepSeek, Qwen, Google, Prism, MiniMax, Meta, Mistral, Z.ai, nvidia, etc.), or wants to know whether a model they're eyeing will work with vLLM or SGLang before writing deployment code.
---

# Model Lookup (sub-skill of modal-llm-inference)

Answers two questions before the user writes a `modal deploy` command:

1. **What open-weight models are out there that match this user's criteria?** (Recent, by provider, by size, by task.)
2. **Can vLLM actually serve this model, or does it need a different engine?** (Not every "open-weight" model is vLLM-compatible — Prism ML's Bonsai series ships only `gguf` and `mlx` formats, for example, which rules out vLLM entirely.)

## When to use

- User asks about a specific model: "can I run X on Modal?", "is Y vLLM-compatible?"
- User names a provider but no specific model: "what's Prism ML working on?", "any new DeepSeek releases?"
- User wants recommendations: "what's a good 30B coding model right now?"
- User is weighing options between several models — compare format/license/GPU-fit side by side

**Don't use** for closed-source APIs (OpenAI, Anthropic, Google's Gemini Pro) — those are API clients, not deployments.

## The core insight this skill exists for

HuggingFace lists tens of thousands of models. A repo being on HF does **not** mean it's deployable on vLLM. The signals that matter:

| What's in the repo | What can serve it |
|---|---|
| `.safetensors` files + `config.json` with a supported architecture | vLLM, SGLang, TensorRT-LLM, Transformers |
| `.gguf` files only | llama.cpp, Ollama, LM Studio. **Not vLLM.** |
| `-mlx-*`, `-mlx-1bit`, etc. | MLX (Apple Silicon only). **Not CUDA, not vLLM.** |
| `-AWQ`, `-GPTQ`, `-FP8`, `-NVFP4` | vLLM + matching `--quantization` flag |
| `-unpacked` (Prism-specific) | Reference weights for a proprietary stack. Check vendor docs. |

Check format **first**. Don't write deployment code for a model that can't be deployed.

## The helper script

`scripts/find_models.py` hits the HuggingFace API directly so results reflect reality as of the user's run, not a static list baked into this skill.

```bash
# List a provider's recent models
python scripts/find_models.py --author prism-ml
python scripts/find_models.py --author MiniMaxAI --limit 10

# Search by keyword, sorted by recency
python scripts/find_models.py --search "reasoning" --sort lastModified --limit 20

# Search by keyword, sorted by popularity
python scripts/find_models.py --search "coder" --sort downloads --limit 20

# Filter by size range (parameter count)
python scripts/find_models.py --search "instruct" --min-params 20B --max-params 80B

# Only show vLLM-compatible results (safetensors + known-good architectures)
python scripts/find_models.py --author Qwen --vllm-only

# Inspect a single model in detail
python scripts/find_models.py --inspect prism-ml/Bonsai-8B-gguf
```

The script **does not require authentication** for public models. For gated models (DeepSeek V4 requires accepting the license on HF), set `HF_TOKEN=hf_xxx` in the environment.

## Output format

Default output for `--search` or `--author`:

```
REPO                                    SIZE    FORMAT      ENGINE(S)           UPDATED    LICENSE
─────────────────────────────────────── ─────── ─────────── ─────────────────── ────────── ──────────
MiniMaxAI/MiniMax-M2.7                  229B    safetensors vllm, sglang        2d ago     modified-mit
google/gemma-4-26B-A4B-it               26B     safetensors vllm, sglang, trtllm 14d ago    gemma
prism-ml/Bonsai-8B-gguf                 8B      gguf        llama.cpp, ollama   18h ago    apache-2.0
prism-ml/Bonsai-8B-mlx-1bit             0.4B    mlx         mlx (Apple only)    18h ago    apache-2.0
```

`--inspect <repo>` output goes deeper — config.json architecture, tokenizer type, number of files, total size on disk, and Modal GPU sizing estimate (weights × 1.3 ÷ VRAM).

## Interpretation rules for Claude

When reporting results to the user:

1. **Lead with format, not size.** A 70B safetensors model is more useful than an 8B gguf model if the goal is Modal deployment. State both engine and GPU requirements prominently.

2. **Flag format-incompatibility as a warning, not a "here's what's available" list item.** If the user asked "can I run Prism Bonsai on Modal?", the answer is not "yes, here are the variants" — the answer is "Bonsai ships only gguf and mlx; vLLM can't serve these. On Modal you'd need llama.cpp + GGUF or a CPU/MLX workflow. Want me to sketch that instead?"

3. **Don't invent metadata.** If the API returns nulls for `downloads` or `lastModified`, say so. Don't confabulate popularity.

4. **Pin recommendations to observed data.** "MiniMax-M2.7 has 142k downloads in the past month, released 2 days ago, FP8 native" — traceable. "MiniMax-M2.7 is the hot new thing" — not.

5. **Point out when a provider has no deployable-on-vLLM models.** This is genuinely useful information; an empty set is a valid result.

6. **Surface engine choice with the recommendation.** For models under ~70B active params that fit on 1-2 GPUs, vLLM is simpler. For models requiring FP4/MXFP4, multi-GPU tensor-parallel (3+), or needing the SGLang-specific `flashinfer_mxfp4` backend, SGLang is preferred. Mention the engine alongside the model recommendation.

7. **Name the GPU hourly cost.** Don't just say "4 GPUs" — say "4×H200 at $18.16/hr". The cost number changes deployment decisions more than the model name.

## Known provider → format patterns (as of April 2026)

Snapshot of what each shop usually ships. Verify with the script — these shift.

- **google** (Gemma family): safetensors, multiple quant variants. vLLM-ready.
- **MiniMaxAI**: safetensors (FP8 native), needs `--trust-remote-code`. vLLM-ready.
- **Qwen** (Alibaba): safetensors + GGUF mirrors. vLLM-ready on the main repos.
- **deepseek-ai** (DeepSeek V4 Flash / Pro): safetensors, FP4+FP8 mixed precision. **SGLang is the canonical engine** — Modal's official `deepseek_v4.py` uses SGLang's `flashinfer_mxfp4` backend. vLLM 0.22+ also supports V4 via dedicated `deepseek_v4/` package but SGLang is preferred for multi-GPU MXFP4. Flash (284B, 13B active) needs 4×H200 minimum ($18.16/hr). Pro (1.6T, 49B active) requires 8×B200 for MXFP4 ($50/hr).
- **mistralai**: safetensors. vLLM-ready.
- **meta-llama**: safetensors. vLLM-ready.
- **zai-org** (GLM): safetensors + FP8 variants. vLLM and SGLang both supported.
- **nvidia** (Nemotron): safetensors + FP8/NVFP4. SGLang preferred, vLLM works.
- **prism-ml**: gguf + mlx-1bit only. **Not vLLM-deployable.** llama.cpp or MLX route.
- **unsloth**: mostly GGUF quants of other people's models. Not vLLM.
- **bartowski**, **mlx-community**, **ggml-org**: quantization mirrors. Not originals; may or may not be vLLM-ready depending on format.

When the user names a provider, run the script first. Don't answer from this table alone — it goes stale.
