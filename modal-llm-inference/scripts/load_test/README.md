# Load testing with locust on Modal

Real load-testing pattern, mirrored from [Modal's canonical OpenAI-compatible
load test](https://github.com/modal-labs/modal-examples/tree/main/06_gpu_and_ml/llm-serving/openai_compatible).

## Files

- `locustfile.py` — defines what each simulated user does (POSTs chat completions)
- `load_test.py` — Modal driver that runs locust against your deployed endpoint

## Usage

```bash
# Point at your deployed server
export TARGET_HOST=https://<workspace>--gemma-4-vllm-server-serve.modal.run

# Headless run: 36 users, ramping at 1/sec, for 2 minutes
modal run scripts/load_test/load_test.py --r 1 --u 36 --t 2m

# Stress test
modal run scripts/load_test/load_test.py --r 5 --u 200 --t 10m

# Interactive UI — Modal prints a URL for the locust web dashboard
modal serve scripts/load_test/load_test.py
```

Results land in a Modal Volume named `loadtest-results` as timestamped
subdirectories containing `stats.csv` + `report.html`. Fetch locally with:

```bash
modal volume get loadtest-results <timestamp-directory>
```

## Tuning notes

- `wait_time` in `locustfile.py` controls per-user think-time. `between(1, 5)` simulates
  conversational pacing; `between(0, 0.1)` is pure stress.
- Workers (CPU processes on the Modal side) is set to 8. Bump for higher RPS ceilings.
- Measure TTFT and total tokens/sec — these are in the CSV, not just the HTML.
- For throughput benchmarking specifically, also look at Modal's `vllm_throughput.py`
  example which uses the offline `LLM` interface instead of HTTP (different workload shape).
