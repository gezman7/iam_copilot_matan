from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="iam_agent",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="CLI and Server for IAM Copilot Agent",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/iam_agent",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.23.2",
        "rich>=13.7.0",
        "prompt_toolkit>=3.0.41",
        "httpx>=0.25.0",
        "typer>=0.9.0",
        "langchain==0.3.23",
        "langchain-core==0.3.52",
        "langchain-community==0.3.21",
        "langgraph==0.3.30",
        "langgraph-checkpoint>=2.0.24",
        "langchain-ollama==0.3.2",
        "tiktoken==0.9.0",
        "sqlglot==26.14.0",
    ],
    entry_points={
        "console_scripts": [
            "iam-cli=iam_agent.cli:main",
            "iam-server=iam_agent.server:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
) 