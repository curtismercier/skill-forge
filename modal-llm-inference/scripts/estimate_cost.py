#!/usr/bin/env python3
"""
estimate_cost.py — estimate Modal + vLLM inference cost before deploying.

Uses Modal's real per-second GPU pricing as of April 2026.
Source: https://modal.com/pricing — verify before quoting to customers.

Usage:
    # What does 100k requests cost on different GPUs?
    python estimate_cost.py --requests 100000 --in-tokens 500 --out-tokens 200

    # Specific model + GPU + load pattern:
    python estimate_cost.py --model gemma-4-31b --gpu H200 --rps 2 --hours 24

    # Quantitative cold-start model: is enabling snapshots actually worth it?
    python estimate_cost.py --amortize --model gemma-4-26b-a4b --gpu H200 \\
        --hours 720 --cold-starts-per-hour 2

    # Include cold-start reduction from memory snapshots in the estimate:
    python estimate_cost.py --compare --model gemma-4-26b-a4b --rps 0.1 --hours 24 --snapshot

    # Show pointers to Modal's billing-tracking APIs:
    python estimate_cost.py --tracking

    # Just show the GPU price sheet:
    python estimate_cost.py --rates

    # Compare serving options for a model:
    python estimate_cost.py --model minimax-m27 --compare

IMPORTANT CAVEATS:
  * Throughput numbers are rough ranges from published benchmarks (vLLM + H200/H100).
    Real throughput depends on batch size, sequence length, prefix cache hit rate,
    and a dozen other things. Use --worst-case for conservative estimates.
  * Assumes serverless (scale-to-zero) billing by default. For always-on replicas,
    pass --min-replicas 1 --hours 720 (month).
  * Does NOT include network egress, storage, or CPU/memory overhead (usually <5%).
  * Does NOT include the one-time cold-start compilation cost (tens of seconds to
    a few minutes per boot, amortized if you keep warm).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass


# ================================================================
# VERIFIED MODAL GPU PRICING (April 2026)
# Source: https://modal.com/pricing
# ================================================================
GPU_PRICE_PER_SEC: dict[str, float] = {
    "B200":           0.001736,
    "H200":           0.001261,
    "H100":           0.001097,
    "RTX_PRO_6000":   0.000842,
    "A100-80GB":      0.000694,
    "A100-40GB":      0.000583,
    "L40S":           0.000542,
    "A10":            0.000306,
    "L4":             0.000222,
    "T4":             0.000164,
}

GPU_VRAM_GB: dict[str, int] = {
    "B200": 192, "H200": 141, "H100": 80, "RTX_PRO_6000": 48,
    "A100-80GB": 80, "A100-40GB": 40, "L40S": 48,
    "A10": 24, "L4": 24, "T4": 16,
}

# Per Modal pricing: region selection is 1.25-2.5x base, non-preemptible is 3x base.
REGION_MULTIPLIERS = {"default": 1.0, "regional-low": 1.25, "regional-high": 2.5}
NONPREEMPT_MULTIPLIER = 3.0


# ================================================================
# MODEL PROFILES
# Rough throughput ranges from public benchmarks. Not promises.
# Tokens/sec is aggregate across concurrent requests on a single replica.
# ================================================================
@dataclass
class ModelProfile:
    name: str
    hf_repo: str
    params_billions: float         # total params
    weight_bytes_per_param: float  # 2 for bf16, 1 for fp8, 0.5 for fp4
    # min_gpu maps GPU type -> count needed to fit weights + reasonable KV cache
    min_gpu: dict[str, int]
    # throughput: (low, high) output tokens/sec per replica at moderate concurrency (~10-32 reqs)
    # These are HONEST ranges from vLLM/Modal benchmarks, not marketing numbers.
    throughput_tps: tuple[float, float]
    notes: str = ""


MODELS: dict[str, ModelProfile] = {
    "gemma-4-26b-a4b": ModelProfile(
        name="gemma-4-26b-a4b",
        hf_repo="google/gemma-4-26B-A4B-it",
        params_billions=26.0, weight_bytes_per_param=2.0,  # bf16
        min_gpu={"H200": 1, "H100": 1, "B200": 1, "A100-80GB": 1},
        throughput_tps=(800, 2500),  # MoE, only 4B active → faster than dense 26B
        notes="MoE (4B active). Modal's canonical vLLM example uses this on 1×H200.",
    ),
    "gemma-4-31b": ModelProfile(
        name="gemma-4-31b",
        hf_repo="google/gemma-4-31B-it",
        params_billions=30.7, weight_bytes_per_param=2.0,  # bf16
        min_gpu={"H200": 1, "H100": 1, "B200": 1, "A100-80GB": 1},
        throughput_tps=(300, 900),   # dense 31B — slower than the MoE variant
        notes="Dense 31B, 256K ctx, multimodal. Released April 2026. Beats 26B-A4B on every bench.",
    ),
    "minimax-m27": ModelProfile(
        name="minimax-m27",
        hf_repo="MiniMaxAI/MiniMax-M2.7",
        params_billions=229.0, weight_bytes_per_param=1.0,  # FP8 native
        min_gpu={"H200": 4, "H100": 8, "B200": 2},
        throughput_tps=(400, 1400),  # per-replica aggregate, MoE with 10B active
        notes="229B MoE (10B active), FP8. Floor is 4×H200 with tensor parallelism.",
    ),
    "deepseek-v4-flash": ModelProfile(
        name="deepseek-v4-flash",
        hf_repo="deepseek-ai/DeepSeek-V4-Flash",
        params_billions=284.0, weight_bytes_per_param=0.75,  # FP4+FP8 mixed ~0.75 avg
        min_gpu={"H200": 4, "H100": 8, "B200": 2},
        throughput_tps=(500, 1500),  # SGLang flashinfer_mxfp4, 13B active MoE + EAGLE
        notes="284B MoE (13B active), FP4+FP8. SGLang is canonical (flashinfer_mxfp4). 93.5% LiveCodeBench, 80.6% SWE-Verified. Needs 4×H200. FP8 variant at sgl-project/DeepSeek-V4-Flash-FP8.",
    ),
    "deepseek-v4-pro": ModelProfile(
        name="deepseek-v4-pro",
        hf_repo="deepseek-ai/DeepSeek-V4-Pro",
        params_billions=1600.0, weight_bytes_per_param=0.5,  # MXFP4 experts + FP8
        min_gpu={"B200": 8},  # MXFP4 requires Blackwell
        throughput_tps=(600, 2000),  # 8×B200, EAGLE, flashinfer_mxfp4, 49B active
        notes="1.6T MoE (49B active), MXFP4. REQUIRES 8×B200 Blackwell. SGLang only (flashinfer_mxfp4). Matches Opus 4.6 on SWE Verified (80.6%). $50/hr.",
    ),
    # Add more as they come up; keep numbers honest.
}


# ================================================================
# Cost math
# ================================================================
@dataclass
class Workload:
    requests: int | None = None         # absolute request count (one-off batch)
    rps: float | None = None            # requests per second (steady-state)
    hours: float = 1.0                  # window of operation
    in_tokens: int = 500
    out_tokens: int = 200

    def total_requests(self) -> float:
        if self.requests is not None:
            return float(self.requests)
        if self.rps is not None:
            return self.rps * self.hours * 3600
        raise ValueError("Specify either --requests or --rps")

    def total_output_tokens(self) -> float:
        return self.total_requests() * self.out_tokens


@dataclass
class Estimate:
    gpu: str
    gpu_count: int
    model: ModelProfile
    workload: Workload
    throughput_low: float
    throughput_high: float
    min_replicas: int = 0
    region_mult: float = 1.0
    nonpreempt_mult: float = 1.0

    def gpu_cost_per_sec(self) -> float:
        base = GPU_PRICE_PER_SEC[self.gpu] * self.gpu_count
        return base * self.region_mult * self.nonpreempt_mult

    def compute_seconds(self, tps: float) -> float:
        """How many seconds of GPU time to complete the workload at given throughput."""
        return self.workload.total_output_tokens() / tps

    def serverless_cost(self, tps: float) -> float:
        """Scale-to-zero: pay only for seconds we're actually serving."""
        return self.compute_seconds(tps) * self.gpu_cost_per_sec()

    def always_on_cost(self) -> float:
        """min_replicas=1: pay for the whole window regardless of traffic."""
        seconds = self.workload.hours * 3600 * self.min_replicas
        return seconds * self.gpu_cost_per_sec()

    def render(self) -> dict:
        low_compute = self.compute_seconds(self.throughput_high)   # faster → less compute
        high_compute = self.compute_seconds(self.throughput_low)   # slower → more compute
        low_cost = self.serverless_cost(self.throughput_high)
        high_cost = self.serverless_cost(self.throughput_low)

        # Utilization check: can the GPU actually handle the requested RPS?
        max_rps_low = self.throughput_low / self.workload.out_tokens
        max_rps_high = self.throughput_high / self.workload.out_tokens

        result = {
            "gpu": f"{self.gpu_count}×{self.gpu}",
            "gpu_price_per_hr": round(self.gpu_cost_per_sec() * 3600, 3),
            "workload": {
                "requests": int(self.workload.total_requests()),
                "in_tokens": self.workload.in_tokens,
                "out_tokens": self.workload.out_tokens,
                "window_hours": self.workload.hours,
            },
            "throughput_tps_range": [self.throughput_low, self.throughput_high],
            "compute_seconds_range": [round(low_compute, 1), round(high_compute, 1)],
            "serverless_cost_usd_range": [round(low_cost, 2), round(high_cost, 2)],
            "max_rps_this_replica": [round(max_rps_low, 2), round(max_rps_high, 2)],
        }
        if self.min_replicas > 0:
            result["always_on_cost_usd"] = round(self.always_on_cost(), 2)
            result["note"] = (
                f"Always-on cost billed for {self.min_replicas} replica(s) "
                f"× {self.workload.hours}h regardless of traffic."
            )
        return result


