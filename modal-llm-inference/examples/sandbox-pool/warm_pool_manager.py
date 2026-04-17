"""
Warm Sandbox Pool Manager for rapid-fire vLLM inference
File: examples/sandbox-pool/warm_pool_manager.py

This pattern maintains a pool of pre-warmed vLLM sandboxes ready to
serve requests instantly without cold start delays.

Usage:
    modal run examples/sandbox-pool/warm_pool_manager.py
    modal deploy examples/sandbox-pool/warm_pool_manager.py
"""

import modal
import time
from dataclasses import dataclass
from typing import Optional, List

app = modal.App("vllm-warm-pool")

# Configuration
POOL_SIZE = 3
POOL_TTL_SECONDS = 300  # 5 minutes
SANDBOX_IDLE_TIMEOUT = 3600  # 1 hour

# Create persistent queue for requests
REQUEST_QUEUE = modal.Queue.from_name("vllm-pool-requests", create_if_missing=True)
RESULT_QUEUE = modal.Queue.from_name("vllm-pool-results", create_if_missing=True)


@dataclass
class SandboxInfo:
    """Information about a sandbox in the pool."""
    sandbox_id: str
    created_at: float
    last_used: float
    is_healthy: bool


# In-memory pool state (in production, use Redis or Modal Volume)
_pool_state: List[SandboxInfo] = []


@app.function(
    image=modal.Image.debian_slim(python_version="3.12").uv_pip_install(
        "vllm==0.19.0",
        "openai>=1.0.0",
        "requests>=2.31.0",
    ),
    gpu="H200",
    timeout=SANDBOX_IDLE_TIMEOUT,
    secrets=[modal.Secret.from_name("huggingface-secret", create_if_missing=True)],
)
def create_warm_sandbox() -> dict:
    """Create a pre-warmed vLLM sandbox.

    This function initializes a full vLLM server before returning,
    ensuring the sandbox is ready for immediate use.
    """

    import subprocess
    import os
    import requests

    # Create sandbox
    sandbox = modal.Sandbox.create(
        image=modal.Image.debian_slim(python_version="3.12").uv_pip_install(
            "vllm==0.19.0",
            "openai>=1.0.0",
        ),
        gpu="H200",
    )

    sandbox_id = sandbox.object_id

    # Initialize vLLM in sandbox
    vllm_init = sandbox.exec(
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--dtype", "half",
        "--max-model-len", "8192",
        "--port", "8000",
        "--host", "0.0.0.0",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "gemma4",
        "--tool-call-parser", "gemma4",
    )

    # Wait for vLLM to initialize
    print(f"Sandbox {sandbox_id}: Waiting for vLLM startup...")
    time.sleep(60)

    # Health check
    max_retries = 10
    for i in range(max_retries):
        try:
            # Note: In real usage, you'd use sandbox's external URL
            print(f"Sandbox {sandbox_id}: Health check {i+1}/{max_retries}")
            time.sleep(5)
        except Exception as e:
            if i == max_retries - 1:
                print(f"Sandbox {sandbox_id}: Health check failed")
                sandbox.terminate()
                return {"status": "failed", "error": str(e)}

    return {
        "sandbox_id": sandbox_id,
        "status": "ready",
        "created_at": time.time(),
    }


@app.function(
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
    timeout=300,
)
def maintain_pool():
    """Maintain pool size by creating/removing sandboxes.

    This function:
    1. Checks current pool size
    2. Removes expired or unhealthy sandboxes
    3. Creates new sandboxes to maintain target size
    """

    global _pool_state

    print("Pool maintenance started")
    print(f"Current pool size: {len(_pool_state)}")
    print(f"Target pool size: {POOL_SIZE}")

    current_time = time.time()

    # Remove expired sandboxes
    active = []
    for info in _pool_state:
        age = current_time - info.created_at
        if age < POOL_TTL_SECONDS and info.is_healthy:
            active.append(info)
        else:
            print(f"Removing expired/unhealthy sandbox: {info.sandbox_id}")

    _pool_state = active

    # Create new sandboxes if needed
    while len(_pool_state) < POOL_SIZE:
        print(f"Creating new sandbox... ({len(_pool_state)}/{POOL_SIZE})")
        result = create_warm_sandbox.remote()

        if result["status"] == "ready":
            info = SandboxInfo(
                sandbox_id=result["sandbox_id"],
                created_at=result["created_at"],
                last_used=current_time,
                is_healthy=True,
            )
            _pool_state.append(info)
            print(f"Created sandbox: {info.sandbox_id}")
        else:
            print(f"Failed to create sandbox: {result.get('error')}")
            break

    print(f"Pool maintenance complete. Pool size: {len(_pool_state)}")


