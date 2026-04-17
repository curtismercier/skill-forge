# Modal vLLM LLM Inference Skill

A comprehensive skill for deploying and running OpenAI-compatible LLM inference on Modal.com using vLLM framework.

## Overview

This skill provides the foundation for rapidly deploying and creating terminal-based agents and models on Modal's vLLM infrastructure. It covers Gemma 4 and MiniMax 2.7 models with comprehensive cost management and optimization strategies.

## Features

- **OpenAI-Compatible API**: Seamless integration with existing OpenAI clients
- **Volume Caching**: 10-second cold starts with cached model weights
- **Cost Optimization**: Per-second billing with throughput optimization
- **Multi-Model Support**: Gemma 4, MiniMax 2.7, and custom models
- **TUI/Agent Ready**: OpenCode integration and custom TUI support
- **Scalable Infrastructure**: Auto-scaling with queue-based request management

## Quick Start

```bash
# Install Modal SDK
pip install modal

# Authenticate
modal token new

# Set up secrets
python scripts/setup_secrets.py

# Run basic deployment
modal run examples/basic-deployment/gemma_server.py
```

## Documentation Structure

```
modal-llm-inference/
├── SKILL.md                    # Main entry point
├── docs/
│   ├── 01-foundation.md       # Core concepts and architecture
│   ├── 02-deployment-patterns.md  # Advanced deployment
│   ├── 03-client-integration.md   # Client SDK integration
│   ├── 04-cost-management.md     # Cost optimization
│   └── 05-tui-agent-patterns.md  # Terminal agents
├── examples/
│   ├── basic-deployment/       # Basic server examples
│   ├── tui-agent/             # Terminal UI examples
│   ├── batch-processing/      # Batch processing examples
│   └── sandbox-pool/          # Warm pool examples
├── configs/                    # Configuration templates
└── scripts/                   # Utility scripts
```

## Target Models

| Model | Parameters | Use Case |
|-------|------------|----------|
| Gemma 4 26B-A4B-it | 26B total / 4B active (MoE) | Reasoning, coding, multimodal |
| MiniMax-M2.7 | 229B total / 10B active (MoE) | Agentic coding, long-horizon tasks |

## GPU Requirements

| GPU | VRAM | Gemma 4 26B-A4B | MiniMax-M2.7 (FP8) |
|-----|------|-----------------|---------------------|
| H200 | 141 GB | Single GPU — optimal | Need 2× |
| H100 | 80 GB | Tight (FP8/AWQ) | Need 4× |
| B200 | 192 GB | Single GPU — fastest | 2× for comfort |
| A100-80GB | 80 GB | Quantized only | Not viable |
| A100-40GB | 40 GB | Not viable | Not viable |
| L40S | 48 GB | Not viable | Not viable |

## Cost Management

Estimate costs before deployment:

```bash
# Compare GPU options
python scripts/estimate_cost.py --requests 1000 --gpu all

# Single GPU estimate
python scripts/estimate_cost.py --requests 1000 --gpu H200
```

## Examples

### Basic Deployment

```bash
# Gemma 4 server (single H200)
modal deploy examples/basic-deployment/gemma_server.py

# MiniMax-M2.7 server (2×H200 with tensor parallelism)
modal deploy examples/basic-deployment/minimax_server.py
```

### Interactive TUI

```bash
# Start server first
modal run examples/basic-deployment/gemma_server.py

# Run TUI client
python examples/tui-agent/custom_tui_client.py
```

### Batch Processing

```bash
# Generate test prompts
python examples/batch-processing/batch_inference.py --generate 100

# Process custom prompts
python examples/batch-processing/batch_inference.py --prompts "prompt1|prompt2|prompt3"
```

### Benchmarking

```bash
# Run local benchmark
python scripts/benchmark_throughput.py --url http://localhost:8000/v1

# Run on Modal
python scripts/benchmark_throughput.py --remote
```

## Progressive Learning Path

1. **Foundation**: Start with `docs/01-foundation.md`
2. **Deployment**: Review `docs/02-deployment-patterns.md`
3. **Clients**: Study `docs/03-client-integration.md`
4. **Costs**: Explore `docs/04-cost-management.md`
5. **Agents**: Implement `docs/05-tui-agent-patterns.md`

## Requirements

- Modal account with GPU quota
- HuggingFace account with model access
- Python 3.10+
- Modal SDK installed

## License

MIT — see LICENSE file if present.