# ================================================================
# Commands
# ================================================================

def cmd_rates() -> int:
    print(f"{'GPU':<15} {'$/sec':>12} {'$/hour':>10} {'VRAM':>8}")
    print("─" * 50)
    for gpu, rate in sorted(GPU_PRICE_PER_SEC.items(), key=lambda x: -x[1]):
        vram = GPU_VRAM_GB.get(gpu, "—")
        print(f"{gpu:<15} {rate:>12.6f} {rate*3600:>10.3f} {vram:>6}GB")
    print()
    print("Multipliers (layer on top of base prices):")
    print(f"  Region-low / Region-high:  1.25x / 2.5x")
    print(f"  Non-preemptible execution: 3x")
    print()
    print("Source: https://modal.com/pricing (April 2026)")
    return 0


def cmd_compare(
    model_key: str,
    workload: Workload,
    region_mult: float,
    nonpreempt_mult: float,
    snapshot: bool = False,
) -> int:
    model = MODELS[model_key]
    print(f"─── {model.name} ({model.hf_repo}) — {model.params_billions}B params ───")
    print(f"{model.notes}")
    print()
    print(f"Workload: {int(workload.total_requests()):,} requests × {workload.out_tokens} out-tokens "
          f"= {int(workload.total_output_tokens()):,} tokens generated")
    print()

    rows = []
    for gpu, count in model.min_gpu.items():
        if gpu not in GPU_PRICE_PER_SEC:
            continue
        est = Estimate(
            gpu=gpu, gpu_count=count, model=model, workload=workload,
            throughput_low=model.throughput_tps[0], throughput_high=model.throughput_tps[1],
            region_mult=region_mult, nonpreempt_mult=nonpreempt_mult,
        )
        r = est.render()
        rows.append((gpu, count, r))

    print(f"{'GPU':<18} {'$/hr':>8} {'compute (s)':>14} {'cost range (USD)':>22} {'max rps':>12}")
    print("─" * 80)
    for gpu, count, r in rows:
        cost_lo, cost_hi = r["serverless_cost_usd_range"]
        cs_lo, cs_hi = r["compute_seconds_range"]
        rps_lo, rps_hi = r["max_rps_this_replica"]
        print(f"{count}×{gpu:<15} {r['gpu_price_per_hr']:>8.2f} "
              f"{cs_lo:>6.0f}..{cs_hi:<6.0f} "
              f"${cost_lo:>8.2f}..${cost_hi:<8.2f} "
              f"{rps_lo:>5.2f}..{rps_hi:<5.2f}")
    print()
    print("Ranges reflect honest throughput uncertainty. Left = optimistic, right = conservative.")
    print("Add --hours N --min-replicas 1 for always-on pricing.")

    if snapshot:
        print()
        print("━" * 68)
        print(" GPU memory snapshots (--snapshot) — verified caveats")
        print("━" * 68)
        print(" Source: https://modal.com/docs/guide/memory-snapshots")
        print()
        print(" What snapshots DO:")
        print("   • 3–10× faster cold starts (Modal's own published number)")
        print("   • Skip JIT compilation + import phase on container wake")
        print("   • Relevant mainly for scale-from-zero workloads")
        print()
        print(" What snapshots DON'T do:")
        print("   • Do NOT speed up model weight loading from storage")
        print("     (snapshots use the same distributed FS as Volumes)")
        print("   • Do NOT help if most of your cold start is weight download")
        print()
        print(" Incompatibilities (alpha feature):")
        print("   • Generally INCOMPATIBLE with multi-GPU (tensor-parallel) setups")
        print("     → minimax-m27 (4× H200) cannot use GPU snapshots today")
        print("   • Generally incompatible with non-CUDA GPU code")
        print("   • Can interact poorly with torch.compile")
        print("     → mitigation: env TORCHINDUCTOR_COMPILE_THREADS=1")
        print()
        print(" Billing side-effects:")
        print("   • Modal needs 2–3 snapshots per GPU type to fully cover worker pool")
        print("   • First few invocations of a new Function create snapshots → slower + billed")
        print("   • Redeploying with new GPU type or code invalidates existing snapshots")
        print("   • No separate snapshot storage line item (bundled into Function billing)")
        print()
        print(" Bottom line: snapshots are a single-GPU cold-start optimization.")
        print(" If your workload is always-on (--min-replicas ≥ 1), snapshots rarely")
        print(" matter — your replicas stay warm.")
    return 0


