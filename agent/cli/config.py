"""CLI configuration and utilities."""

import os
from pathlib import Path
from typing import Dict, Optional

import click
from rich.console import Console

console = Console()


class CLIConfig:
    """CLI configuration management."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".zorix"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        self._config = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                import json
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
            except Exception as e:
                console.print(f"Warning: Failed to load config: {e}", style="yellow")
                self._config = {}
        else:
            self._config = self.get_default_config()
            self.save_config()
    
    def save_config(self):
        """Save configuration to file."""
        try:
            import json
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            console.print(f"Warning: Failed to save config: {e}", style="yellow")
    
    def get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "api_url": "http://127.0.0.1:8000",
            "output_format": "rich",
            "log_level": "INFO",
            "auto_approve_low_risk": False,
            "default_dry_run": False,
            "max_search_results": 10,
            "poll_interval": 2,
            "request_timeout": 30
        }
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value."""
        self._config[key] = value
        self.save_config()
    
    def update(self, updates: Dict):
        """Update multiple configuration values."""
        self._config.update(updates)
        self.save_config()
    
    def reset(self):
        """Reset configuration to defaults."""
        self._config = self.get_default_config()
        self.save_config()
    
    def show(self) -> Dict:
        """Show current configuration."""
        return self._config.copy()


# Global config instance
cli_config = CLIConfig()


@click.group()
def config():
    """Manage CLI configuration."""
    pass


@config.command()
def show():
    """Show current configuration."""
    config_data = cli_config.show()
    
    from rich.table import Table
    
    table = Table(title="Zorix CLI Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Description", style="white")
    
    descriptions = {
        "api_url": "API server URL",
        "output_format": "Default output format (rich/json)",
        "log_level": "Logging level",
        "auto_approve_low_risk": "Auto-approve low-risk tasks",
        "default_dry_run": "Default to dry-run mode",
        "max_search_results": "Maximum search results",
        "poll_interval": "Task polling interval (seconds)",
        "request_timeout": "HTTP request timeout (seconds)"
    }
    
    for key, value in config_data.items():
        description = descriptions.get(key, "")
        table.add_row(key, str(value), description)
    
    console.print(table)


@config.command()
@click.argument("key")
@click.argument("value")
def set_value(key, value):
    """Set a configuration value."""
    # Type conversion
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)
    elif value.replace(".", "").isdigit():
        value = float(value)
    
    cli_config.set(key, value)
    console.print(f"✅ Set {key} = {value}", style="green")


@config.command()
@click.argument("key")
def get_value(key):
    """Get a configuration value."""
    value = cli_config.get(key)
    if value is not None:
        console.print(f"{key} = {value}")
    else:
        console.print(f"❌ Configuration key '{key}' not found", style="red")


@config.command()
@click.confirmation_option(prompt="Are you sure you want to reset all configuration?")
def reset():
    """Reset configuration to defaults."""
    cli_config.reset()
    console.print("✅ Configuration reset to defaults", style="green")


@config.command()
def edit():
    """Edit configuration file in default editor."""
    import subprocess
    
    editor = os.environ.get("EDITOR", "nano")
    
    try:
        subprocess.run([editor, str(cli_config.config_file)])
        cli_config.load_config()  # Reload after editing
        console.print("✅ Configuration reloaded", style="green")
    except Exception as e:
        console.print(f"❌ Failed to edit config: {e}", style="red")


def get_config_value(key: str, default=None, env_var: Optional[str] = None):
    """Get configuration value with environment variable fallback."""
    # Check environment variable first
    if env_var and env_var in os.environ:
        value = os.environ[env_var]
        # Type conversion for common types
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        elif value.isdigit():
            return int(value)
        elif value.replace(".", "").isdigit():
            return float(value)
        return value
    
    # Check CLI config
    return cli_config.get(key, default)