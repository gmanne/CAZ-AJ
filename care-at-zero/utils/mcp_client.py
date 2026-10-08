"""
MCP client helper for the Streamlit app.

Instead of importing connectors/scoring directly, app.py calls these
functions, which speak the real Model Context Protocol to
mcp_server/server.py (spawned as a subprocess over stdio) — the same
server Claude Desktop or any other MCP client could connect to.

This is a genuine MCP integration, not a simulation: the Streamlit app
is an MCP *client*, the same role Claude Desktop plays, talking to the
same server over the same protocol.

A fresh server subprocess is spawned per call rather than kept alive
across Streamlit reruns. That costs a little startup time per search,
but avoids the complexity (and failure modes) of managing a long-lived
async subprocess inside Streamlit's synchronous rerun model — a
reasonable tradeoff for a search that already involves live network
calls to federal APIs.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"


class MCPUnavailableError(Exception):
    """Raised when the MCP server subprocess can't be started or reached."""
    pass


async def _call_tool_async(tool_name: str, arguments: Dict[str, Any]) -> Union[List, Dict, str]:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

    if result.isError:
        error_text = "".join(getattr(c, "text", "") for c in result.content)
        raise MCPUnavailableError(f"MCP tool '{tool_name}' returned an error: {error_text}")

    # Prefer structured content (search_care/list_upcoming_events return
    # {"result": [...]}). Fall back to parsing the text content as JSON
    # for tools that return a plain dict or string (get_care_detail,
    # get_referral_summary).
    if result.structuredContent and "result" in result.structuredContent:
        return result.structuredContent["result"]

    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def call_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Union[List, Dict, str]:
    """
    Synchronous wrapper — call an MCP tool and get back plain Python
    data (list/dict/str), exactly like a normal Python function call,
    even though a real MCP round-trip happens underneath.
    """
    arguments = arguments or {}
    try:
        return asyncio.run(_call_tool_async(tool_name, arguments))
    except MCPUnavailableError:
        raise
    except Exception as e:
        raise MCPUnavailableError(f"Could not reach the CareAtZero MCP server: {e}") from e