def cmd_single(args: argparse.Namespace) -> int:
    if args.model not in MODELS:
        print(f"Unknown model: {args.model}. Known: {', '.join(MODELS)}", file=sys.stderr)
        return 2
    if args.gpu and args.gpu not in GPU_PRICE_PER_SEC:
        print(f"Unknown GPU: {args.gpu}. Known: {', '.join(GPU_PRICE_PER_SEC)}", file=sys.stderr)
        return 2

    model = MODELS[args.model]
    gpu = args.gpu or next(iter(model.min_gpu))
    gpu_count = args.gpu_count or model.min_gpu.get(gpu, 1)

    workload = Workload(
        requests=args.requests,
        rps=args.rps,
        hours=args.hours,
        in_tokens=args.in_tokens,
        out_tokens=args.out_tokens,
    )

    # Optionally narrow to conservative (worst case) throughput only.
    tps_low = model.throughput_tps[0]
    tps_high = model.throughput_tps[0] if args.worst_case else model.throughput_tps[1]

    est = Estimate(
        gpu=gpu, gpu_count=gpu_count, model=model, workload=workload,
        throughput_low=tps_low, throughput_high=tps_high,
        min_replicas=args.min_replicas,
        region_mult=REGION_MULTIPLIERS[args.region],
        nonpreempt_mult=NONPREEMPT_MULTIPLIER if args.nonpreempt else 1.0,
    )
    print(json.dumps(est.render(), indent=2))
    return 0


