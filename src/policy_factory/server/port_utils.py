"""Utility functions for port management."""

import logging
import socket

logger = logging.getLogger(__name__)


def is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        host: Host address to check
        port: Port number to check

    Returns:
        True if the port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Set SO_REUSEADDR to allow quick rebinding
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(
    host: str,
    start_port: int,
    max_attempts: int = 20,
) -> int | None:
    """Find an available port starting from start_port.

    Tries ports sequentially from start_port up to start_port + max_attempts - 1.

    Args:
        host: Host address to bind to
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try (default: 20)

    Returns:
        The first available port, or None if no port is available
    """
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(host, port):
            if offset > 0:
                logger.info("Port %d is available", port)
            return port
        logger.debug("Port %d is busy, trying next...", port)
    return None
