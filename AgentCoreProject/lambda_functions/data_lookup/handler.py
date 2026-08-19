"""AgentCore Gateway Lambda target for order, customer, and product lookups.

Backs three tools exposed through an AgentCore Gateway Lambda target:
  - order_lookup:   look up an order by customer_id + product_id in workshop-orders
  - user_lookup:    look up a customer by customer_id in workshop-customers
  - product_lookup: look up a product by product_id in workshop-products

Gateway invocation contract (see AWS docs "AWS Lambda function targets"):
  - `event` is a flat map of the tool's inputSchema properties.
  - `context.client_context.custom['bedrockAgentCoreToolName']` holds the
    invoked tool name, prefixed with the target name as `${target_name}___${tool_name}`.
    The prefix must be stripped using the `___` delimiter before dispatching.
"""

import json
import logging
from decimal import Decimal
from typing import Any

import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION = "us-west-2"
TOOL_NAME_DELIMITER = "___"

CUSTOMERS_TABLE = "workshop-customers"
ORDERS_TABLE = "workshop-orders"
PRODUCTS_TABLE = "workshop-products"

_dynamodb = boto3.resource("dynamodb", region_name=REGION)


def _decimal_default(value: Any) -> Any:
    """JSON-serialize DynamoDB Decimal values as int/float."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def _to_json_safe(item: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(item, default=_decimal_default))


def _extract_tool_name(context: Any) -> str:
    """Extract and strip the target-name prefix from the invoked tool name."""
    custom = context.client_context.custom
    original_tool_name = custom["bedrockAgentCoreToolName"]

    if TOOL_NAME_DELIMITER in original_tool_name:
        return original_tool_name[
            original_tool_name.index(TOOL_NAME_DELIMITER) + len(TOOL_NAME_DELIMITER):
        ]
    return original_tool_name


def _order_lookup(event: dict[str, Any]) -> dict[str, Any]:
    customer_id = event.get("customer_id")
    product_id = event.get("product_id")

    if not customer_id or not product_id:
        return {"error": "Both 'customer_id' and 'product_id' are required for order_lookup."}

    table = _dynamodb.Table(ORDERS_TABLE)
    response = table.get_item(Key={"customer_id": customer_id, "product_id": product_id})
    item = response.get("Item")

    if not item:
        return {"error": f"No order found for customer_id={customer_id}, product_id={product_id}."}

    return _to_json_safe(item)


def _user_lookup(event: dict[str, Any]) -> dict[str, Any]:
    customer_id = event.get("customer_id")

    if not customer_id:
        return {"error": "'customer_id' is required for user_lookup."}

    table = _dynamodb.Table(CUSTOMERS_TABLE)
    response = table.get_item(Key={"customer_id": customer_id})
    item = response.get("Item")

    if not item:
        return {"error": f"No customer found for customer_id={customer_id}."}

    return _to_json_safe(item)


def _product_lookup(event: dict[str, Any]) -> dict[str, Any]:
    product_id = event.get("product_id")

    if not product_id:
        return {"error": "'product_id' is required for product_lookup."}

    table = _dynamodb.Table(PRODUCTS_TABLE)
    response = table.get_item(Key={"product_id": product_id})
    item = response.get("Item")

    if not item:
        return {"error": f"No product found for product_id={product_id}."}

    return _to_json_safe(item)


_TOOL_DISPATCH = {
    "order_lookup": _order_lookup,
    "user_lookup": _user_lookup,
    "product_lookup": _product_lookup,
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    tool_name = _extract_tool_name(context)
    logger.info("Invoked tool: %s, event: %s", tool_name, json.dumps(event))

    handler = _TOOL_DISPATCH.get(tool_name)
    if handler is None:
        logger.warning("Unknown tool name: %s", tool_name)
        return {"error": f"Unknown tool '{tool_name}'."}

    try:
        return handler(event)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the gateway/agent
        logger.exception("Error handling tool '%s'", tool_name)
        return {"error": f"Internal error handling '{tool_name}': {exc}"}
