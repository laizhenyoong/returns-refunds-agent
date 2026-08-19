"""AgentCore Gateway Lambda target for retrieving return policies from a Bedrock Knowledge Base.

Backs a single tool, `policy_retrieval`, exposed through an AgentCore Gateway Lambda
target. The Knowledge Base ID is read from SSM Parameter Store (parameter name
overridable via KB_ID_PARAMETER_NAME) rather than hardcoded, so the KB can be
redeployed or rotated without changing this function. The region is taken from the
Lambda execution environment.

Gateway invocation contract (see AWS docs "AWS Lambda function targets"):
  - `event` is a flat map of the tool's inputSchema properties (expects a `query`
    property with the policy question/topic to search for).
  - `context.client_context.custom['bedrockAgentCoreToolName']` holds the invoked tool
    name, prefixed with the target name as `${target_name}___${tool_name}`. The prefix
    must be stripped using the `___` delimiter before dispatching.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Any

import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOL_NAME_DELIMITER = "___"
TOOL_NAME = "policy_retrieval"
KB_ID_PARAMETER_NAME = os.environ.get(
    "KB_ID_PARAMETER_NAME", "/app/workshop/kb/knowledge-base-id"
)
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "5"))

_ssm = boto3.client("ssm")
_bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")


@lru_cache(maxsize=1)
def _knowledge_base_id() -> str:
    """Fetch and cache the Knowledge Base ID from SSM Parameter Store."""
    return _ssm.get_parameter(Name=KB_ID_PARAMETER_NAME)["Parameter"]["Value"]


def _extract_tool_name(context: Any) -> str:
    """Extract and strip the target-name prefix from the invoked tool name."""
    tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    _, _, unprefixed = tool_name.partition(TOOL_NAME_DELIMITER)
    return unprefixed or tool_name


def _policy_retrieval(query: str) -> dict[str, Any]:
    response = _bedrock_agent_runtime.retrieve(
        knowledgeBaseId=_knowledge_base_id(),
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": MAX_RESULTS}},
    )
    results = [
        {
            "content": result.get("content", {}).get("text", ""),
            "score": result.get("score"),
            "location": result.get("location"),
        }
        for result in response.get("retrievalResults", [])
    ]
    if not results:
        return {"query": query, "results": [], "message": "No matching policy content found."}
    return {"query": query, "results": results}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    tool_name = _extract_tool_name(context)
    logger.info("Invoked tool: %s, event: %s", tool_name, json.dumps(event))

    if tool_name != TOOL_NAME:
        logger.warning("Unknown tool name: %s", tool_name)
        return {"error": f"Unknown tool '{tool_name}'."}

    query = event.get("query")
    if not query:
        return {"error": f"'query' is required for {TOOL_NAME}."}

    try:
        return _policy_retrieval(query)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the gateway/agent
        logger.exception("Error handling tool '%s'", tool_name)
        return {"error": f"Internal error handling '{tool_name}': {exc}"}
