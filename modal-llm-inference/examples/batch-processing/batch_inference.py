"""
Batch processing client for vLLM inference
File: examples/batch-processing/batch_inference.py

Usage:
    modal run examples/batch-processing/batch_inference.py --prompts "prompt1|prompt2|prompt3"
"""

import os
import time
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL_ID = "google/gemma-4-26B-A4B-it"


@dataclass
class BatchResult:
    """Result of batch inference."""
    prompt: str
    response: str
    latency_ms: float
    tokens: int
    success: bool
    error: Optional[str] = None


class BatchVLLMClient:
    """Batch processing client for vLLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        max_workers: int = 10,
    ):
        self.base_url = base_url
        self.client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", "dummy"),
            base_url=base_url,
        )
        self.model = MODEL_ID
        self.max_workers = max_workers

    def process_single(
        self,
        prompt: str,
        max_tokens: int = 512,
    ) -> BatchResult:
        """Process single prompt with timing."""

        start = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )

            latency_ms = (time.time() - start) * 1000
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens

            return BatchResult(
                prompt=prompt,
                response=content,
                latency_ms=latency_ms,
                tokens=tokens,
                success=True,
            )

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return BatchResult(
                prompt=prompt,
                response="",
                latency_ms=latency_ms,
                tokens=0,
                success=False,
                error=str(e),
            )

    def process_batch(
        self,
        prompts: list[str],
        max_tokens: int = 512,
        show_progress: bool = True,
    ) -> list[BatchResult]:
        """Process batch of prompts in parallel."""

        results = []
        total = len(prompts)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_single, p, max_tokens): p
                for p in prompts
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1

                if show_progress:
                    progress = completed * 100 // total
                    print(
                        f"\rProgress: {completed}/{total} ({progress}%)",
                        end="",
                        flush=True,
                    )

                result = future.result()
                results.append(result)

        if show_progress:
            print()

        return results

    def print_summary(self, results: list[BatchResult]):
        """Print batch processing summary."""

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        total_tokens = sum(r.tokens for r in successful)
        total_latency = sum(r.latency_ms for r in successful)
        avg_latency = total_latency / len(successful) if successful else 0

        print("\n" + "=" * 60)
        print("Batch Processing Summary")
        print("=" * 60)
        print(f"Total prompts: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Total tokens: {total_tokens:,}")
        print(f"Average latency: {avg_latency:.2f}ms")
        print(f"Total processing time: {total_latency:.2f}ms")

        if total_latency > 0:
            tokens_per_second = (total_tokens / total_latency) * 1000
            print(f"Throughput: {tokens_per_second:.2f} tokens/sec")

        # Cost estimation (H200)
        h200_rate_per_hour = 3.50
        gpu_hours = total_latency / 3600000
        estimated_cost = gpu_hours * h200_rate_per_hour

        if total_tokens > 0:
            cost_per_million = (estimated_cost / total_tokens) * 1_000_000
            print(f"\nEstimated cost (H200): ${estimated_cost:.6f}")
            print(f"Cost per million tokens: ${cost_per_million:.4f}")

        print("=" * 60)

        # Print failed requests
        if failed:
            print("\nFailed requests:")
            for r in failed[:5]:
                print(f"  - {r.prompt[:50]}... : {r.error}")
            if len(failed) > 5:
                print(f"  ... and {len(failed) - 5} more")


def generate_test_prompts(count: int = 100) -> list[str]:
    """Generate test prompts for benchmarking."""

    topics = [
        "machine learning", "quantum computing", "blockchain",
        "neural networks", "deep learning", "artificial intelligence",
        "natural language processing", "computer vision",
    ]

    question_types = [
        "Explain the concept of",
        "What are the benefits of",
        "How does",
        "Compare and contrast",
        "Describe the history of",
    ]

    prompts = []
    for i in range(count):
        topic = topics[i % len(topics)]
        question = question_types[i % len(question_types)]
        prompts.append(f"{question} {topic} in simple terms.")

    return prompts


@app.function(
    timeout=1800,
)
def run_batch_inference(
    prompts: list[str],
    base_url: str = "http://localhost:8000/v1",
):
    """Run batch inference via Modal."""

    client = BatchVLLMClient(base_url=base_url, max_workers=10)
    results = client.process_batch(prompts)
    client.print_summary(results)

    return {
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }


@app.local_entrypoint()
def main():
    """Local entry point for batch processing."""

    import argparse

    parser = argparse.ArgumentParser(description="Batch vLLM inference")
    parser.add_argument(
        "--prompts",
        type=str,
        help="Pipe-separated prompts (or use --generate for test data)",
    )
    parser.add_argument(
        "--generate",
        type=int,
        default=0,
        help="Generate N test prompts",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/v1",
        help="vLLM API base URL",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers",
    )

    args = parser.parse_args()

    # Get prompts
    if args.generate > 0:
        prompts = generate_test_prompts(args.generate)
        print(f"Generated {len(prompts)} test prompts")
    elif args.prompts:
        prompts = args.prompts.split("|")
        print(f"Processing {len(prompts)} prompts")
    else:
        print("No prompts provided. Use --prompts or --generate")
        return

    # Run batch processing
    client = BatchVLLMClient(base_url=args.url, max_workers=args.workers)
    results = client.process_batch(prompts)
    client.print_summary(results)

    # Save results to file
    output_file = "batch_results.json"
    import json

    with open(output_file, "w") as f:
        json.dump([
            {
                "prompt": r.prompt,
                "response": r.response,
                "latency_ms": r.latency_ms,
                "tokens": r.tokens,
                "success": r.success,
            }
            for r in results
        ], f, indent=2)

    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
