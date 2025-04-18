#!/usr/bin/env python3

"""Non-streaming CLI for IAM Agent.

This is a modified version of the IAM Agent CLI that defaults to non-streaming mode.
"""

import sys
import os
import argparse
import uuid
import json
import asyncio
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.theme import Theme
import httpx

# Add the project root to the path to ensure we can import iam_agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from iam_agent.config import CliConfig, RISK_CATEGORIES, WELCOME_MESSAGE

# Custom theme for rich
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "user": "green",
    "agent": "blue",
    "system": "purple",
})

console = Console(theme=custom_theme)

class NonStreamingIAMAgentCLI:
    """Non-streaming CLI for IAM Agent."""
    
    def __init__(self, config: CliConfig = None):
        """Initialize the CLI.
        
        Args:
            config: CLI configuration
        """
        self.config = config or CliConfig()
        self.thread_id = str(uuid.uuid4())
        self.streaming = False  # Always set to False for this version
        self.running = True
    
    def print_welcome_message(self):
        """Print the welcome message."""
        # Format risk categories for display
        formatted_risks = "\n".join([f"  • {risk}" for risk in RISK_CATEGORIES])
        message = WELCOME_MESSAGE.format(risk_categories=formatted_risks)
        
        console.print(Panel(
            Markdown(message),
            title="[bold cyan]IAM Copilot Agent (Non-Streaming Mode)[/bold cyan]",
            border_style="cyan",
            expand=False
        ))
    
    def print_user_message(self, message: str):
        """Print a user message."""
        console.print(f"[bold green]You:[/bold green] {message}")
    
    def print_agent_message(self, message: str):
        """Print an agent message."""
        # Check if the message is empty
        if not message.strip():
            return
        
        # Format the message as markdown
        if message.strip().startswith(("#", "*", "-", ">", "```")):
            console.print("[bold blue]Agent:[/bold blue]")
            console.print(Markdown(message))
        else:
            console.print(f"[bold blue]Agent:[/bold blue] {message}")
    
    def print_system_message(self, message: str):
        """Print a system message."""
        console.print(f"[bold purple]System:[/bold purple] {message}")
    
    def print_debug_message(self, message: str):
        """Print a debug message if debug mode is enabled."""
        if self.config.debug:
            console.print(f"[dim][bold cyan]Debug:[/bold cyan] {message}[/dim]")
    
    def print_error_message(self, message: str):
        """Print an error message."""
        console.print(f"[bold red]Error:[/bold red] {message}")
    
    async def _process_query(self, query: str):
        """Process a query with the agent using non-streaming mode."""
        url = self.config.chat_endpoint
        
        # Prepare request payload
        payload = {
            "query": query,
            "thread_id": self.thread_id,
            "stream": False  # Always false for non-streaming mode
        }
        
        try:
            self.print_debug_message(f"Sending request to {url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=120.0)  # Longer timeout
                
                if response.status_code != 200:
                    self.print_error_message(f"Error: {response.text}")
                    return
                
                data = response.json()
                self.print_agent_message(data["response"])
                
                # Update thread_id if present
                if "thread_id" in data:
                    self.thread_id = data["thread_id"]
                    self.print_debug_message(f"Thread ID: {self.thread_id}")
                
        except httpx.HTTPError as e:
            self.print_error_message(f"HTTP error: {str(e)}")
        except Exception as e:
            self.print_error_message(f"Error: {str(e)}")
    
    def handle_command(self, command: str) -> bool:
        """Handle a special command.
        
        Returns:
            True if the command was handled, False otherwise
        """
        if command == "//exit":
            self.print_system_message("Exiting...")
            self.running = False
            return True
        elif command == "//restart":
            self.thread_id = str(uuid.uuid4())
            self.print_system_message("Chat session restarted.")
            return True
        elif command == "//debug":
            self.config.debug = not self.config.debug
            self.print_system_message(f"Debug mode {'enabled' if self.config.debug else 'disabled'}.")
            return True
        return False
    
    async def run(self):
        """Run the CLI interface."""
        self.print_welcome_message()
        self.print_system_message("Running in non-streaming mode.")
        
        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask("[bold green]You")
                
                # Handle empty input
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith("//"):
                    if self.handle_command(user_input):
                        continue
                
                # Process query (always non-streaming)
                await self._process_query(user_input)
                
            except KeyboardInterrupt:
                self.print_system_message("Interrupted. Type //exit to quit.")
            except Exception as e:
                self.print_error_message(f"Error: {str(e)}")
    
def main():
    """Run the CLI with command-line arguments."""
    parser = argparse.ArgumentParser(description="Non-Streaming IAM Agent CLI")
    parser.add_argument("--server-url", type=str, default="http://127.0.0.1:8000", help="URL of the IAM Agent server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Create config
    config = CliConfig(
        server_url=args.server_url,
        debug=args.debug
    )
    
    # Create CLI
    cli = NonStreamingIAMAgentCLI(config=config)
    
    # Run CLI
    asyncio.run(cli.run())

if __name__ == "__main__":
    main() 