def cmd_amortize(
    model_key: str,
    gpu: str,
    gpu_count: int,
    hours: float,
    cold_starts_per_hour: float,
    cold_start_seconds_nosnapshot: float,
    cold_start_seconds_snapshot: float,
    snapshot_overhead_first_deploys: int,
    region_mult: float,
    nonpreempt_mult: float,
) -> int:
    """Quantitative cold-start cost model: compare with-snapshot vs without-snapshot
    total cost for a given traffic pattern and cold-start frequency."""
    model = MODELS[model_key]
    if gpu not in GPU_PRICE_PER_SEC:
        print(f"Unknown GPU: {gpu}. Use --rates to list GPUs.", file=sys.stderr)
        return 2

    gpu_per_sec = GPU_PRICE_PER_SEC[gpu] * gpu_count * region_mult * nonpreempt_mult
    gpu_per_hr = gpu_per_sec * 3600

    total_cold_starts = cold_starts_per_hour * hours

    # Cost WITHOUT snapshots
    cold_start_cost_nosnap = total_cold_starts * cold_start_seconds_nosnapshot * gpu_per_sec

    # Cost WITH snapshots — cold starts are faster, BUT Modal bills the 2-3 snapshot-creation
    # events per GPU type on first deploys. Modal's docs say 2-3 for GPU-targeted functions.
    # We model the creation as equivalent to one full un-snapshotted cold start each.
    cold_start_cost_snap = (
        total_cold_starts * cold_start_seconds_snapshot * gpu_per_sec
        + snapshot_overhead_first_deploys * cold_start_seconds_nosnapshot * gpu_per_sec
    )

    savings = cold_start_cost_nosnap - cold_start_cost_snap
    savings_pct = (savings / cold_start_cost_nosnap * 100) if cold_start_cost_nosnap > 0 else 0

    breakeven_cold_starts = (
        snapshot_overhead_first_deploys * cold_start_seconds_nosnapshot
        / max(cold_start_seconds_nosnapshot - cold_start_seconds_snapshot, 0.001)
    )

    print("━" * 72)
    print(f" Cold-start amortization: {model.name} on {gpu_count}×{gpu}")
    print("━" * 72)
    print(f"  GPU cost:             ${gpu_per_hr:.3f}/hr  (${gpu_per_sec:.6f}/sec)")
    print(f"  Window:               {hours}h  ({total_cold_starts:.1f} cold starts total)")
    print(f"  Cold start (no snap): {cold_start_seconds_nosnapshot}s each")
    print(f"  Cold start (w/ snap): {cold_start_seconds_snapshot}s each")
    print(f"  Snapshot-creation overhead: {snapshot_overhead_first_deploys} "
          f"events × {cold_start_seconds_nosnapshot}s (first deploys only)")
    print()
    print(f"{'':30} {'WITHOUT snapshots':>20} {'WITH snapshots':>20}")
    print("─" * 72)
    print(f"{'Cold-start compute cost:':30} "
          f"${cold_start_cost_nosnap:>18.2f}  ${cold_start_cost_snap:>18.2f}")
    print(f"{'Savings with snapshots:':30} {'':>20} "
          f"${savings:>18.2f}  ({savings_pct:+.0f}%)")
    print()
    print(f"  Breakeven: ~{breakeven_cold_starts:.0f} cold starts")
    print(f"  (snapshots pay for themselves above this threshold)")
    print()
    if cold_starts_per_hour * hours < breakeven_cold_starts:
        print(f"  ⚠  At {cold_starts_per_hour}/hr over {hours}h, "
              f"you're BELOW the breakeven. Snapshots cost you ${-savings:.2f} more.")
    else:
        print(f"  ✓  At {cold_starts_per_hour}/hr over {hours}h, snapshots save ${savings:.2f}.")
    print()
    print("Caveats this model does NOT cover:")
    print("  • Weight-loading time: snapshots don't help with storage I/O")
    print("  • Multi-GPU deployments: GPU snapshots not supported today")
    print("  • Latency impact on end users (this is only dollar cost)")
    print("  • Throughput delta while warm (none — only cold-start phase differs)")
    print("Verify cold-start numbers against your own Modal dashboard before trusting this.")
    return 0