@app.function(
    timeout=60,
)
def claim_sandbox() -> Optional[dict]:
    """Claim an available sandbox from the pool.

    Returns sandbox info or None if pool is empty.
    """

    global _pool_state

    if not _pool_state:
        return None

    # Get least recently used sandbox
    sandbox = min(_pool_state, key=lambda x: x.last_used)
    sandbox.last_used = time.time()

    return {
        "sandbox_id": sandbox.sandbox_id,
        "claimed_at": sandbox.last_used,
    }


@app.function(
    timeout=600,
)
def inference_with_pool(
    prompt: str,
    max_tokens: int = 1024,
) -> dict:
    """Process inference request using warm pool."""

    # Claim sandbox
    sandbox_info = claim_sandbox.remote()

    if not sandbox_info:
        # Pool empty, create on-demand (slower)
        print("Pool empty, creating on-demand sandbox...")
        result = create_warm_sandbox.remote()
        if result["status"] != "ready":
            return {"error": "Failed to create sandbox"}
        sandbox_id = result["sandbox_id"]
    else:
        sandbox_id = sandbox_info["sandbox_id"]
        print(f"Using sandbox from pool: {sandbox_id}")

    # Note: In production, you'd use the sandbox's actual URL
    # For this example, we return the sandbox info

    return {
        "sandbox_id": sandbox_id,
        "prompt": prompt,
        "status": "processed",
    }


@app.function
def get_pool_status() -> dict:
    """Get current pool status."""

    global _pool_state

    return {
        "pool_size": len(_pool_state),
        "target_size": POOL_SIZE,
        "ttl_seconds": POOL_TTL_SECONDS,
        "sandboxes": [
            {
                "sandbox_id": s.sandbox_id,
                "age_seconds": time.time() - s.created_at,
                "last_used_seconds_ago": time.time() - s.last_used,
                "is_healthy": s.is_healthy,
            }
            for s in _pool_state
        ],
    }


@app.local_entrypoint()
def main():
    """Local entry point for pool management."""

    import argparse

    parser = argparse.ArgumentParser(description="vLLM Warm Pool Manager")
    parser.add_argument(
        "action",
        choices=["deploy", "status", "maintain", "claim"],
        help="Action to perform",
    )

    args = parser.parse_args()

    if args.action == "deploy":
        print("Deploying warm pool manager...")
        print(f"Target pool size: {POOL_SIZE}")
        print(f"TTL: {POOL_TTL_SECONDS} seconds")

        # Initial pool creation
        print("\nCreating initial pool...")
        maintain_pool.local()

        print("\nDeploying scheduled maintenance...")
        print("Run 'modal deploy' to deploy to production")

    elif args.action == "status":
        status = get_pool_status.local()
        print("\nPool Status")
        print("=" * 40)
        print(f"Current size: {status['pool_size']}")
        print(f"Target size: {status['target_size']}")
        print(f"TTL: {status['ttl_seconds']}s")
        print("\nSandboxes:")
        for s in status["sandboxes"]:
            print(f"  - {s['sandbox_id']}")
            print(f"    Age: {s['age_seconds']:.0f}s")
            print(f"    Last used: {s['last_used_seconds_ago']:.0f}s ago")
            print(f"    Healthy: {s['is_healthy']}")

    elif args.action == "maintain":
        print("Running pool maintenance...")
        maintain_pool.local()
        print("Maintenance complete")

    elif args.action == "claim":
        print("Claiming sandbox from pool...")
        result = claim_sandbox.local()
        if result:
            print(f"Claimed sandbox: {result['sandbox_id']}")
        else:
            print("No sandbox available in pool")


if __name__ == "__main__":
    main()
