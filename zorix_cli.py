#!/usr/bin/env python3
"""
Zorix Agent CLI Tool

A command-line interface for interacting with the Zorix Agent system.
"""

import sys
from pathlib import Path

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.cli.main import cli

if __name__ == "__main__":
    cli()