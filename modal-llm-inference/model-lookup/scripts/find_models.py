#!/usr/bin/env python3
"""
find_models.py — discover open-weight LLMs on HuggingFace and assess
whether they're deployable on Modal + vLLM.

Part of the modal-llm-inference skill. Hits HF's public API directly so
results reflect reality at runtime, not a stale table.

No dependencies beyond the Python stdlib. Works offline for --inspect of
already-downloaded repos (cached in ~/.cache/huggingface/).

Usage:
    python find_models.py --author prism-ml
    python find_models.py --author MiniMaxAI --limit 10
    python find_models.py --search reasoning --sort lastModified
    python find_models.py --search coder --min-params 20B --max-params 80B
    python find_models.py --author Qwen --vllm-only
    python find_models.py --inspect prism-ml/Bonsai-8B-gguf

Authentication:
    Optional. Set HF_TOKEN=hf_xxx in the environment for gated models or
    higher API rate limits.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


HF_API = "https://huggingface.co/api"

# Known vLLM-compatible architectures (as of vLLM 0.19).
# Source: https://docs.vllm.ai/en/latest/models/supported_models.html
# This set is a heuristic, not exhaustive — vLLM adds arches every release.
# If a repo's config.json has one of these, vLLM will almost certainly serve it.
VLLM_ARCHITECTURES = {
    "LlamaForCausalLM", "MistralForCausalLM", "MixtralForCausalLM",
    "Qwen2ForCausalLM", "Qwen3ForCausalLM", "Qwen2MoeForCausalLM", "Qwen3MoeForCausalLM",
    "GemmaForCausalLM", "Gemma2ForCausalLM", "Gemma3ForCausalLM", "Gemma4ForCausalLM",
    "DeepseekV2ForCausalLM", "DeepseekV3ForCausalLM",
    "MiniMaxText01ForCausalLM", "MiniMaxM2ForCausalLM",
    "Glm4ForCausalLM", "Glm4MoeForCausalLM",
    "Phi3ForCausalLM", "Phi4ForCausalLM",
    "FalconForCausalLM", "MPTForCausalLM",
    "CohereForCausalLM", "Cohere2ForCausalLM",
    "InternLMForCausalLM", "InternLM2ForCausalLM", "InternLM3ForCausalLM",
    "Starcoder2ForCausalLM",
    "NemotronForCausalLM", "NemotronHForCausalLM",
    # Multimodal variants vLLM supports:
    "LlavaForConditionalGeneration", "Qwen2VLForConditionalGeneration",
    "Gemma3ForConditionalGeneration", "Gemma4ForConditionalGeneration",
}


def hf_get(path: str, params: dict | None = None) -> object:
    """GET against HuggingFace API. Returns parsed JSON or raises."""
    url = f"{HF_API}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    token = os.environ.get("HF_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HF API error {e.code}: {e.reason} for {url}\n")
        if e.code == 429:
            sys.stderr.write("  (rate limited — set HF_TOKEN=hf_xxx to raise limits)\n")
        raise
    except urllib.error.URLError as e:
        sys.stderr.write(f"Network error: {e.reason}\n")
        raise


# ----- Format / engine classification -----

def classify_format(repo_id: str, siblings: list[dict] | None = None) -> str:
    """Return a coarse format label based on repo name and file listing.
    'safetensors' | 'gguf' | 'mlx' | 'pytorch-bin' | 'awq' | 'gptq' | 'fp8' | 'unknown'
    """
    lower = repo_id.lower()
    # Name-based quick checks
    if any(marker in lower for marker in ["-gguf", ".gguf", "_gguf"]):
        return "gguf"
    if "-mlx" in lower or "mlx-" in lower or "mlx_" in lower:
        return "mlx"
    if "-awq" in lower or "awq-" in lower:
        return "awq"
    if "-gptq" in lower or "gptq-" in lower:
        return "gptq"
    if "-fp8" in lower or "-nvfp4" in lower or "-fp4" in lower:
        return "fp8"
    if "-unpacked" in lower:
        return "unpacked"

    # File-based checks (more reliable when available)
    if siblings:
        filenames = [s.get("rfilename", "").lower() for s in siblings]
        if any(f.endswith(".gguf") for f in filenames):
            return "gguf"
        if any(f.endswith(".safetensors") for f in filenames):
            return "safetensors"
        if any(f.endswith(".bin") for f in filenames):
            return "pytorch-bin"
    return "unknown"


def engines_for(fmt: str, architecture: str | None = None) -> list[str]:
    """Which inference engines can serve this format+arch combo?"""
    if fmt == "gguf":
        return ["llama.cpp", "ollama", "lm-studio"]
    if fmt == "mlx":
        return ["mlx (Apple Silicon only)"]
    if fmt == "unpacked":
        return ["(reference weights — check vendor docs)"]
    if fmt in ("safetensors", "fp8", "awq", "gptq"):
        if architecture and architecture in VLLM_ARCHITECTURES:
            return ["vllm", "sglang", "transformers"]
        if architecture:
            return [f"transformers (arch {architecture} not in vLLM's known list)"]
        return ["vllm (probable)", "transformers"]
    if fmt == "pytorch-bin":
        return ["transformers", "vllm (if arch supported)"]
    return ["unknown"]


def vllm_compatible(fmt: str, architecture: str | None = None) -> bool:
    if fmt in ("gguf", "mlx", "unpacked", "unknown"):
        return False
    if architecture and architecture not in VLLM_ARCHITECTURES:
        return False
    return True


# ----- Size parsing -----

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([BMK])\b", re.IGNORECASE)


def parse_size(s: str) -> float | None:
    """Parse '26B' / '1.7B' / '120M' / '500K' into a float count of parameters."""
    if not s:
        return None
    m = _SIZE_RE.search(s)
    if not m:
        return None
    num, unit = float(m.group(1)), m.group(2).upper()
    return num * {"K": 1e3, "M": 1e6, "B": 1e9}[unit]


def format_size(n: float | None) -> str:
    if n is None:
        return "—"
    if n >= 1e9:
        return f"{n/1e9:.1f}B".rstrip("0").rstrip(".") + ("B" if not f"{n/1e9:.1f}".rstrip("0").rstrip(".").endswith(".") else "")
    if n >= 1e6:
        return f"{n/1e6:.0f}M"
    return f"{n/1e3:.0f}K"


# HF model metadata includes a numeric 'safetensors.total' (param count) when available.
def extract_params(model_meta: dict) -> float | None:
    st = model_meta.get("safetensors")
    if isinstance(st, dict) and "total" in st:
        return float(st["total"])
    # Fall back to parsing size hints from tags / modelId.
    tags = model_meta.get("tags", []) or []
    for t in tags:
        n = parse_size(t)
        if n:
            return n
    return parse_size(model_meta.get("modelId", "") or model_meta.get("id", ""))


# ----- Time formatting -----

def ago(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        ts = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10]
    delta = dt.datetime.now(dt.timezone.utc) - ts
    secs = delta.total_seconds()
    if secs < 3600:
        return f"{int(secs/60)}m ago"
    if secs < 86400:
        return f"{int(secs/3600)}h ago"
    if secs < 30 * 86400:
        return f"{int(secs/86400)}d ago"
    if secs < 365 * 86400:
        return f"{int(secs/(30*86400))}mo ago"
    return f"{int(secs/(365*86400))}y ago"


# ----- Commands -----

def cmd_list(args: argparse.Namespace) -> int:
    """Author-or-search listing."""
    params = {"limit": args.limit, "sort": args.sort, "direction": "-1"}
    if args.author:
        params["author"] = args.author
    if args.search:
        params["search"] = args.search
    if args.filter:
        params["filter"] = args.filter

    models = hf_get("models", params)
    if not isinstance(models, list):
        print("Unexpected API response; aborting.", file=sys.stderr)
        return 2

    rows: list[dict] = []
    for m in models:
        repo = m.get("modelId") or m.get("id")
        if not repo:
            continue
        siblings = m.get("siblings")  # may be absent in list endpoint
        fmt = classify_format(repo, siblings)
        params_count = extract_params(m)
        # For list endpoint, architecture often isn't in the metadata — engine guess
        # is format-based only; use --inspect for arch-aware classification.
        engines = engines_for(fmt, architecture=None)
        if args.vllm_only and not vllm_compatible(fmt):
            continue
        if args.min_params and params_count and params_count < parse_size(args.min_params):
            continue
        if args.max_params and params_count and params_count > parse_size(args.max_params):
            continue
        rows.append({
            "repo": repo,
            "size": format_size(params_count),
            "format": fmt,
            "engines": ", ".join(engines),
            "updated": ago(m.get("lastModified")),
            "downloads": m.get("downloads", 0) or 0,
            "license": _find_tag_prefix(m.get("tags", []), "license:") or "—",
        })

    if not rows:
        print("(no matches — try dropping filters)")
        return 0

    _print_table(
        rows,
        columns=[
            ("repo",      "REPO",      40),
            ("size",      "SIZE",       7),
            ("format",    "FORMAT",    11),
            ("engines",   "ENGINE(S)", 28),
            ("updated",   "UPDATED",   10),
            ("downloads", "DOWNLOADS", 10),
            ("license",   "LICENSE",   16),
        ],
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Deep-dive on a single repo: architecture, files, size, vLLM verdict."""
    repo = args.inspect
    meta = hf_get(f"models/{repo}")
    if not isinstance(meta, dict):
        return 2

    siblings = meta.get("siblings", []) or []
    config = meta.get("config", {}) or {}
    architectures = config.get("architectures") or []
    arch = architectures[0] if architectures else None
    fmt = classify_format(repo, siblings)
    params_count = extract_params(meta)
    engines = engines_for(fmt, arch)
    vllm_ok = vllm_compatible(fmt, arch)

    # Sum known file sizes (HF reports size per sibling when available).
    total_bytes = 0
    known_size = False
    for s in siblings:
        sz = s.get("size")
        if isinstance(sz, int):
            total_bytes += sz
            known_size = True

    # Cheap GPU-fit hint: need weights × 1.3 for KV cache headroom.
    gpu_hint = _gpu_hint(total_bytes) if known_size else None

    print(f"─── {repo} ───")
    print(f"  Architecture:  {arch or '(not declared)'}")
    print(f"  Format:        {fmt}")
    print(f"  Parameters:    {format_size(params_count)}")
    if known_size:
        print(f"  Disk size:     {total_bytes / 1e9:.1f} GB across {len(siblings)} files")
    print(f"  License:       {_find_tag_prefix(meta.get('tags', []) or [], 'license:') or '—'}")
    print(f"  Last update:   {meta.get('lastModified', '—')}")
    print(f"  Downloads:     {meta.get('downloads', 0) or 0}")
    print(f"  Engines:       {', '.join(engines)}")
    print()
    if vllm_ok:
        print(f"  ✅ vLLM-compatible — can deploy with modal-llm-inference skill's standard pattern.")
        if gpu_hint:
            print(f"     GPU hint:   {gpu_hint}")
    else:
        print(f"  ❌ Not directly vLLM-compatible.")
        if fmt == "gguf":
            print(f"     Run on Modal with llama.cpp (modal-examples/06_gpu_and_ml/llm-serving/ollama.py)")
            print(f"     or in-process via ctransformers. Not through vllm serve.")
        elif fmt == "mlx":
            print(f"     MLX-1bit / MLX quants run only on Apple Silicon — not on Modal's CUDA GPUs.")
            print(f"     Look for a safetensors or GGUF variant of the same base model.")
        elif fmt == "unpacked":
            print(f"     Vendor-specific reference weights. Check the model card for runtime instructions.")
        elif arch and arch not in VLLM_ARCHITECTURES:
            print(f"     Architecture {arch!r} isn't in vLLM's supported list as of this script's data.")
            print(f"     Check https://docs.vllm.ai/en/latest/models/supported_models.html for updates.")
    return 0


