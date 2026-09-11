"""stdio MCP entrypoint for controlled Xinye NAS deployment."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import core

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("xinye-nas-deploy")


def safe_call(function: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        logging.exception("MCP operation failed")
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def nas_health() -> dict[str, Any]:
    """Check SSH connectivity and the deployed system health endpoint."""
    return safe_call(core.tool_health)


@mcp.tool()
def nas_status() -> dict[str, Any]:
    """Show Docker Compose status for the work-hours system."""
    return safe_call(core.tool_status)


@mcp.tool()
def nas_logs(service: str = "backend", tail: int = 80) -> dict[str, Any]:
    """Read recent backend, frontend, or all service logs; tail is limited to 200 lines."""
    return safe_call(core.tool_logs, service, tail)


@mcp.tool()
def nas_backup() -> dict[str, Any]:
    """Create a timestamped remote deployment-file backup; Docker data volume is untouched."""
    return safe_call(core.tool_backup)


@mcp.tool()
def nas_deploy(confirm: bool = False) -> dict[str, Any]:
    """Build and publish the current project. Preview first; execute with confirm=true."""
    return safe_call(core.tool_deploy, confirm)


@mcp.tool()
def nas_rollback(backup_name: str, confirm: bool = False) -> dict[str, Any]:
    """Restore a .backup-* directory after preview; execute only with confirm=true."""
    return safe_call(core.tool_rollback, backup_name, confirm)


if __name__ == "__main__":
    mcp.run(transport="stdio")

