<!--
CANONICAL SOURCES — when in doubt, prefer these over the snippets below:
  • Runnable servers:  examples/basic-deployment/*.py       (tested, current APIs)
  • API gotchas:       references/modal-api-notes.md        (URL retrieval, auth, snapshots)
  • Verification:      docs/00-verification-playbook.md     (how to check if anything here is stale)
  • ERRATA:            ERRATA.md                            (known discrepancies awaiting fix)

Snippets here illustrate patterns. Real deployable code lives in examples/.
-->

# Client Integration

## Purpose

Client-side integration patterns for Python, JavaScript, and terminal-based applications with streaming and batch processing support.

## Table of Contents

1. [Python Client](#python-client)
2. [JavaScript/TypeScript Client](#javascripttypescript-client)
3. [Streaming Responses](#streaming-responses)
4. [Batch Processing Client](#batch-processing-client)
5. [Error Handling](#error-handling)

## Python Client

### Basic OpenAI-Compatible Client

```python
"""
Python client for Modal vLLM inference
File: examples/client/python_client.py
"""

from openai import OpenAI
from typing import Optional

class VLLMClient:
    """OpenAI-compatible client for Modal vLLM server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "dummy",
        model: str = "google/gemma-4-26B-A4B-it",
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """Generate completion for prompt."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        return response.choices[0].message.content

    def complete_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ):
        """Generate completion with streaming."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Usage example
if __name__ == "__main__":
    client = VLLMClient(
        base_url="https://your-app.modal.run/v1",
        model="google/gemma-4-26B-A4B-it",
    )

    response = client.complete(
        prompt="Explain quantum entanglement",
        system_prompt="You are a physics expert.",
    )
    print(response)
```

### Async Client

```python
"""
Async Python client for Modal vLLM
File: examples/client/async_client.py
"""

import asyncio
from openai import AsyncOpenAI
from typing import Optional, AsyncIterator

class AsyncVLLMClient:
    """Async client for Modal vLLM server."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "dummy",
        model: str = "google/gemma-4-26B-A4B-it",
    ):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate completion asynchronously."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    async def complete_many(
        self,
        prompts: list[str],
        max_tokens: int = 512,
    ) -> list[str]:
        """Process multiple prompts concurrently."""

        tasks = [
            self.complete(prompt, max_tokens=max_tokens)
            for prompt in prompts
        ]

        return await asyncio.gather(*tasks)

    async def stream_complete(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Stream completion tokens."""

        messages = [{"role": "user", "content": prompt}]

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Usage
async def main():
    client = AsyncVLLMClient(
        base_url="https://your-app.modal.run/v1",
    )

    # Single request
    response = await client.complete("Hello, world!")
    print(response)

    # Batch requests
    responses = await client.complete_many([
        "What is AI?",
        "What is ML?",
        "What is DL?",
    ])

    # Streaming
    async for token in client.stream_complete("Tell me a story"):
        print(token, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

## JavaScript/TypeScript Client

### JavaScript Client

```javascript
/**
 * JavaScript client for Modal vLLM inference
 * File: examples/client/vllm_client.js
 */

class VLLMClient {
  constructor(options = {}) {
    this.baseURL = options.baseURL || "http://localhost:8000/v1";
    this.apiKey = options.apiKey || "dummy";
    this.model = options.model || "google/gemma-4-26B-A4B-it";
  }

  async complete(prompt, options = {}) {
    const {
      systemPrompt = null,
      maxTokens = 1024,
      temperature = 0.7,
    } = options;

    const messages = [];
    if (systemPrompt) {
      messages.push({ role: "system", content: systemPrompt });
    }
    messages.push({ role: "user", content: prompt });

    const response = await fetch(`${this.baseURL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_tokens: maxTokens,
        temperature,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  async *streamComplete(prompt, options = {}) {
    const { maxTokens = 1024, temperature = 0.7 } = options;

    const messages = [{ role: "user", content: prompt }];

    const response = await fetch(`${this.baseURL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_tokens: maxTokens,
        temperature,
        stream: true,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            return;
          }
          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content;
            if (content) {
              yield content;
            }
          } catch (e) {
            // Skip invalid JSON
          }
        }
      }
    }
  }

  async completeBatch(prompts, options = {}) {
    return Promise.all(
      prompts.map((prompt) => this.complete(prompt, options))
    );
  }
}