# ----- Helpers -----

def _gpu_hint(bytes_: int) -> str:
    """Suggest a Modal GPU fit from total weight bytes."""
    need_gb = bytes_ * 1.3 / 1e9  # weights + KV cache headroom
    if need_gb <= 40:
        return f"~{need_gb:.0f}GB needed → fits on L40S(48GB) / A100-40GB"
    if need_gb <= 80:
        return f"~{need_gb:.0f}GB needed → fits on A100-80GB / H100"
    if need_gb <= 140:
        return f"~{need_gb:.0f}GB needed → fits on single H200(141GB)"
    if need_gb <= 180:
        return f"~{need_gb:.0f}GB needed → fits on single B200(192GB)"
    gpus = max(2, int(need_gb / 140) + (1 if need_gb % 140 else 0))
    return f"~{need_gb:.0f}GB needed → {gpus}×H200 (or {max(2, gpus*2)}×H100) with --tensor-parallel-size"


def _find_tag_prefix(tags: list[str], prefix: str) -> str | None:
    for t in tags:
        if t.startswith(prefix):
            return t[len(prefix):]
    return None


def _print_table(rows: list[dict], columns: list[tuple[str, str, int]]) -> None:
    # Header
    parts = []
    for _, header, width in columns:
        parts.append(header.ljust(width))
    print(" ".join(parts))
    # Separator
    print(" ".join("─" * w for _, _, w in columns))
    # Rows
    for row in rows:
        parts = []
        for key, _, width in columns:
            val = str(row.get(key, ""))
            if len(val) > width:
                val = val[: width - 1] + "…"
            parts.append(val.ljust(width))
        print(" ".join(parts))


# ----- CLI -----

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find and assess open-weight LLMs on HuggingFace.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--author", help="Filter by HF org/user (e.g. prism-ml, MiniMaxAI)")
    p.add_argument("--search", help="Keyword search")
    p.add_argument("--filter", help="HF filter tag (e.g. 'text-generation')")
    p.add_argument("--sort", default="lastModified",
                   choices=["lastModified", "downloads", "likes", "trending-score"],
                   help="Sort order (default: lastModified)")
    p.add_argument("--limit", type=int, default=15, help="Max rows to return")
    p.add_argument("--vllm-only", action="store_true",
                   help="Only show results whose format is vLLM-deployable")
    p.add_argument("--min-params", help="Min parameter count, e.g. 7B, 30B")
    p.add_argument("--max-params", help="Max parameter count, e.g. 70B, 500B")
    p.add_argument("--inspect", metavar="REPO",
                   help="Deep-dive on a single repo (overrides list flags)")
    args = p.parse_args(argv)

    if args.inspect:
        return cmd_inspect(args)
    if not (args.author or args.search or args.filter):
        p.error("specify --author, --search, --filter, or --inspect")
    return cmd_list(args)


if __name__ == "__main__":
    sys.exit(main())
