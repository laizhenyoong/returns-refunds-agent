import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from mcp_client.gateway_auth import GatewayTokenManager, gateway_token_manager_from_env

logger = logging.getLogger(__name__)


def get_gateway_mcp_client() -> MCPClient | None:
    """Return an MCPClient connected to the AgentCore Gateway, or None if unconfigured.

    Reads the gateway URL from GATEWAY_URL. Access tokens come from a
    GatewayTokenManager built from the GATEWAY_* env vars on first connection, so
    importing this module does not require them to be set. Every connection attempt
    asks the manager for a token, which it caches and refreshes before expiry.
    """
    gateway_url = os.environ.get("GATEWAY_URL")
    if not gateway_url:
        logger.warning("GATEWAY_URL not set; gateway MCP client will not be created.")
        return None

    token_manager: GatewayTokenManager | None = None

    def create_transport():
        nonlocal token_manager
        if token_manager is None:
            token_manager = gateway_token_manager_from_env()
        headers = {"Authorization": f"Bearer {token_manager.get_token()}"}
        return streamablehttp_client(gateway_url, headers=headers)

    return MCPClient(create_transport)
