"""AgentCore Gateway Lambda target for order, customer, and product lookups.

Backs four tools exposed through an AgentCore Gateway Lambda target:
  - order_lookup:            look up an order by customer_id + product_id
  - user_lookup:             look up a customer by customer_id
  - product_lookup:          look up a product by product_id
  - find_returned_products:  list all RETURNED orders, enriched with product names

Table names come from the CUSTOMERS_TABLE / ORDERS_TABLE / PRODUCTS_TABLE env vars
and fall back to the workshop table names. The region is taken from the Lambda
execution environment.

Gateway invocation contract (see AWS docs "AWS Lambda function targets"):
  - `event` is a flat map of the tool's inputSchema properties.
  - `context.client_context.custom['bedrockAgentCoreToolName']` holds the invoked tool
    name, prefixed with the target name as `${target_name}___${tool_name}`. The prefix
    must be stripped using the `___` delimiter before dispatching.
"""

import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_NAME_DELIMITER = "___"

CUSTOMERS_TABLE = os.environ.get("CUSTOMERS_TABLE", "workshop-customers")
ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "workshop-orders")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "workshop-products")

_dynamodb = boto3.resource("dynamodb")


def _decimal_default(value: Any) -> Any:
    """JSON-serialize DynamoDB Decimal values as int/float."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def _get_item(table_name: str, key: dict[str, str]) -> dict[str, Any]:
    """Fetch one item by key and return it as a JSON-safe dict, or an error dict."""
    item = _dynamodb.Table(table_name).get_item(Key=key).get("Item")
    if not item:
        return {"error": f"No item found in {table_name} for {key}."}
    return json.loads(json.dumps(item, default=_decimal_default))


def _require(event: dict[str, Any], *names: str) -> dict[str, str]:
    """Return the named event values, raising if any are missing."""
    values = {name: event.get(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"Missing required input: {', '.join(missing)}.")
    return values


def _order_lookup(event: dict[str, Any]) -> dict[str, Any]:
    return _get_item(ORDERS_TABLE, _require(event, "customer_id", "product_id"))


def _user_lookup(event: dict[str, Any]) -> dict[str, Any]:
    return _get_item(CUSTOMERS_TABLE, _require(event, "customer_id"))


def _product_lookup(event: dict[str, Any]) -> dict[str, Any]:
    return _get_item(PRODUCTS_TABLE, _require(event, "product_id"))


def _product_names(product_ids: set[str]) -> dict[str, str]:
    """Return a product_id -> product_name map, fetched in a single batch read."""
    # One BatchGetItem instead of a get_item per order. The workshop table is well
    # under the 100-key limit, so unprocessed keys don't need handling.
    if not product_ids:
        return {}
    keys = [{"product_id": pid} for pid in product_ids]
    response = _dynamodb.batch_get_item(RequestItems={PRODUCTS_TABLE: {"Keys": keys}})
    products = response["Responses"][PRODUCTS_TABLE]
    return {p["product_id"]: p.get("product_name") for p in products}


def _find_returned_products(event: dict[str, Any]) -> dict[str, Any]:
    """List all orders with status RETURNED, each enriched with its product name."""
    # No index on `status`, so filter with a scan. `status` is a DynamoDB reserved
    # word, hence Attr() rather than an inline expression. A single scan page covers
    # the small workshop table.
    orders = _dynamodb.Table(ORDERS_TABLE).scan(
        FilterExpression=Attr("status").eq("RETURNED")
    )["Items"]

    names = _product_names({order["product_id"] for order in orders})
    for order in orders:
        order["product_name"] = names.get(order["product_id"])

    result = {"returned_products": orders, "count": len(orders)}
    return json.loads(json.dumps(result, default=_decimal_default))


_TOOL_DISPATCH = {
    "order_lookup": _order_lookup,
    "user_lookup": _user_lookup,
    "product_lookup": _product_lookup,
    "find_returned_products": _find_returned_products,
}


def _extract_tool_name(context: Any) -> str:
    """Extract and strip the target-name prefix from the invoked tool name."""
    tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    _, _, unprefixed = tool_name.partition(TOOL_NAME_DELIMITER)
    return unprefixed or tool_name


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    tool_name = _extract_tool_name(context)
    logger.info("Invoked tool: %s, event: %s", tool_name, json.dumps(event))

    handler = _TOOL_DISPATCH.get(tool_name)
    if handler is None:
        logger.warning("Unknown tool name: %s", tool_name)
        return {"error": f"Unknown tool '{tool_name}'."}

    try:
        return handler(event)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the gateway/agent
        logger.exception("Error handling tool '%s'", tool_name)
        return {"error": f"Internal error handling '{tool_name}': {exc}"}
