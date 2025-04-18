# IAM Copilot

IAM Copilot is an AI-powered agent that helps you analyze and manage IAM (Identity and Access Management) security risks. It uses natural language queries to help you understand your IAM configurations and identify potential security issues.

## Features

- Query IAM user accounts and permissions using natural language
- Identify security risks like users without MFA, inactive accounts, and more
- Get recommendations for improving your IAM security posture
- Easy-to-use command-line interface

## Prerequisites

Before running IAM Copilot, ensure you have:

1. Python 3.9 or newer installed
2. pip or poetry for package management

## Installation

### Using pip

```bash
# Clone the repository
git clone https://github.com/yourusername/iam_agent.git
cd iam_agent

# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Using Poetry

```bash
# Clone the repository
git clone https://github.com/yourusername/iam_agent.git
cd iam_agent

# Install dependencies with Poetry
poetry install
```

## Running IAM Copilot

The easiest way to run IAM Copilot is with the provided `run_copilot.py` script, which starts both the server and client:

```bash
# Run with default settings (non-streaming mode)
./run_copilot.py

# Enable debug mode
./run_copilot.py --debug

# Change server port
./run_copilot.py --port 9000
```

By default, IAM Copilot runs in non-streaming mode. Streaming mode is available as a beta feature:

```bash
# Run with streaming mode (beta)
./run_copilot.py --stream
```

## Running Components Separately

If you need to run the server and client separately:

### Server

```bash
# Run with default settings
./run_server.py

# Run with custom port
./run_server.py --port 9000

# Run with debug mode
./run_server.py --debug
```

### Client

Non-streaming client (recommended):
```bash
# Run with default settings
./non_streaming_cli.py

# Connect to custom server URL
./non_streaming_cli.py --server-url http://127.0.0.1:9000
```

Streaming client (beta):
```bash
# Run with default settings
./simple_cli.py

# Explicitly disable streaming
./simple_cli.py --no-stream

# Connect to custom server
./simple_cli.py --server http://127.0.0.1:9000
```

## Client Commands

While using the client, you can use these special commands:

- `//exit` - Exit the client
- `//restart` - Restart the current conversation
- `//debug` - Toggle debug mode

## License

[Add license information here]

## Contributing

[Add contribution guidelines here]
