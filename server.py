"""
Entry point for running the server from a source checkout:

    fastmcp run server.py

The code lives in the mcp_cookidoo package; installed from PyPI, the server is
started with the ``mcp-cookidoo`` command instead.
"""

from mcp_cookidoo.server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()
