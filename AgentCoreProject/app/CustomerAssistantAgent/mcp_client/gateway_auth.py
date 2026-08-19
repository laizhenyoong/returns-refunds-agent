"""OAuth client-credentials token management for AgentCore Gateway access.

Fetches and caches a JWT access token from a Cognito (or any OAuth2
client_credentials-compatible) token endpoint, automatically refreshing it
shortly before it expires.
"""

import logging
import os
import threading
import time

import requests

logger = logging.getLogger(__name__)

# Refresh this many seconds before the token's reported expiry to avoid
# using a token that expires mid-request.
_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class GatewayTokenManager:
    """Fetches and caches an OAuth2 client_credentials access token."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_endpoint: str,
        scope: str,
    ):
        if not client_id or not client_secret or not token_endpoint or not scope:
            raise ValueError(
                "client_id, client_secret, token_endpoint, and scope are all required "
                "to create a GatewayTokenManager."
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_endpoint = token_endpoint
        self._scope = scope

        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        """Return a valid cached access token, fetching/refreshing it if needed."""
        with self._lock:
            if self._access_token is None or time.time() >= self._expires_at:
                self._fetch_token()
            return self._access_token

    def _fetch_token(self) -> None:
        logger.info("Fetching new gateway access token from %s", self._token_endpoint)
        response = requests.post(
            self._token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 3600)
        self._expires_at = time.time() + max(expires_in - _EXPIRY_SAFETY_MARGIN_SECONDS, 0)


def gateway_token_manager_from_env() -> GatewayTokenManager:
    """Build a GatewayTokenManager from GATEWAY_* environment variables."""
    return GatewayTokenManager(
        client_id=os.environ["GATEWAY_CLIENT_ID"],
        client_secret=os.environ["GATEWAY_CLIENT_SECRET"],
        token_endpoint=os.environ["GATEWAY_TOKEN_ENDPOINT"],
        scope=os.environ["GATEWAY_SCOPE"],
    )
