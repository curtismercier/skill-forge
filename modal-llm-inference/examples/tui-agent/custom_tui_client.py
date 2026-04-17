"""
Custom TUI client for Modal vLLM inference
File: examples/tui-agent/custom_tui_client.py

Usage:
    python examples/tui-agent/custom_tui_client.py --url http://localhost:8000/v1
"""

import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.live import Live
from openai import OpenAI

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
        self.stats = {
            "requests": 0,
            "total_tokens": 0,
        }

    def add_system_prompt(self, prompt: str):
        """Add system prompt to conversation."""
        self.conversation.append({
            "role": "system",
            "content": prompt,
        })

    def stream_response(self, user_input: str) -> str:
        """Stream response to terminal with Rich UI."""

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

                    # Update display
                    live.update(
                        Panel(
                            Markdown("".join(response_content)),
                            title="Response",
                            border_style="green",
                        )
                    )

        response_text = "".join(response_content)

        # Update stats
        self.stats["requests"] += 1
        self.stats["total_tokens"] += len(response_text.split())

        # Add assistant response to conversation
        self.conversation.append({
            "role": "assistant",
            "content": response_text,
        })

        return response_text

    def print_help(self):
        """Print available commands."""
        help_text = """
**Commands:**
- `exit`, `quit`, `q`: Exit the application
- `clear`: Clear conversation history
- `reset`: Reset session completely
- `stats`: Show statistics
- `help`: Show this help message
- `model <name>`: Switch model (gemma4, minimax)
        """
        console.print(Markdown(help_text))

    def show_stats(self):
        """Show conversation statistics."""
        stats_text = f"""
**Statistics:**
- Requests: {self.stats['requests']}
- Total tokens: {self.stats['total_tokens']}
- Conversation length: {len(self.conversation)} messages
        """
        console.print(Markdown(stats_text))

    def run(self):
        """Main TUI loop."""

        # Header
        console.print(Panel.fit(
            "[bold cyan]Modal vLLM Interactive TUI[/bold cyan]\n"
            f"Model: {self.model}\n"
            f"Endpoint: {self.base_url}",
            border_style="cyan",
        ))

        # Setup system prompt
        default_system = "You are a helpful, knowledgeable AI assistant."
        system_prompt = Prompt.ask(
            "\n[yellow]System Prompt[/yellow]",
            default=default_system,
        )
        self.add_system_prompt(system_prompt)

        console.print("\n[green]Ready! Type your queries or 'help' for commands.[/green]\n")

        # Main loop
        while True:
            try:
                user_input = Prompt.ask("\n[bold blue]You[/bold blue]")

                if not user_input.strip():
                    continue

                # Handle commands
                cmd = user_input.lower().strip()

                if cmd in ["exit", "quit", "q"]:
                    console.print("\n[yellow]Goodbye![/yellow]\n")
                    break

                if cmd == "clear":
                    self.conversation = [self.conversation[0]]
                    console.print("[green]Conversation cleared.[/green]")
                    continue

                if cmd == "reset":
                    self.conversation = []
                    console.print("[green]Session reset.[/green]")
                    continue

                if cmd == "stats":
                    self.show_stats()
                    continue

                if cmd == "help":
                    self.print_help()
                    continue

                if cmd.startswith("model "):
                    new_model = cmd.split(" ", 1)[1].strip()
                    if new_model == "gemma4":
                        self.model = "google/gemma-4-26B-A4B-it"
                    elif new_model == "minimax":
                        self.model = "MiniMaxAI/MiniMax-M2.7"
                    console.print(f"[green]Model switched to: {self.model}[/green]")
                    continue

                # Display user message
                console.print(f"\n[blue]You:[/blue] {user_input}")

                # Stream and display response
                console.print("\n[bold green]Assistant:[/bold green]")
                try:
                    response = self.stream_response(user_input)
                except Exception as e:
                    console.print(f"\n[bold red]Error:[/bold red] {e}")

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
