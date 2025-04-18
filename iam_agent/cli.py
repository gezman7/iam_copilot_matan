"""Interactive CLI for IAM Agent.

This module provides a rich, colorful CLI interface for interacting with the 
IAM Copilot agent through the FastAPI server.
"""

import sys
import os
import argparse
import uuid
import json
import asyncio
import threading
from typing import Optional, List, Dict, Any, Union

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.theme import Theme
from rich.live import Live
from rich.text import Text
import httpx

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

class IAMAgentCLI:
    """Interactive CLI for IAM Agent."""
    
    def __init__(self, config: CliConfig = None):
        """Initialize the CLI.
        
        Args:
            config: CLI configuration
        """
        self.config = config or CliConfig()
        self.thread_id = str(uuid.uuid4())
        self.streaming = True
        self.current_response = ""
        self.running = True
    
    def print_welcome_message(self):
        """Print the welcome message."""
        # Format risk categories for display
        formatted_risks = "\n".join([f"  • {risk}" for risk in RISK_CATEGORIES])
        message = WELCOME_MESSAGE.format(risk_categories=formatted_risks)
        
        console.print(Panel(
            Markdown(message),
            title="[bold cyan]IAM Copilot Agent[/bold cyan]",
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
    
    async def _process_stream(self, query: str):
        """Process a streaming chat with the agent."""
        url = self.config.stream_endpoint
        
        # Prepare request payload
        payload = {
            "query": query,
            "thread_id": self.thread_id,
            "stream": True
        }
        
        try:
            self.current_response = ""
            display_text = Text()
            
            # Use a Live context to update the display in place
            with Live(display_text, console=console, refresh_per_second=10) as live:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                        if response.status_code != 200:
                            error_content = await response.aread()
                            self.print_error_message(f"Error: {error_content.decode()}")
                            return
                        
                        # Process streaming response
                        buffer = b""
                        async for chunk in response.aiter_bytes():
                            buffer += chunk
                            
                            try:
                                # Split the buffer on newlines to handle multiple JSON objects
                                parts = buffer.split(b"\n")
                                
                                # Process all complete JSON objects
                                for i, part in enumerate(parts[:-1]):  # All except the last part
                                    if part.strip():
                                        data = json.loads(part)
                                        
                                        if "error" in data:
                                            self.print_error_message(data["error"])
                                        elif "chunk" in data:
                                            self.current_response += data["chunk"]
                                            display_text = Text.from_markup(f"[bold blue]Agent:[/bold blue] {self.current_response}")
                                            # Optional: update thread_id if present
                                            if "thread_id" in data:
                                                self.thread_id = data["thread_id"]
                                
                                # Keep the last part as it might be incomplete
                                buffer = parts[-1]
                            
                            except json.JSONDecodeError:
                                # This can happen if we get incomplete JSON
                                pass
            
            # Print final response
            if self.current_response:
                self.print_agent_message(self.current_response)
            else:
                self.print_error_message("No response received from agent.")
            
        except httpx.HTTPError as e:
            self.print_error_message(f"HTTP error: {str(e)}")
        except Exception as e:
            self.print_error_message(f"Error: {str(e)}")

    async def _process_query(self, query: str):
        """Process a query with the agent."""
        url = self.config.chat_endpoint
        
        # Prepare request payload
        payload = {
            "query": query,
            "thread_id": self.thread_id,
            "stream": False
        }
        
        try:
            self.print_debug_message(f"Sending request to {url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
                
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
        return False
    
    async def run(self):
        """Run the CLI interface."""
        self.print_welcome_message()
        
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
                
                # Process query
                if self.streaming:
                    await self._process_stream(user_input)
                else:
                    await self._process_query(user_input)
                
            except KeyboardInterrupt:
                self.print_system_message("Interrupted. Type //exit to quit.")
            except Exception as e:
                self.print_error_message(f"Error: {str(e)}")
    
def main():
    """Run the CLI with command-line arguments."""
    parser = argparse.ArgumentParser(description="IAM Agent CLI")
    parser.add_argument("--server-url", type=str, default="http://127.0.0.1:8000", help="URL of the IAM Agent server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming responses")
    
    args = parser.parse_args()
    
    # Create config
    config = CliConfig(
        server_url=args.server_url,
        debug=args.debug
    )
    
    # Create CLI
    cli = IAMAgentCLI(config=config)
    
    # Set streaming mode
    cli.streaming = not args.no_stream
    
    # Run CLI
    asyncio.run(cli.run())

if __name__ == "__main__":
    main() 