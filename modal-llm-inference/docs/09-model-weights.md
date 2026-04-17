# Storing Model Weights — Volume patterns for vLLM

<!--
SOURCE: https://modal.com/docs/guide/model-weights + https://modal.com/docs/guide/volumes
        (fetched 2026-04-16)
Refactored for the HuggingFace → Modal Volume → vLLM pipeline specifically.
-->

**The question this doc answers:** where should model weights live, how do they get there, and why do our examples use two separate Volumes?

## The core recommendation

Store model weights in a **Modal Volume**, not in the container Image. Volumes are distributed file systems — shared disks that every container can read from at high bandwidth. Images can embed weights but become harder to update and force full rebuilds for weight changes.

Our server examples use two Volumes:

```python
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

@app.function(
    ...
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,   # model weights
        "/root/.cache/vllm": vllm_cache_vol,         # JIT artifacts
    },
)
```

**Why two?** Different lifecycle characteristics:

- `huggingface-cache` stores weights. Weights are large (4-200 GB), slow to download, and rarely change (only when you update `MODEL_REVISION`).
- `vllm-cache` stores vLLM's JIT compilation artifacts (CUDA graphs, torch.compile output). Small, regenerated when you change GPU type or vLLM version.

Separating them means you can wipe the JIT cache (e.g. after a vLLM upgrade) without re-downloading weights.

## Three ways weights get into a Volume

### 1. Lazy download on first boot (our default)

vLLM will download from HuggingFace Hub the first time the server starts. The Volume is empty on first deploy; `vllm serve` hits the Hub, writes to `/root/.cache/huggingface`, and subsequent boots read locally.

**Pros:** zero setup, just deploy and go.
**Cons:** first cold start can take 3-10+ minutes for large models. Subsequent cold starts are fast because the Volume is populated.

Add the `huggingface-secret` Modal Secret with your HF token to access gated models:

```bash
modal secret create huggingface-secret HF_TOKEN=hf_xxx
```

Then pass `secrets=[modal.Secret.from_name("huggingface-secret")]` to the function. `scripts/setup_secrets.py` does this for you.

### 2. Download ahead of time inside the Image

You can bake the download into the Image build so it happens at deploy time, not first-request time:

```python
def download_weights():
    from huggingface_hub import snapshot_download
    snapshot_download(
        "google/gemma-4-26B-A4B-it",
        revision="47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301",
        local_dir="/root/.cache/huggingface/hub/",
    )

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .uv_pip_install("vllm==0.19.0", "huggingface-hub")
    .run_function(
        download_weights,
        secrets=[modal.Secret.from_name("huggingface-secret")],
        volumes={"/root/.cache/huggingface": hf_cache_vol},
    )
)
```

**Pros:** first cold start is fast because weights are already in the Volume when your vLLM server starts.
**Cons:** image builds take longer (but Modal caches Image layers, so only the first build is slow).

### 3. Upload weights from your machine

For private models or models you've trained yourself:

```bash
# From a directory on your laptop
modal volume put huggingface-cache ./my-model/ models/my-model
```

Or via the Python client:

```python
import modal
vol = modal.Volume.from_name("huggingface-cache")
vol.batch_upload([("./local-path/model.safetensors", "models/my-model/model.safetensors")])
```

For production, upload from a dedicated training cluster directly into the Volume — this keeps weights out of the HuggingFace Hub round-trip entirely.

## Reading weights in your function

Just read them like normal disk. Volumes mount as regular file systems:

```python
@app.function(volumes={"/root/.cache/huggingface": hf_cache_vol})
def serve():
    # vllm serve automatically reads from HF_HOME which defaults to ~/.cache/huggingface
    subprocess.Popen(["vllm", "serve", "google/gemma-4-26B-A4B-it", ...])
```

No special code — vLLM, huggingface-hub, transformers all respect the standard cache paths.

## Using `@modal.enter` to load weights exactly once

If you're using a `modal.Cls` pattern, put the heavy load inside `@modal.enter`:

```python
@app.cls(gpu="H200", volumes={...})
class Server:
    @modal.enter()
    def load_model(self):
        # Runs once per container start, not per request
        self.proc = subprocess.Popen(["vllm", "serve", MODEL_NAME, ...])
        _wait_ready(self.proc)
```

Our `gemma_snapshot_server.py` and `minimax_server.py` use this pattern. The request handler just forwards HTTP; the expensive startup is isolated in `@modal.enter`.

**Gotcha:** `@modal.enter` methods can't take dynamic arguments. If you need per-container model selection (e.g. one container per model variant), use `modal.parameter` on a parametrized Cls:

```python
@app.cls()
class Server:
    model_name: str = modal.parameter()

    @modal.enter()
    def load(self):
        subprocess.Popen(["vllm", "serve", self.model_name, ...])

# Each .with_parameters() call creates a separate autoscaler pool
Server.with_parameters(model_name="gemma-4-26B-A4B-it")
Server.with_parameters(model_name="gemma-4-31B-it")
```

## Cloud bucket mounts (S3, GCS)

If your weights already live in S3:

```python
@app.function(
    volumes={
        "/mnt/weights": modal.CloudBucketMount(
            "my-s3-bucket",
            secret=modal.Secret.from_name("s3-credentials"),
            read_only=True,
        ),
    },
)
def serve():
    subprocess.Popen(["vllm", "serve", "/mnt/weights/my-model", ...])
```

This avoids duplicating the weights into a Modal Volume. Trade-off: S3 reads can be slower than Modal Volume reads for cold first-access, though Modal caches aggressively.

## Decision tree

```
Where are your model weights?
│
├── On HuggingFace Hub (public or gated)
│   ├── Comfortable with 3-10 min first cold start?
│   │   └── YES → Use our default pattern. Volumes populate on first boot.
│   └── Need faster first cold start?
│       └── Bake snapshot_download into the Image build.
│
├── On S3 / GCS already
│   └── Use CloudBucketMount. Read-only, no duplication.
│
└── Private / trained by you
    └── modal volume put from your training cluster or laptop.
```

## References for the next agent

- Upstream guide: https://modal.com/docs/guide/model-weights
- Volume reference: https://modal.com/docs/guide/volumes
- Cloud bucket mounts: https://modal.com/docs/guide/cloud-bucket-mounts
- Parametrized functions: https://modal.com/docs/guide/parametrized-functions
- Our runnable examples all demonstrate option 1 (lazy download); `scripts/setup_secrets.py` sets up the HF token