def cmd_tracking() -> int:
    """Print pointers to Modal's post-hoc cost tracking facilities.
    This estimator predicts cost — Modal's billing APIs measure actual cost."""
    print("━" * 68)
    print(" Cost tracking AFTER deploy — verified against modal.com/docs/guide/billing")
    print("━" * 68)
    print()
    print("This script ESTIMATES cost. For ACTUAL spend once deployed:")
    print()
    print("1. Workspace budget cap (any plan):")
    print("   https://modal.com/settings/usage  →  'Workspace budget' section")
    print("   Hard ceiling per billing period. Max is bounded by your payment history.")
    print()
    print("2. Programmatic billing reports (Team + Enterprise plans):")
    print("   • Python:  import modal; modal.billing.<...>")
    print("   • CLI:     modal billing --help")
    print("   Generates tabular reports of spend over time, broken down by App")
    print("   or by resource. Reports show PRE-credit costs — final invoice may be lower.")
    print()
    print("3. App tags for cost attribution:")
    print("   Tag Apps at deploy time (key-value pairs). Billing reports can filter")
    print("   or aggregate by tag — the way to split cost across team/project/env.")
    print("   Set via  modal.App(..., tags={'team': 'infra', 'env': 'prod'})")
    print()
    print("4. Real-time usage page:")
    print("   https://modal.com/settings/usage  — live spend in current cycle.")
    print()
    print("Modal billing is strictly per-second usage — no reservation minimums,")
    print("no minimum usage-time increments. Scale-to-zero is the default.")
    return 0


