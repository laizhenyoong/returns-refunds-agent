"""AgentCore Gateway Lambda target for retrieving return policies from a Bedrock Knowledge Base.

Backs a single tool, `policy_retrieval`, exposed through an AgentCore Gateway
Lambda target. The Knowledge Base ID is read from SSM Parameter Store at
`/app/workshop/kb/knowledge-base-id` rather than hardcoded, so the KB can be
redeployed/rotated without touching this function's code or configuration.

Gateway invocation contract (see AWS docs "AWS Lambda function targets"):
  - `event` is a flat map of the tool's inputSchema properties (expects a
    `query` property with the policy question/topic to search for).
  - `context.client_context.custom['bedrockAgentCoreToolName']` holds the
    invoked tool name, prefixed with the target name as `${target_name}___${tool_name}`.
    The prefix must be stripped using the `___` delimiter before dispatching.
"""

import json
import logging
from typing import Any

import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION = "us-west-2"
TOOL_NAME_DELIMITER = "___"
KB_ID_PARAMETER_NAME = "/app/workshop/kb/knowledge-base-id"
DEFAULT_MAX_RESULTS = 5

_ssm_client = boto3.client("ssm", region_name=REGION)
_bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=REGION)

_cached_kb_id: str | None = None


def _get_knowledge_base_id() -> str:
    """Fetch and cache the Knowledge Base ID from SSM Parameter Store."""
    global _cached_kb_id
    if _cached_kb_id is None:
        response = _ssm_client.get_parameter(Name=KB_ID_PARAMETER_NAME)
        _cached_kb_id = response["Parameter"]["Value"]
    return _cached_kb_id


def _extract_tool_name(context: Any) -> str:
    """Extract and strip the target-name prefix from the invoked tool name."""
    custom = context.client_context.custom
    original_tool_name = custom["bedrockAgentCoreToolName"]

    if TOOL_NAME_DELIMITER in original_tool_name:
        return original_tool_name[
            original_tool_name.index(TOOL_NAME_DELIMITER) + len(TOOL_NAME_DELIMITER):
        ]
    return original_tool_name


def _policy_retrieval(event: dict[str, Any]) -> dict[str, Any]:
    query = event.get("query")

    if not query:
        return {"error": "'query' is required for policy_retrieval."}

    knowledge_base_id = _get_knowledge_base_id()

    response = _bedrock_agent_runtime_client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": DEFAULT_MAX_RESULTS}
        },
    )

    results = []
    for result in response.get("retrievalResults", []):
        results.append(
            {
                "content": result.get("content", {}).get("text", ""),
                "score": result.get("score"),
                "location": result.get("location"),
            }
        )

    if not results:
        return {"query": query, "results": [], "message": "No matching policy content found."}

    return {"query": query, "results": results}


_TOOL_DISPATCH = {
    "policy_retrieval": _policy_retrieval,
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
