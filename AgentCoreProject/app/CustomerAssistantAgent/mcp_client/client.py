import logging
import os

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from mcp_client.gateway_auth import GatewayTokenManager, gateway_token_manager_from_env

logger = logging.getLogger(__name__)


def get_gateway_mcp_client(token_manager: GatewayTokenManager | None = None) -> MCPClient | None:
    """Return an MCPClient connected to the AgentCore Gateway, or None if unconfigured.

    Reads the gateway URL from the GATEWAY_URL environment variable and obtains
    OAuth access tokens via `token_manager` (built lazily from GATEWAY_CLIENT_ID,
    GATEWAY_CLIENT_SECRET, GATEWAY_TOKEN_ENDPOINT, GATEWAY_SCOPE on first use, if
    not provided). Each connection attempt fetches a fresh (cached/auto-refreshed)
    token so the MCP client always authenticates with a non-expired Bearer token.
    """
    gateway_url = os.environ.get("GATEWAY_URL")
    if not gateway_url:
        logger.warning("GATEWAY_URL not set; gateway MCP client will not be created.")
        return None

    # Lazily built on first connection attempt so importing this module doesn't
    # require GATEWAY_* env vars to already be set.
    _token_manager_holder: list[GatewayTokenManager] = [] if token_manager is None else [token_manager]

    def _create_streamable_http_transport():
        if not _token_manager_holder:
            _token_manager_holder.append(gateway_token_manager_from_env())
        access_token = _token_manager_holder[0].get_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        return streamablehttp_client(gateway_url, headers=headers)

    return MCPClient(_create_streamable_http_transport)
