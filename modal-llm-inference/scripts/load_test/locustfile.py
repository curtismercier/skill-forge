"""
Locust workload definition for load-testing a deployed vLLM endpoint.

Adapted from modal-examples/06_gpu_and_ml/llm-serving/openai_compatible/locustfile.py

Edit the MODEL_NAME, MESSAGES, and HEADERS constants below to match your deployment.
Edit WebsiteUser.wait_time to change traffic pattern (e.g. think-time between requests).
"""

import logging
import os
import random

import locust


# ----- Configure these to match your deployment -----
MODEL_NAME = os.environ.get("LOADTEST_MODEL", "llm")  # the --served-model-name alias
AUTH_HEADER = os.environ.get("LOADTEST_AUTH", "Bearer dummy")

MESSAGES = [
    {"role": "system", "content": "You are a terse, precise assistant."},
    {"role": "user",   "content": "Give me two short tips for writing idiomatic Rust."},
]


class WebsiteUser(locust.HttpUser):
    """Simulated user. wait_time controls think-time between requests per user."""

    # Each user waits 1-5s between requests — simulates conversational pacing.
    # For throughput benchmarks, drop to between(0.1, 0.5). For stress, between(0, 0.1).
    wait_time = locust.between(1, 5)

    headers = {
        "Authorization": AUTH_HEADER,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    @locust.task
    def chat_completion(self):
        payload = {
            "model": MODEL_NAME,
            "messages": MESSAGES,
            "max_tokens": 128,
        }

        response = self.client.request(
            "POST", "/v1/chat/completions", json=payload, headers=self.headers,
        )
        response.raise_for_status()

        # Occasionally log a completion so you can eyeball output quality during load.
        if random.random() < 0.01:
            try:
                logging.info(response.json()["choices"][0]["message"]["content"])
            except (KeyError, IndexError):
                pass
