<!--
CANONICAL SOURCES — when in doubt, prefer these over the snippets below:
  • Runnable servers:  examples/basic-deployment/*.py       (tested, current APIs)
  • API gotchas:       references/modal-api-notes.md        (URL retrieval, auth, snapshots)
  • Verification:      docs/00-verification-playbook.md     (how to check if anything here is stale)
  • ERRATA:            ERRATA.md                            (known discrepancies awaiting fix)

Snippets here illustrate patterns. Real deployable code lives in examples/.
-->

# TUI/Agent Patterns

## Purpose

Terminal-based agent deployment using OpenCode patterns and custom TUI interfaces for interactive inference sessions on Modal vLLM infrastructure.

## Table of Contents

1. [OpenCode Server Pattern](#opencode-server-pattern)
2. [Custom TUI Implementation](#custom-tui-implementation)
3. [Interactive Agent Loop](#interactive-agent-loop)
4. [Multi-Model Agent](#multi-model-agent)
5. [Sandbox Integration](#sandbox-integration)

## OpenCode Server Pattern

OpenCode provides a powerful terminal-based coding agent that can be deployed on Modal with vLLM as the inference backend.

### OpenCode Server Deployment

```python
"""
OpenCode server with vLLM backend
File: examples/tui-agent/opencode_server.py
"""

import modal
import os

app = modal.App("opencode-vllm-agent")

# Image with OpenCode and vLLM client dependencies
agent_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.19.0",
        "openai>=1.0.0",
        "rich>=13.0.0",
        "prompt-toolkit>=3.0.0",
        "httpx>=0.25.0",
    )
    .run_commands([
        "git clone https://github.com/opencodeai/opencode.git /app/opencode"
    ])
)

@app.function(
    image=agent_image,
    gpu="H200",
    timeout=3600,
    scaledown_window=600,
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("opencode-auth"),
    ],
)
def opencode_agent_server():
    """Start OpenCode server with vLLM backend.

    This enables terminal-based agent interaction via:
    - Web UI (browser access)
    - TUI (terminal access)
    - Direct API (programmatic access)
    """

    import subprocess
    import os

    # Configure environment
    vllm_endpoint = os.environ.get("VLLM_ENDPOINT", "http://localhost:8000/v1")
    hf_token = os.environ.get("HF_TOKEN", "")

    env = {
        **os.environ,
        "OPENAI_API_BASE": vllm_endpoint,
        "OPENAI_API_KEY": hf_token,
        "OPENCODE_PORT": "8080",
        "OPENCODE_PASSWORD": os.environ.get("OPENCODE_SERVER_PASSWORD", ""),
    }

    # Clone OpenCode if not in image
    if not os.path.exists("/app/opencode"):
        subprocess.run([
            "git", "clone",
            "https://github.com/opencodeai/opencode.git",
            "/app/opencode"
        ], check=True)

    # Start OpenCode in server mode
    subprocess.Popen(
        ["opencode", "api", "--port", "8080"],
        cwd="/app/opencode",
        env=env,
    )

    return {
        "status": "ready",
        "endpoint": f"{vllm_endpoint}/chat/completions",
        "opencode_ui": "http://localhost:8080",
    }


@app.local_entrypoint()
def main():
    """Deploy OpenCode server."""
    result = opencode_agent_server.remote()
    print("OpenCode Server deployed!")
    print(f"vLLM Endpoint: {result['endpoint']}")
    print(f"OpenCode UI: {result['opencode_ui']}")
```

### OpenCode with Custom Backend

```python
"""
OpenCode with custom vLLM configuration
File: examples/tui-agent/opencode_custom.py
"""

import modal

app = modal.App("opencode-custom-vllm")

agent_image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.19.0", "openai", "rich")
)

@app.function(
    image=agent_image,
    gpu="H200",
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def vllm_with_opencode():
    """Combined vLLM + OpenCode server."""

    import subprocess
    import time
    import os

    # Start vLLM first
    vllm_process = subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--dtype", "half",
        "--max-model-len", "8192",
        "--port", "8000",
    ])

    # Wait for vLLM to initialize
    time.sleep(60)

    # Configure OpenCode environment
    env = {
        **os.environ,
        "OPENAI_API_BASE": "http://localhost:8000/v1",
        "OPENAI_API_KEY": os.environ.get("HF_TOKEN", "dummy"),
        "OPENCODE_PORT": "8080",
    }

    # Start OpenCode
    subprocess.Popen(
        ["opencode", "api", "--port", "8080"],
        env=env,
    )

    return {
        "vllm_pid": vllm_process.pid,
        "status": "running",
    }
```

## Custom TUI Implementation

### Interactive Chat TUI

```python
"""
Custom terminal UI for vLLM inference
File: examples/tui-agent/custom_tui_client.py
"""

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.live import Live
import os
import sys

console = Console()

class VLLMTUI:
    """Terminal UI for interactive vLLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "google/gemma-4-26B-A4B-it",
    ):
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", "dummy"),
            base_url=base_url,
        )
        self.conversation = []

    def add_system_prompt(self, prompt: str):
        """Add system prompt to conversation."""
        self.conversation.append({
            "role": "system",
            "content": prompt,
        })

    def stream_response(self, user_input: str) -> str:
        """Stream response to terminal."""

        # Add user message
        self.conversation.append({
            "role": "user",
            "content": user_input,
        })

        # Create streaming completion
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self.conversation,
            stream=True,
            max_tokens=2048,
            temperature=0.7,
        )

        # Stream response
        response_content = []
        with Live(
            console=console,
            refresh_per_second=10,
            transient=False,
        ) as live:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    response_content.append(token)
                    live.update(
                        Panel(
                            Markdown("".join(response_content)),
                            title="Response",
                            border_style="green",
                        )
                    )

        response_text = "".join(response_content)

        # Add assistant response to conversation
        self.conversation.append({
            "role": "assistant",
            "content": response_text,
        })

        return response_text

    def run(self):
        """Main TUI loop."""

        # Header
        console.print(Panel.fit(
            "[bold cyan]Modal vLLM Interactive TUI[/bold cyan]\n"
            "Powered by Gemma 4 / MiniMax 2.7",
            border_style="cyan",
        ))

        # Setup system prompt
        default_system = "You are a helpful, knowledgeable AI assistant."
        system_prompt = Prompt.ask(
            "[yellow]System Prompt[/yellow]",
            default=default_system,
        )
        self.add_system_prompt(system_prompt)

        console.print("\n[green]Ready! Type your queries.[/green]\n")

        # Main loop
        while True:
            try:
                user_input = Prompt.ask("\n[bold blue]You[/bold blue]")

                if not user_input.strip():
                    continue

                if user_input.lower() in ["exit", "quit", "q"]:
                    console.print("\n[yellow]Goodbye![/yellow]\n")
                    break

                if user_input.lower() == "clear":
                    self.conversation = [self.conversation[0]]  # Keep system
                    console.print("[green]Conversation cleared.[/green]")
                    continue

                if user_input.lower() == "reset":
                    self.conversation = []
                    console.print("[green]Session reset.[/green]")
                    continue

                # Display user message
                console.print(f"\n[blue]You:[/blue] {user_input}")

                # Stream and display response
                console.print("\n[bold green]Assistant:[/bold green]")
                response = self.stream_response(user_input)

            except KeyboardInterrupt:
                console.print("\n\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                console.print(f"\n[bold red]Error:[/bold red] {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Modal vLLM Interactive TUI")
    parser.add_argument(
        "--url",
        default="http://localhost:8000/v1",
        help="vLLM API base URL",
    )
    parser.add_argument(
        "--model",
        default="google/gemma-4-26B-A4B-it",
        help="Model ID",
    )

    args = parser.parse_args()

    tui = VLLMTUI(base_url=args.url, model=args.model)
    tui.run()


if __name__ == "__main__":
    main()
```

### Rich Terminal Dashboard

```python
"""
Rich terminal dashboard for monitoring
File: examples/tui-agent/terminal_dashboard.py
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
import time
import os

console = Console()

class InferenceDashboard:
    """Real-time dashboard for vLLM inference monitoring."""

    def __init__(self):
        self.requests = 0
        self.total_tokens = 0
        self.start_time = time.time()
        self.errors = 0

    def record_request(self, tokens: int, success: bool = True):
        """Record completed request."""
        self.requests += 1
        self.total_tokens += tokens
        if not success:
            self.errors += 1

    def get_stats(self) -> dict:
        """Get current statistics."""
        elapsed = time.time() - self.start_time
        return {
            "uptime": elapsed,
            "requests": self.requests,
            "tokens": self.total_tokens,
            "tokens_per_minute": (self.total_tokens / elapsed) * 60 if elapsed > 0 else 0,
            "error_rate": (self.errors / self.requests) * 100 if self.requests > 0 else 0,
        }

    def render(self) -> Layout:
        """Render dashboard layout."""

        stats = self.get_stats()

        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Header
        layout["header"].update(Panel(
            "[bold cyan]Modal vLLM Inference Dashboard[/bold cyan]",
            style="cyan",
        ))

        # Main stats
        stats_table = Table(title="Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        stats_table.add_row("Uptime", f"{stats['uptime']:.0f}s")
        stats_table.add_row("Requests", str(stats['requests']))
        stats_table.add_row("Tokens Generated", f"{stats['tokens']:,}")
        stats_table.add_row("Tokens/min", f"{stats['tokens_per_minute']:.1f}")
        stats_table.add_row("Error Rate", f"{stats['error_rate']:.2f}%")

        layout["main"].update(Panel(stats_table, title="Current Stats"))

        # Footer
        layout["footer"].update(Panel(
            "[dim]Press Ctrl+C to exit[/dim]",
            style="dim",
        ))

        return layout

    def run(self):
        """Run dashboard with live updates."""

        with Live(self.render(), console=console, refresh_per_second=1) as live:
            try:
                while True:
                    live.update(self.render())
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    dashboard = InferenceDashboard()
    dashboard.run()
```

## Interactive Agent Loop

### ReAct Agent Pattern

```python
"""
ReAct (Reasoning + Acting) agent on Modal vLLM
File: examples/tui-agent/react_agent.py
"""

from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
import os
import json

console = Console()

class ReActAgent:
    """ReAct pattern agent with vLLM backend."""

    def __init__(
        self,
        base_url: str,
        model: str = "google/gemma-4-26B-A4B-it",
        max_iterations: int = 10,
    ):
        self.client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", "dummy"),
            base_url=base_url,
        )
        self.model = model
        self.max_iterations = max_iterations
        self.tools = {
            "search": self.tool_search,
            "calculate": self.tool_calculate,
            "wikipedia": self.tool_wikipedia,
        }

    def think(self, prompt: str, context: list) -> str:
        """Generate thought using vLLM."""

        messages = [
            {"role": "system", "content": self._system_prompt()},
            *context,
            {"role": "user", "content": prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
        )

        return response.choices[0].message.content

    def _system_prompt(self) -> str:
        return """You are a ReAct agent that solves problems through reasoning and acting.

For each step:
1. THOUGHT: Analyze the situation and decide what to do
2. ACTION: Choose a tool (search, calculate, wikipedia)
3. OBSERVATION: Report the result

Respond in JSON format:
{
    "thought": "Analysis of current situation",
    "action": "tool_name",
    "action_input": "input for the tool",
}

Available tools:
- search: Search the web for information
- calculate: Perform mathematical calculations
- wikipedia: Look up information on Wikipedia
"""

    def tool_search(self, query: str) -> str:
        """Search tool implementation."""
        return f"Search results for: {query}"

    def tool_calculate(self, expression: str) -> str:
        """Calculate tool implementation."""
        try:
            result = eval(expression)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def tool_wikipedia(self, topic: str) -> str:
        """Wikipedia lookup implementation."""
        return f"Wikipedia summary for: {topic}"

    def run(self, task: str) -> str:
        """Execute task using ReAct pattern."""

        context = []
        console.print(f"\n[bold cyan]Task:[/bold cyan] {task}\n")

        for i in range(self.max_iterations):
            # Generate next step
            step_prompt = f"Task: {task}\n\nContext so far:\n" + "\n".join(context)

            response = self.think(step_prompt, context)

            try:
                # Parse response
                step = json.loads(response)
                thought = step.get("thought", "")
                action = step.get("action", "")
                action_input = step.get("action_input", "")

                console.print(f"[bold yellow]Iteration {i+1}:[/bold yellow]")
                console.print(f"  Thought: {thought}")
                console.print(f"  Action: {action}({action_input})")

                # Execute tool
                if action in self.tools:
                    observation = self.tools[action](action_input)
                    console.print(f"  Observation: {observation}\n")

                    context.append({
                        "role": "assistant",
                        "content": json.dumps(step)
                    })
                    context.append({
                        "role": "user",
                        "content": f"Observation: {observation}"
                    })

                    # Check for completion
                    if "final answer" in thought.lower() or "complete" in thought.lower():
                        return observation

                else:
                    console.print(f"  [red]Unknown tool: {action}[/red]\n")

            except json.JSONDecodeError:
                console.print(f"[yellow]Parse error, continuing...[/yellow]\n")

        return "Max iterations reached"


if __name__ == "__main__":
    agent = ReActAgent(base_url="http://localhost:8000/v1")

    task = console.input("[bold green]Enter task:[/bold green] ")
    result = agent.run(task)

    console.print(f"\n[bold green]Result:[/bold green] {result}")
```

## Multi-Model Agent

### Model Routing Agent

```python
"""
Multi-model agent with automatic model selection
File: examples/tui-agent/multi_model_agent.py
"""

from openai import OpenAI
from dataclasses import dataclass
from enum import Enum
import os

class Model(Enum):
    """Available models."""
    GEMMA_4 = "google/gemma-4-26B-A4B-it"
    MINIMAX_27B = "MiniMaxAI/MiniMax-M2.7"

@dataclass
class ModelConfig:
    """Model configuration."""
    model: Model
    strength: str
    max_tokens: int
    temperature: float
    estimated_cost_factor: float

MODEL_CONFIGS = {
    Model.GEMMA_4: ModelConfig(
        model=Model.GEMMA_4,
        strength="Complex reasoning, code generation, multimodal",
        max_tokens=8192,
        temperature=0.7,
        estimated_cost_factor=1.0,
    ),
    Model.MINIMAX_27B: ModelConfig(
        model=Model.MINIMAX_27B,
        strength="Fast inference, general purpose, cost-effective",
        max_tokens=4096,
        temperature=0.7,
        estimated_cost_factor=0.5,
    ),
}

class MultiModelAgent:
    """Agent that routes requests to appropriate model."""

    def __init__(self, base_url: str):
        self.client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", "dummy"),
            base_url=base_url,
        )

    def select_model(self, task: str) -> ModelConfig:
        """Select best model based on task analysis."""

        task_lower = task.lower()

        # Route based on keywords
        if any(kw in task_lower for kw in ["code", "programming", "function", "debug"]):
            return MODEL_CONFIGS[Model.GEMMA_4]

        if any(kw in task_lower for kw in ["quick", "simple", "fast", "brief"]):
            return MODEL_CONFIGS[Model.MINIMAX_27B]

        # Default to Gemma 4 for complex tasks
        return MODEL_CONFIGS[Model.GEMMA_4]

    def complete(self, task: str, use_routing: bool = True) -> tuple[str, ModelConfig]:
        """Complete task with optional model routing."""

        if use_routing:
            config = self.select_model(task)
        else:
            config = MODEL_CONFIGS[Model.GEMMA_4]

        response = self.client.chat.completions.create(
            model=config.model.value,
            messages=[{"role": "user", "content": task}],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        return response.choices[0].message.content, config


if __name__ == "__main__":
    agent = MultiModelAgent(base_url="http://localhost:8000/v1")

    task = "Explain quantum entanglement"
    response, config = agent.complete(task)

    print(f"Model: {config.model.name}")
    print(f"Response: {response}")
```

## Sandbox Integration

### Agent in Modal Sandbox

```python
"""
Agent running in Modal Sandbox for isolation
File: examples/sandbox-pool/agent_sandbox.py
"""

import modal

app = modal.App("agent-sandbox")

@app.function(
    timeout=600,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def agent_in_sandbox(task: str):
    """Run agent in isolated sandbox environment."""

    import modal
    from openai import OpenAI
    import os

    # Create sandbox
    sandbox = modal.Sandbox.create(
        image=modal.Image.debian_slim(python_version="3.12").uv_pip_install("vllm==0.19.0"),
        gpu="H200",
    )

    try:
        # Initialize vLLM in sandbox
        sandbox.exec(
            "vllm", "serve", "google/gemma-4-26B-A4B-it",
        )

        # Wait for startup
        import time
        time.sleep(60)

        # Create client
        client = OpenAI(
            api_key=os.environ.get("HF_TOKEN", ""),
            base_url="http://localhost:8000/v1",
        )

        # Execute task
        response = client.chat.completions.create(
            model="google/gemma-4-26B-A4B-it",
            messages=[{"role": "user", "content": task}],
            max_tokens=1024,
        )

        return {
            "result": response.choices[0].message.content,
            "sandbox_id": sandbox.object_id,
        }

    finally:
        # Clean up sandbox
        sandbox.terminate()
```

## Next Steps

- Review [Foundation](01-foundation.md) for core concepts
- Explore [Cost Management](04-cost-management.md) for optimization
- Check [Deployment Patterns](02-deployment-patterns.md) for production setup
