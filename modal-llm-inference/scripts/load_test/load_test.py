"""
load_test.py — Run locust on Modal to load-test a deployed vLLM endpoint.

Adapted from modal-examples/06_gpu_and_ml/llm-serving/openai_compatible/load_test.py

Two usage modes:

1) Headless run (CI / automated benchmark):
       modal run scripts/load_test/load_test.py --r 1 --u 36 --t 2m
   Spawns 36 users at 1/sec, runs for 2 minutes, writes CSV + HTML report
   to a Modal Volume named "loadtest-results".

2) Interactive UI:
       modal serve scripts/load_test/load_test.py
   Gets you the locust web UI at a public URL so you can tune live.

Edit TARGET_HOST below to point at YOUR deployed endpoint.
"""

import os
from datetime import datetime, timezone
from pathlib import Path, PosixPath

import modal


# ----- Target: which endpoint to load-test -----
# Edit this to match the URL Modal printed after your `modal deploy` of the server.
# Example: "https://my-workspace--gemma-4-vllm-server-serve.modal.run"
TARGET_HOST = os.environ.get(
    "TARGET_HOST",
    "https://<your-workspace>--gemma-4-vllm-server-serve.modal.run",
)

# Auth header value for the deployed endpoint, if you secured it.
# "Bearer dummy" is the default that works with an unsecured vLLM deployment.
TARGET_AUTH = os.environ.get("TARGET_AUTH", "Bearer dummy")

# Which served-model-name to request. Matches --served-model-name on the server.
TARGET_MODEL = os.environ.get("TARGET_MODEL", "llm")


# ----- Workspace / environment (so this works in any Modal workspace) -----
if modal.is_local():
    workspace = modal.config._profile
    environment = modal.config.config.get("environment") or ""
else:
    workspace = os.environ["MODAL_WORKSPACE"]
    environment = os.environ["MODAL_ENVIRONMENT"]


# ----- Image: locust + openai, with the locustfile mounted at runtime -----
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("locust~=2.36.2", "openai~=1.37.1")
    .env({
        "MODAL_WORKSPACE": workspace,
        "MODAL_ENVIRONMENT": environment,
        "LOADTEST_MODEL": TARGET_MODEL,
        "LOADTEST_AUTH": TARGET_AUTH,
    })
    .add_local_file(
        Path(__file__).parent / "locustfile.py",
        remote_path="/root/locustfile.py",
    )
)


# ----- Persistent storage for results -----
volume = modal.Volume.from_name("loadtest-results", create_if_missing=True)
RESULTS_PATH = Path("/root") / "loadtests"
OUT_DIRECTORY = RESULTS_PATH / datetime.now(timezone.utc).replace(microsecond=0).isoformat()


app = modal.App("loadtest-vllm", image=image, volumes={RESULTS_PATH: volume})

MINUTES = 60
WORKERS = 8  # locust worker processes


# Common locust args — -H sets the base URL all requests go to.
base_args = [
    "-H", TARGET_HOST,
    "--processes", str(WORKERS),
    "--csv", str(OUT_DIRECTORY / "stats"),
]


@app.function(cpu=WORKERS, timeout=60 * MINUTES)
def run_locust(args: list, wait: bool = False) -> int | None:
    """Run locust as a subprocess. Called by both interactive and headless modes."""
    import subprocess

    process = subprocess.Popen(["locust"] + args)
    if wait:
        process.wait()
        return process.returncode
    return None


@app.function(cpu=WORKERS)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=8089)
def serve():
    """Interactive locust web UI. Run with `modal serve load_test.py`.
    Modal will print a URL; open it in a browser to start/stop tests live."""
    run_locust.local(base_args)


@app.local_entrypoint()
def main(r: float = 1.0, u: int = 36, t: str = "1m"):
    """Headless run: spawn `u` users at `r`/sec, run for `t` (e.g. '1m', '30s', '1h').

    Examples:
        modal run load_test.py                      # defaults: 36 users over 1min
        modal run load_test.py --r 2 --u 100 --t 5m # stress test: 100 users, 5 min
        modal run load_test.py --r 0.5 --u 10 --t 30s # gentle baseline
    """
    if "<your-workspace>" in TARGET_HOST:
        raise SystemExit(
            "Edit TARGET_HOST at the top of this file (or set env var TARGET_HOST) "
            "to point at your deployed endpoint before running the load test."
        )

    args = base_args + [
        "--spawn-rate", str(r),
        "--users", str(u),
        "--run-time", t,
        "--headless",
        "--autostart",
        "--autoquit", "10",  # wait 10s after completion before exiting
        "--html", str(PosixPath(OUT_DIRECTORY / "report.html")),
    ]

    exit_code = run_locust.remote(args, wait=True)
    if exit_code:
        raise SystemExit(exit_code)

    print(f"\nResults saved to Modal Volume 'loadtest-results' at: {OUT_DIRECTORY}")
    print("Fetch them with:")
    print(f"  modal volume get loadtest-results {OUT_DIRECTORY}")
