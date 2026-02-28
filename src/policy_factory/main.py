"""CLI entry point for Policy Factory."""

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def load_env_files() -> None:
    """Load .env from multiple locations (in order of preference).

    1. Current working directory
    2. Project root (for development)
    3. User config directory (~/.config/policy-factory/.env)
    """
    from dotenv import load_dotenv

    # Try cwd first
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)
        return

    # Try project root (development mode)
    project_env = Path(__file__).parents[2] / ".env"
    if project_env.exists():
        load_dotenv(project_env)
        return

    # Try user config directory (for global installs)
    config_env = Path.home() / ".config" / "policy-factory" / ".env"
    if config_env.exists():
        load_dotenv(config_env)
        return

    # No .env found - that's OK, env vars might be set directly


# Load environment on import
load_env_files()

# Configure logging
logging.basicConfig(level=logging.WARNING)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="policy-factory",
        description="Policy Factory — AI-powered policy analysis engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  policy-factory server                     Start server on localhost:8765
  policy-factory server --port 8080         Start server on custom port
  policy-factory server --host 0.0.0.0      Bind to all interfaces

Environment:
  ANTHROPIC_API_KEY              Required for Claude Code SDK (agent operations)
  POLICY_FACTORY_HOST            Host to bind to (overrides --host default)
  POLICY_FACTORY_PORT            Port to bind to (overrides --port default)
  POLICY_FACTORY_DB_PATH         Path to SQLite database file
  POLICY_FACTORY_DATA_DIR        Path to data directory
  POLICY_FACTORY_HEARTBEAT_INTERVAL  Heartbeat interval in seconds (default: 14400)
  POLICY_FACTORY_HEARTBEAT_ENABLED   Enable heartbeat (default: true)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # server - web UI server
    server_parser = subparsers.add_parser(
        "server",
        help="Start web UI server",
    )
    default_host = os.environ.get("POLICY_FACTORY_HOST", "127.0.0.1")
    default_port = int(os.environ.get("POLICY_FACTORY_PORT", "8765"))

    server_parser.add_argument(
        "--host",
        default=default_host,
        help=f"Host to bind to (default: {default_host})",
    )

    # Custom action to track if port was explicitly specified
    class PortAction(argparse.Action):
        def __call__(
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: str | Sequence[Any] | None,
            option_string: str | None = None,
        ) -> None:
            setattr(namespace, self.dest, values)
            setattr(namespace, "port_explicit", True)

    server_parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        action=PortAction,
        help=f"Port to bind to (default: {default_port}, auto-increments if busy)",
    )
    # Default flag for when port is not explicitly specified
    server_parser.set_defaults(port_explicit=False)

    return parser


def server_command(args: argparse.Namespace) -> int:
    """Start the web UI server."""
    import uvicorn

    from policy_factory.server.app import create_app
    from policy_factory.server.port_utils import find_available_port, is_port_available
    from policy_factory.store import PolicyStore, get_default_db_path

    # Initialize the store
    db_path = get_default_db_path()
    store = PolicyStore(db_path)
    print(f"Database initialized at {db_path}")

    # Create app with store
    app = create_app(store=store)

    # Determine the port to use
    requested_port = args.port
    port_explicitly_specified = args.port_explicit

    if port_explicitly_specified:
        # User explicitly specified a port - fail if unavailable
        if not is_port_available(args.host, requested_port):
            print(
                f"ERROR: Port {requested_port} is already in use.",
                file=sys.stderr,
            )
            print(
                "Use a different port with --port or let the server auto-select.",
                file=sys.stderr,
            )
            return 1
        port = requested_port
    else:
        # Auto-find available port starting from default
        port = find_available_port(args.host, requested_port, max_attempts=20)
        if port is None:
            print(
                f"ERROR: Could not find an available port in range "
                f"{requested_port}-{requested_port + 19}.",
                file=sys.stderr,
            )
            print(
                "All 20 ports are busy. Please free up a port or specify "
                "a different starting port with --port.",
                file=sys.stderr,
            )
            return 1
        if port != requested_port:
            print(f"Note: Port {requested_port} was busy, using port {port} instead.")

    print(f"Starting Policy Factory server at http://{args.host}:{port}")

    uvicorn.run(app, host=args.host, port=port)
    return 0


def main() -> int:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "server":
        return server_command(args)

    return 0


def cli() -> None:
    """Entry point for console_scripts."""
    sys.exit(main())


if __name__ == "__main__":
    cli()
