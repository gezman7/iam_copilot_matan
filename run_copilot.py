#!/usr/bin/env python3

"""
Run IAM Copilot

This script starts both the IAM Agent server and a non-streaming CLI client
in separate processes, allowing users to interact with the copilot in a single command.
"""

import os
import sys
import subprocess
import time
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Run IAM Copilot (Server and Client)")
    parser.add_argument("--port", default="8004", help="Port for the server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--stream", action="store_true", help="Use streaming mode (beta)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Define environment variables for child processes
    env = os.environ.copy()
    
    # Start the server process
    server_cmd = [sys.executable, "run_server.py", "--port", args.port]
    if args.debug:
        server_cmd.append("--debug")
    
    print(f"Starting IAM Agent server on port {args.port}...")
    server_process = subprocess.Popen(server_cmd, env=env)
    
    # Give the server time to start
    time.sleep(2)
    
    # Start the client process based on streaming preference
    if args.stream:
        client_cmd = [sys.executable, "simple_cli.py", "--server", f"http://127.0.0.1:{args.port}"]
        if args.debug:
            client_cmd.append("--debug")
        print("Starting IAM Agent CLI in streaming mode (beta)...")
    else:
        client_cmd = [sys.executable, "non_streaming_cli.py", "--server-url", f"http://127.0.0.1:{args.port}"]
        if args.debug:
            client_cmd.append("--debug")
        print("Starting IAM Agent CLI in non-streaming mode...")
    
    client_process = subprocess.Popen(client_cmd, env=env)
    
    try:
        # Wait for the client to exit
        client_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down IAM Copilot...")
    finally:
        # Clean up processes
        if client_process.poll() is None:
            client_process.terminate()
        if server_process.poll() is None:
            server_process.terminate()
    
    print("IAM Copilot has been shut down.")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 