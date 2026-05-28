"""Registry client subpackage.

Reads the official MCP registry at `registry.modelcontextprotocol.io` and
exposes the inventory as typed `RegistryEntry` objects.
"""

from mcp_verified.registry.client import RegistryClient, RegistryEntry

__all__ = ["RegistryClient", "RegistryEntry"]