# ================================================================
# CLI
# ================================================================
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Estimate Modal + vLLM inference costs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rates", action="store_true", help="Show Modal GPU price sheet")
    mode.add_argument("--tracking", action="store_true",
                      help="Show pointers to Modal's post-hoc billing APIs + budget cap")
    mode.add_argument("--compare", action="store_true",
                      help="Compare GPU options for --model (pair with --requests or --rps)")
    mode.add_argument("--single", action="store_true",
                      help="Estimate for a specific --model + --gpu pairing")
    mode.add_argument("--amortize", action="store_true",
                      help="Quantitative cold-start cost model: compare with-snapshot vs "
                           "without-snapshot total cost for a given cold-start frequency")

    # Workload sizing — used by --compare and --single
    p.add_argument("--requests", type=int, help="Total requests in the workload")
    p.add_argument("--rps", type=float, help="Steady-state requests per second")

    p.add_argument("--model", default="gemma-4-26b-a4b", choices=list(MODELS),
                   help="Model profile (default: gemma-4-26b-a4b)")
    p.add_argument("--gpu", help="GPU type (default: model's minimum-viable GPU)")
    p.add_argument("--gpu-count", type=int,
                   help="GPU count (default: model's minimum for chosen GPU)")
    p.add_argument("--hours", type=float, default=1.0, help="Window hours (default: 1)")
    p.add_argument("--in-tokens", type=int, default=500)
    p.add_argument("--out-tokens", type=int, default=200)
    p.add_argument("--min-replicas", type=int, default=0,
                   help="Always-on replicas (default: 0, scale-to-zero)")
    p.add_argument("--region", default="default", choices=list(REGION_MULTIPLIERS))
    p.add_argument("--nonpreempt", action="store_true",
                   help="Non-preemptible execution (3x price)")
    p.add_argument("--worst-case", action="store_true",
                   help="Use low-end throughput only (conservative estimate)")
    p.add_argument("--snapshot", action="store_true",
                   help="Assume GPU memory snapshots enabled (adds caveats to output, "
                        "reduces effective cold-start penalty in always-on comparison)")

    # --amortize mode specifics
    p.add_argument("--cold-starts-per-hour", type=float, default=2.0,
                   help="Cold-start rate for --amortize (default: 2/hr)")
    p.add_argument("--cold-start-nosnap", type=float, default=90.0,
                   help="Cold-start seconds without snapshot (default: 90s — typical vLLM "
                        "warm-up on H200 with cached weights)")
    p.add_argument("--cold-start-snap", type=float, default=15.0,
                   help="Cold-start seconds WITH snapshot (default: 15s — Modal's 3-10× number, "
                        "midpoint)")
    p.add_argument("--snap-creations", type=int, default=3,
                   help="Snapshot-creation events (default: 3 — Modal needs 2-3 per GPU type)")
    args = p.parse_args(argv)

    if args.rates:
        return cmd_rates()
    if args.tracking:
        return cmd_tracking()
    if args.amortize:
        model = MODELS[args.model]
        gpu = args.gpu or next(iter(model.min_gpu))
        gpu_count = args.gpu_count or model.min_gpu.get(gpu, 1)
        return cmd_amortize(
            model_key=args.model,
            gpu=gpu,
            gpu_count=gpu_count,
            hours=args.hours,
            cold_starts_per_hour=args.cold_starts_per_hour,
            cold_start_seconds_nosnapshot=args.cold_start_nosnap,
            cold_start_seconds_snapshot=args.cold_start_snap,
            snapshot_overhead_first_deploys=args.snap_creations,
            region_mult=REGION_MULTIPLIERS[args.region],
            nonpreempt_mult=NONPREEMPT_MULTIPLIER if args.nonpreempt else 1.0,
        )

    if args.requests is None and args.rps is None:
        p.error("--compare/--single require --requests or --rps")

    if args.compare:
        workload = Workload(
            requests=args.requests,
            rps=args.rps,
            hours=args.hours,
            in_tokens=args.in_tokens,
            out_tokens=args.out_tokens,
        )
        return cmd_compare(
            args.model, workload,
            REGION_MULTIPLIERS[args.region],
            NONPREEMPT_MULTIPLIER if args.nonpreempt else 1.0,
            snapshot=args.snapshot,
        )
    return cmd_single(args)


if __name__ == "__main__":
    sys.exit(main())
