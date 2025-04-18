#!/usr/bin/env python3

"""
Run the IAM Agent Server

This script launches the IAM Agent server with debug mode enabled.
For more options, run with --help flag.
"""

import sys
from iam_agent.server import main

if __name__ == "__main__":
    sys.argv.extend(["--debug", "--port", "8004"])  # Enable debug mode and set port
    sys.exit(main()) 