// Usage
const client = new VLLMClient({
  baseURL: "https://your-app.modal.run/v1",
  model: "google/gemma-4-26B-A4B-it",
});

const response = await client.complete("Hello, world!");
console.log(response);

for await (const token of client.streamComplete("Tell me a story")) {
  process.stdout.write(token);
}
```

### TypeScript Client

```typescript
/**
 * TypeScript client for Modal vLLM inference
 * File: examples/client/vllm_client.ts
 */

interface CompletionOptions {
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
}

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface CompletionResponse {
  content: string;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

class VLLMClient {
  private baseURL: string;
  private apiKey: string;
  private model: string;

  constructor(options: {
    baseURL?: string;
    apiKey?: string;
    model?: string;
  } = {}) {
    this.baseURL = options.baseURL || "http://localhost:8000/v1";
    this.apiKey = options.apiKey || "dummy";
    this.model = options.model || "google/gemma-4-26B-A4B-it";
  }

  async complete(
    prompt: string,
    options: CompletionOptions = {}
  ): Promise<CompletionResponse> {
    const {
      systemPrompt = null,
      maxTokens = 1024,
      temperature = 0.7,
    } = options;

    const messages: ChatMessage[] = [];
    if (systemPrompt) {
      messages.push({ role: "system", content: systemPrompt });
    }
    messages.push({ role: "user", content: prompt });

    const response = await fetch(`${this.baseURL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_tokens: maxTokens,
        temperature,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      content: data.choices[0].message.content,
      usage: {
        promptTokens: data.usage.prompt_tokens,
        completionTokens: data.usage.completion_tokens,
        totalTokens: data.usage.total_tokens,
      },
    };
  }

  async *streamComplete(
    prompt: string,
    options: CompletionOptions = {}
  ): AsyncGenerator<string> {
    const { maxTokens = 1024, temperature = 0.7 } = options;

    const messages: ChatMessage[] = [{ role: "user", content: prompt }];

    const response = await fetch(`${this.baseURL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        max_tokens: maxTokens,
        temperature,
        stream: true,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            return;
          }
          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content;
            if (content) {
              yield content;
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  }
}

export { VLLMClient, CompletionOptions, CompletionResponse };
```

## Streaming Responses

### Rich Terminal Display

```python
"""
Streaming client with Rich terminal UI
File: examples/client/streaming_client.py
"""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from openai import OpenAI
import os

console = Console()

class StreamingVLLMClient:
    """Client with streaming response and Rich terminal display."""

    def __init__(self, base_url: str):
        self.client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", "dummy"),
            base_url=base_url,
        )
        self.model = "google/gemma-4-26B-A4B-it"

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        render_markdown: bool = True,
    ):
        """Stream chat with terminal display."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            max_tokens=2048,
        )

        response_text = []

        with Live(console=console, refresh_per_second=10) as live:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    response_text.append(token)

                    if render_markdown:
                        live.update(
                            console.rule("[bold blue]Response[/bold blue]")
                        )
                        live.update(
                            Markdown("".join(response_text))
                        )
                    else:
                        live.update(
                            "".join(response_text) + "▌"
                        )

        return "".join(response_text)


if __name__ == "__main__":
    client = StreamingVLLMClient(
        base_url="https://your-app.modal.run/v1"
    )

    console.print("[bold green]Modal vLLM Streaming Client[/bold green]")
    console.print("-" * 50)

    prompt = console.input("\n[yellow]Enter your question:[/yellow] ")

    result = client.chat_stream(prompt)
    console.print("\n[bold green]Complete![/bold green]")
```

## Batch Processing Client

### Parallel Batch Client

```python
"""
Batch processing client with progress tracking
File: examples/client/batch_client.py
"""

from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class BatchResult:
    """Result of batch inference."""
    prompt: str
    response: str
    latency_ms: float
    tokens: int

class BatchVLLMClient:
    """Batch processing client for vLLM inference."""

    def __init__(
        self,
        base_url: str,
        max_workers: int = 10,
    ):
        self.client = OpenAI(
            api_key="dummy",
            base_url=base_url,
        )
        self.model = "google/gemma-4-26B-A4B-it"
        self.max_workers = max_workers

    def process_single(
        self,
        prompt: str,
        max_tokens: int = 512,
    ) -> BatchResult:
        """Process single prompt."""

        start = time.time()

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
                    print(
                        f"\rProgress: {completed}/{total} "
                        f"({completed*100//total}%)",
                        end="",
                    )

                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    prompt = futures[future]
                    results.append(BatchResult(
                        prompt=prompt,
                        response=f"Error: {e}",
                        latency_ms=0,
                        tokens=0,
                    ))

        if show_progress:
            print()

        return results

    def print_summary(self, results: list[BatchResult]):
        """Print batch processing summary."""

        total_tokens = sum(r.tokens for r in results)
        avg_latency = sum(r.latency_ms for r in results) / len(results)
        total_time = sum(r.latency_ms for r in results)

        print("\n" + "=" * 50)
        print("Batch Processing Summary")
        print("=" * 50)
        print(f"Total prompts: {len(results)}")
        print(f"Total tokens: {total_tokens}")
        print(f"Avg latency: {avg_latency:.2f}ms")
        print(f"Total time: {total_time:.2f}ms")
        print(f"Throughput: {total_tokens * 1000 / total_time:.2f} tokens/sec")
        print("=" * 50)


if __name__ == "__main__":
    client = BatchVLLMClient(
        base_url="https://your-app.modal.run/v1",
        max_workers=10,
    )

    prompts = [f"Explain concept {i}" for i in range(100)]

    results = client.process_batch(prompts)
    client.print_summary(results)
```

## Error Handling

### Retry Logic

```python
"""
Error handling with retry logic
File: examples/client/retry_client.py
"""

from openai import OpenAI, APIError, RateLimitError
from typing import Optional
import time
import random

class RetryVLLMClient:
    """Client with automatic retry and backoff."""

    def __init__(
        self,
        base_url: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        self.client = OpenAI(api_key="dummy", base_url=base_url)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def _calculate_delay(self, attempt: int, exception: Exception) -> float:
        """Calculate exponential backoff delay."""

        if isinstance(exception, RateLimitError):
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay * (2 ** attempt)

        # Add jitter
        delay *= (0.5 + random.random() * 0.5)

        return min(delay, self.max_delay)

    def complete_with_retry(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> str:
        """Complete with automatic retry."""

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model="google/gemma-4-26B-A4B-it",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )

                return response.choices[0].message.content

            except (APIError, RateLimitError) as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, e)
                    print(f"Retry {attempt + 1}/{self.max_retries} "
                          f"after {delay:.1f}s: {e}")
                    time.sleep(delay)
                else:
                    print(f"Max retries ({self.max_retries}) exceeded")

        raise last_exception


if __name__ == "__main__":
    client = RetryVLLMClient(
        base_url="https://your-app.modal.run/v1",
        max_retries=5,
    )

    try:
        result = client.complete_with_retry("Hello, world!")
        print(result)
    except Exception as e:
        print(f"Failed after retries: {e}")
```

## Next Steps

- Study [Cost Management](04-cost-management.md) for cost tracking
- Implement [TUI/Agent Patterns](05-tui-agent-patterns.md) for terminal agents
- Review [Deployment Patterns](02-deployment-patterns.md) for production setup
