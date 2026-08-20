"""AgentCore Gateway RESPONSE interceptor that redacts internal business fields.

Runs after a gateway target returns and before the response reaches the agent, so
internal-only values never enter the LLM context. This is not PII redaction —
Bedrock Guardrails covers standardised patterns like emails and card numbers. The
fields blocked here (wholesale cost, margin, supplier ID, internal notes) have no
standard shape; they are known only from our own schema.

Gateway invocation contract, as observed from a live RESPONSE interception:

    {
      "interceptorInputVersion": "1.0",
      "mcp": {
        "gatewayRequest":     {"path", "httpMethod", "headers", "body", "context"},
        "gatewayResponse":    {"path", "httpMethod", "headers", "statusCode",
                               "body", "isStreamingResponse"},
        "rawGatewayRequest":  {"body": "<original JSON text>"}
      }
    }

`gatewayResponse.body` arrives already parsed as the MCP JSON-RPC envelope. Tool
output sits inside it as JSON-encoded text under `result.content[].text`, so
redaction has to walk into embedded JSON strings as well as ordinary nested maps.

The reply shape is strict — the gateway answers anything else with
`InterceptorException - Received invalid response from interceptor`:

    {
      "interceptorOutputVersion": "1.0",
      "mcp": {"transformedGatewayResponse": {"body": <replacement body>}}
    }

`transformedGatewayResponse` must be nested under `mcp` and must carry `body`
alone; echoing back `statusCode`, `headers`, or the other `gatewayResponse`
fields is rejected. The interceptor runs for every MCP message, `initialize` and
`tools/list` included, so an invalid reply breaks the handshake, not just a tool
call.
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Any

import boto3

# The Lambda runtime configures the root logger before this module is imported,
# so basicConfig is a no-op here and INFO records would be dropped at WARNING.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OUTPUT_VERSION = "1.0"
REDACTED = "[INTERNAL - REDACTED]"

# Matched against key names normalised to lowercase alphanumerics, so
# `wholesale_cost`, `wholesaleCost`, and `Wholesale-Cost` all collapse to the
# same entry.
BLOCKED_KEYS = frozenset(
    {
        "wholesalecost",
        "costprice",
        "profitmargin",
        "marginpct",
        "internalnotes",
        "internalflag",
        "supplierid",
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]")

CACHE_TABLE = os.environ.get("CACHE_TABLE", "workshop-interceptor-cache")
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

# Must match CACHEABLE_TOOLS in the REQUEST interceptor: an entry written for a
# tool that side never reads is dead weight, and the reverse is a silent miss.
CACHEABLE_TOOLS = frozenset(
    {
        "policy-retrieval___policy_retrieval",
        "data-lookup___order_lookup",
        "data-lookup___user_lookup",
        "data-lookup___product_lookup",
        "data-lookup___find_returned_products",
    }
)

_table = boto3.resource("dynamodb").Table(CACHE_TABLE)


def cache_key(tool_name: str, arguments: Any) -> str:
    """Stable key for a tool call. Must match the REQUEST interceptor's key."""
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{tool_name}\n{canonical}".encode()).hexdigest()
    return f"{tool_name}#{digest[:32]}"


def _store(request_body: Any, response_body: Any) -> None:
    """Cache a successful read-only tool result for the REQUEST interceptor.

    The body stored here is the redacted one, so a later cache hit serves
    redacted data too — redaction cannot be bypassed by warming the cache.
    """
    if not isinstance(request_body, dict) or request_body.get("method") != "tools/call":
        return
    params = request_body.get("params") or {}
    tool_name = params.get("name")
    if tool_name not in CACHEABLE_TOOLS:
        return
    result = (response_body or {}).get("result") if isinstance(response_body, dict) else None
    if not isinstance(result, dict) or result.get("isError"):
        return  # never cache an error

    try:
        _table.put_item(
            Item={
                "cache_key": cache_key(tool_name, params.get("arguments")),
                "body": json.dumps(response_body),
                "expires_at": int(time.time()) + CACHE_TTL_SECONDS,
            }
        )
        logger.info("Cached %s for %ds.", tool_name, CACHE_TTL_SECONDS)
    except Exception:  # noqa: BLE001 - a cache failure must not fail the call
        logger.exception("Cache write failed for %s.", tool_name)


def _normalise(key: str) -> str:
    return _NON_ALNUM.sub("", key.lower())


class _Redactor:
    """Recursively replaces blocked values, counting each replacement."""

    def __init__(self) -> None:
        self.count = 0

    def walk(self, node: Any) -> Any:
        if isinstance(node, dict):
            return {key: self._value(key, value) for key, value in node.items()}
        if isinstance(node, list):
            return [self.walk(item) for item in node]
        if isinstance(node, str):
            return self._embedded_json(node)
        return node

    def _value(self, key: str, value: Any) -> Any:
        if _normalise(key) in BLOCKED_KEYS:
            self.count += 1
            return REDACTED
        return self.walk(value)

    def _embedded_json(self, text: str) -> str:
        """Redact inside a string that itself holds a JSON object or array.

        MCP wraps tool output as JSON-encoded text inside `result.content`, so the
        business fields live one encoding layer below the response body.
        """
        stripped = text.strip()
        if not stripped.startswith(("{", "[")):
            return text
        try:
            inner = json.loads(stripped)
        except json.JSONDecodeError:
            return text

        before = self.count
        redacted = self.walk(inner)
        return json.dumps(redacted) if self.count > before else text


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    mcp = event.get("mcp") or {}
    gateway_response = mcp.get("gatewayResponse")

    if not isinstance(gateway_response, dict):
        # Nothing to transform, and no body to hand back.
        logger.warning("No mcp.gatewayResponse in event; passing through unchanged.")
        return {"interceptorOutputVersion": OUTPUT_VERSION}

    redactor = _Redactor()
    transformed_body = redactor.walk(gateway_response.get("body"))

    request_body = (mcp.get("gatewayRequest") or {}).get("body")
    method = (request_body or {}).get("method")
    logger.info("Redacted %d field(s) from the %s response.", redactor.count, method)

    _store(request_body, transformed_body)

    # Always hand the body back, even when untouched: omitting it fails the call.
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayResponse": {"body": transformed_body}},
    }
