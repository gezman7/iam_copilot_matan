"""Configuration for IAM Agent CLI and Server."""

import os
from pydantic import BaseModel
from typing import Optional

class ServerConfig(BaseModel):
    """Server configuration settings."""
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "data/risk_views.db"
    model: str = "llama3.2-ctx4000"
    num_ctx: int = 4000
    debug: bool = False
    
class CliConfig(BaseModel):
    """CLI configuration settings."""
    server_url: str = "http://127.0.0.1:8000"
    debug: bool = False
    
    @property
    def chat_endpoint(self) -> str:
        """Get the chat endpoint URL."""
        return f"{self.server_url}/chat"
    
    @property
    def stream_endpoint(self) -> str:
        """Get the streaming endpoint URL."""
        return f"{self.server_url}/stream"

# Risk categories supported by the IAM Copilot
RISK_CATEGORIES = [
    "NO_MFA_USERS", 
    "WEAK_MFA_USERS", 
    "INACTIVE_USERS", 
    "NEVER_LOGGED_IN_USERS",
    "PARTIALLY_OFFBOARDED_USERS", 
    "SERVICE_ACCOUNTS", 
    "LOCAL_ACCOUNTS", 
    "RECENTLY_JOINED_USERS"
]

# Welcome message for the CLI
WELCOME_MESSAGE = """
Welcome to IAM Copilot Agent!

This CLI allows you to interact with the IAM Copilot agent, which helps you
manage and monitor IAM risks in your environment.

Supported risk categories:
{risk_categories}

Commands:
  //restart - Restart the chat session
  //exit    - Exit the application

Start chatting by typing your query!
""" 