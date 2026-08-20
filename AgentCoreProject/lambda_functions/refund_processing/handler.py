"""AgentCore Gateway Lambda target for mock refund processing.

Backs a single tool, `process_refund`, exposed through an AgentCore Gateway Lambda
target. Nothing is actually refunded: no payment provider is called and no data
store is written to. The function returns a synthetic confirmation so refund
policies and agent workflows can be exercised end to end without side effects.

Gateway invocation contract (see AWS docs "AWS Lambda function targets"):
  - `event` is a flat map of the tool's inputSchema properties (expects `order_id`,
    `amount`, and `reason`).
  - `context.client_context.custom['bedrockAgentCoreToolName']` holds the invoked tool
    name, prefixed with the target name as `${target_name}___${tool_name}`. The prefix
    must be stripped using the `___` delimiter before dispatching.
"""

import json
import logging
import random
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_NAME_DELIMITER = "___"
TOOL_NAME = "process_refund"


def _extract_tool_name(context: Any) -> str:
    """Extract and strip the target-name prefix from the invoked tool name."""
    tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    _, _, unprefixed = tool_name.partition(TOOL_NAME_DELIMITER)
    return unprefixed or tool_name


def _require(event: dict[str, Any], *names: str) -> dict[str, Any]:
    """Return the named event values, raising if any are missing."""
    values = {name: event.get(name) for name in names}
    missing = [name for name, value in values.items() if value in (None, "")]
    if missing:
        raise ValueError(f"Missing required input: {', '.join(missing)}.")
    return values


def _process_refund(event: dict[str, Any]) -> dict[str, Any]:
    """Return a mock refund confirmation. No refund is actually issued."""
    values = _require(event, "order_id", "amount", "reason")
    order_id, reason = values["order_id"], values["reason"]
    try:
        amount = int(values["amount"])
    except (TypeError, ValueError):
        raise ValueError(f"'amount' must be a whole number of dollars, got {values['amount']!r}.")

    confirmation_id = f"REF-{random.randint(100000, 999999)}"
    return {
        "refunded": True,
        "mock": True,
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "confirmation_id": confirmation_id,
        "message": (
            f"Refund of ${amount} processed for order {order_id}. "
            f"Reason: {reason}. Confirmation ID: {confirmation_id}"
        ),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    tool_name = _extract_tool_name(context)
    logger.info("Invoked tool: %s, event: %s", tool_name, json.dumps(event))

    if tool_name != TOOL_NAME:
        logger.warning("Unknown tool name: %s", tool_name)
        return {"error": f"Unknown tool '{tool_name}'."}

    try:
        return _process_refund(event)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the gateway/agent
        logger.exception("Error handling tool '%s'", tool_name)
        return {"error": f"Internal error handling '{tool_name}': {exc}"}
