"""AgentCore Gateway REQUEST interceptor that serves repeated tool calls from cache.

Runs before the gateway forwards a call to its target. On a cache hit it returns
the stored response directly, short-circuiting the request: the target Lambda is
never invoked, so a repeated knowledge-base lookup costs a DynamoDB read instead
of a Bedrock Retrieve.

The cache is written by the RESPONSE interceptor, which derives the same key from
the same request. Nothing is coordinated between the two functions beyond
`cache_key`, so both must build it identically — see `cache_key` in `shared`.

Only read-only tools are cacheable (see CACHEABLE_TOOLS). Never cache a tool with
side effects: a short-circuited call skips the target entirely, so a cached
`process_refund` would return a stale confirmation without processing anything.

Gateway invocation contract, observed from live REQUEST interceptions:

    {
      "interceptorInputVersion": "1.0",
      "mcp": {
        "gatewayRequest":    {"path", "httpMethod", "headers", "body", "context"},
        "gatewayResponse":   null,
        "rawGatewayRequest": {"body": "<original JSON text>"}
      }
    }

Two reply shapes are valid, and the gateway rejects anything else with
`InterceptorException - Received invalid response from interceptor`:

    pass through:  {"mcp": {"transformedGatewayRequest":  {"body": ...}}}
    short-circuit: {"mcp": {"transformedGatewayResponse": {"statusCode": 200,
                                                           "body": ...}}}

`transformedGatewayResponse` requires `statusCode` here and rejects `headers` or
`isStreamingResponse` — the mirror of the RESPONSE point, which rejects
`statusCode`. Both must be nested under `mcp`.
"""

import hashlib
import json
import logging
import os
import time
from typing import Any

import boto3

# The Lambda runtime configures the root logger before this module is imported,
# so basicConfig is a no-op here and INFO records would be dropped at WARNING.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OUTPUT_VERSION = "1.0"
CACHE_TABLE = os.environ.get("CACHE_TABLE", "workshop-interceptor-cache")
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

# Read-only tools only. Anything that writes must reach its target every time.
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
    """Stable key for a tool call. Must match the RESPONSE interceptor's key."""
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{tool_name}\n{canonical}".encode()).hexdigest()
    return f"{tool_name}#{digest[:32]}"


def _tool_call(body: Any) -> tuple[str, Any] | None:
    """Return (tool_name, arguments) if the body is a cacheable tools/call."""
    if not isinstance(body, dict) or body.get("method") != "tools/call":
        return None
    params = body.get("params") or {}
    name = params.get("name")
    if name not in CACHEABLE_TOOLS:
        return None
    return name, params.get("arguments")


def _lookup(key: str) -> Any | None:
    """Return the cached response body, or None on miss or expiry."""
    try:
        item = _table.get_item(Key={"cache_key": key}).get("Item")
    except Exception:  # noqa: BLE001 - a cache failure must not fail the call
        logger.exception("Cache read failed for %s; falling through to target.", key)
        return None

    if not item:
        return None
    # The table has no TTL enabled, so expiry is enforced here on read.
    if int(item.get("expires_at", 0)) <= int(time.time()):
        logger.info("Cache entry expired: %s", key)
        return None
    return json.loads(item["body"])


def _pass_through(body: Any) -> dict[str, Any]:
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayRequest": {"body": body}},
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    body = ((event.get("mcp") or {}).get("gatewayRequest") or {}).get("body")

    call = _tool_call(body)
    if call is None:
        return _pass_through(body)

    tool_name, arguments = call
    key = cache_key(tool_name, arguments)
    cached = _lookup(key)

    if cached is None:
        logger.info("Cache MISS for %s; forwarding to target.", tool_name)
        return _pass_through(body)

    # Reuse the stored payload but adopt this request's JSON-RPC id, or the
    # client will discard the reply as unsolicited.
    cached["id"] = body.get("id")
    logger.info("Cache HIT for %s; target not invoked.", tool_name)
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayResponse": {"statusCode": 200, "body": cached}},
    }
