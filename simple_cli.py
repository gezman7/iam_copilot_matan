#!/usr/bin/env python3

import asyncio
import httpx
import json
import argparse
from rich.console import Console
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown

console = Console()

async def stream_query(query, server_url="http://127.0.0.1:8004", stream=True, debug=False):
    """Function to query the IAM agent with streaming or non-streaming support."""
    
    # FIXED: Use the correct endpoint name for non-streaming mode
    endpoint = "/stream" if stream else "/chat"
    url = f"{server_url}{endpoint}"
    
    payload = {
        "query": query,
        "thread_id": "test_thread",
        "stream": stream
    }
    
    console.print(f"[bold green]You:[/bold green] {query}")
    if debug:
        console.print(f"[dim]DEBUG: Using endpoint {url}[/dim]")
        console.print(f"[dim]DEBUG: Payload: {payload}[/dim]")
    
    try:
        if stream:
            current_response = ""
            display_text = Text()
            
            # Use Live display
            with Live(display_text, console=console, refresh_per_second=10) as live:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                        if response.status_code != 200:
                            error_content = await response.aread()
                            console.print(f"[bold red]Error:[/bold red] {error_content.decode()}")
                            return
                        
                        buffer = b""
                        async for chunk in response.aiter_bytes():
                            buffer += chunk
                            if debug:
                                console.print(f"[dim]DEBUG: Raw chunk: {buffer}[/dim]")
                            
                            try:
                                parts = buffer.split(b"\n")
                                
                                for part in parts[:-1]:
                                    if part.strip():
                                        if debug:
                                            console.print(f"[dim]DEBUG: Processing part: {part}[/dim]")
                                        try:
                                            data = json.loads(part)
                                            if debug:
                                                console.print(f"[dim]DEBUG: Parsed JSON: {data}[/dim]")
                                            
                                            if "error" in data:
                                                console.print(f"[bold red]Error:[/bold red] {data['error']}")
                                            elif "chunk" in data:
                                                current_response += data["chunk"]
                                                display_text = Text.from_markup(f"[bold blue]Agent:[/bold blue] {current_response}")
                                            elif "messages" in data and isinstance(data["messages"], list):
                                                # Extract content from the last AI message
                                                for msg in reversed(data["messages"]):
                                                    if msg.get("type") == "ai" and "content" in msg:
                                                        content = msg.get("content", "")
                                                        if content and content not in current_response:
                                                            current_response = content
                                                            display_text = Text.from_markup(f"[bold blue]Agent:[/bold blue] {current_response}")
                                                            break
                                            else:
                                                if debug:
                                                    console.print(f"[dim]DEBUG: Unhandled data format: {data}[/dim]")
                                        except json.JSONDecodeError as e:
                                            if debug:
                                                console.print(f"[dim]DEBUG: JSONDecodeError: {str(e)} for part: {part}[/dim]")
                                
                                buffer = parts[-1]
                            except Exception as e:
                                if debug:
                                    console.print(f"[dim]DEBUG: Processing error: {str(e)}[/dim]")
        else:
            # Non-streaming mode
            if debug:
                console.print(f"[dim]DEBUG: Sending non-streaming request to {url}[/dim]")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
                
                if response.status_code != 200:
                    console.print(f"[bold red]Error (Status {response.status_code}):[/bold red] {response.text}")
                    return
                
                data = response.json()
                if debug:
                    console.print(f"[dim]DEBUG: Non-streaming response: {data}[/dim]")
                
                # Extract the response
                content = ""
                if "response" in data:
                    content = data["response"]
                    if debug:
                        console.print(f"[dim]DEBUG: Found 'response' field with content length {len(content)}[/dim]")
                elif "messages" in data and isinstance(data["messages"], list):
                    if debug:
                        console.print(f"[dim]DEBUG: Found 'messages' field with {len(data['messages'])} messages[/dim]")
                    # Extract content from the last AI message
                    for msg in reversed(data["messages"]):
                        if msg.get("type") == "ai" and "content" in msg:
                            content = msg.get("content", "")
                            if debug:
                                console.print(f"[dim]DEBUG: Found AI message with content length {len(content)}[/dim]")
                            break
                
                current_response = content
        
        # Print final response as markdown if it contains markdown formatting
        console.print("[bold blue]Agent:[/bold blue]")
        if current_response:
            if any(marker in current_response for marker in ["#", "```", "*", "-", ">"]):
                console.print(Markdown(current_response))
            else:
                console.print(current_response)
        else:
            console.print("[bold yellow]No response received from the agent[/bold yellow]")
            
    except httpx.HTTPError as e:
        console.print(f"[bold red]HTTP Error:[/bold red] {str(e)}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if debug:
            import traceback
            console.print(f"[dim]DEBUG: Exception: {traceback.format_exc()}[/dim]")

async def main():
    parser = argparse.ArgumentParser(description="Simple CLI for IAM Agent")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming mode")
    parser.add_argument("--server", default="http://127.0.0.1:8004", help="Server URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    console.print(f"[bold]IAM Agent CLI[/bold] {'(non-streaming)' if args.no_stream else '(streaming)'}")
    console.print("Type 'exit' to quit\n")
    
    while True:
        try:
            query = input("\nEnter your query (or 'exit' to quit): ")
            if query.lower() == 'exit':
                break
            await stream_query(
                query, 
                server_url=args.server, 
                stream=not args.no_stream, 
                debug=args.debug
            )
        except KeyboardInterrupt:
            console.print("[bold yellow]Interrupted. Type 'exit' to quit.[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            if args.debug:
                import traceback
                console.print(f"[dim]DEBUG: {traceback.format_exc()}[/dim]")

if __name__ == "__main__":
    asyncio.run(main()) 