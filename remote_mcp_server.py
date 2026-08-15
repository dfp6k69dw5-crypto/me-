#!/usr/bin/env python3
"""Remote MCP entrypoint for Claude custom connectors.

This exposes the same Alex Repo Simulator tools over Streamable HTTP at /mcp.
It is intentionally stateless at the transport layer so it can run behind a
normal HTTPS host or serverless platform.
"""

from __future__ import annotations

import os

# Hosted filesystems are often read-only. Keep transient run history in /tmp.
os.environ.setdefault("SIMULATOR_RUN_DIR", "/tmp/alex-repo-simulator-runs")

from mcp_server import mcp

# Passing a non-local host prevents the SDK from installing a localhost-only
# Host allowlist. The service exposes no private network resources; its only
# capability is executing the simulator bundled in this repository.
app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
)

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
        json_response=True,
    )
