import os
import re
from collections import OrderedDict
from typing import Any

from strands import Agent, tool
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from strands_tools.current_time import current_time as get_current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from model.load import load_model
from mcp_client.client import get_gateway_mcp_client

app = BedrockAgentCoreApp()
log = app.logger

# Define a Streamable HTTP MCP Client connected to the AgentCore Gateway.
# The gateway exposes the data_lookup Lambda's order_lookup/user_lookup/product_lookup
# tools and the policy_retrieval Lambda's policy_retrieval tool. Authentication is
# handled internally by GatewayTokenManager (see mcp_client/gateway_auth.py), which
# obtains and caches a Cognito client_credentials JWT and auto-refreshes it before
# expiry. GATEWAY_* env vars are read lazily on first use, not at import time, so the
# module can still be imported (e.g. for tests) without them set.
mcp_clients = [get_gateway_mcp_client()]

DEFAULT_SYSTEM_PROMPT = """
You are the Returns & Refunds Assistant. Introduce yourself as such when greeting the user.

You are speaking with an administrator, not a customer. The administrator has access to
customer data, order records, and return policies, and uses you to help manage returns and
refunds on behalf of customers. Your job is to:
- Check whether an order or item is eligible for return based on return policies
- Calculate refund amounts for returns
- Answer questions about return policies

Be helpful and concise. Always confirm the relevant details (order/item, reason for return,
policy terms, and calculated refund amount) with the administrator before processing any
return or refund. Use tools when appropriate.

"""


# Define a collection of tools used by the model
tools = []

_INLINE_FUNCTION_NAMES = set()

# Define a simple function tool
@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a+b
tools.append(add_numbers)

# Register the Strands built-in current_time tool
tools.append(get_current_time)


# Add MCP client to tools if available. The gateway client discovers and exposes
# order_lookup, user_lookup, product_lookup, and policy_retrieval as callable tools.
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)


def _make_conversation_manager():
    return NullConversationManager()


# AgentCore Memory gives each user durable, isolated conversation history.
# MEMORY_ID is injected as a runtime env var (see agentcore.json). When it is
# absent — e.g. plain local runs or unit tests — the agent still works, but
# history is in-process only and lost on restart.
MEMORY_ID = os.environ.get("MEMORY_ID", "").strip()
MEMORY_REGION = os.environ.get("AWS_REGION", "us-west-2")

# Must match the namespaceTemplates on the CustomerAssistantMemory resource and
# the namespacePath condition on the runtime role's IAM policy. {actorId} is
# substituted by the session manager at retrieval time.
MEMORY_NAMESPACE = "/users/{actorId}/preference/"

DEFAULT_ACTOR_ID = "anonymous"
_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize_id(value: Any, fallback: str) -> str:
    """Coerce a caller-supplied actor/session id into a safe, non-empty token.

    Callers control these values, so they are restricted to characters that are
    valid in an AgentCore actor/session id and cannot escape the
    /users/<actor>/preference/ namespace the runtime role is scoped to.
    """
    if not isinstance(value, str):
        return fallback
    cleaned = _ID_SAFE.sub("-", value.strip())[:128].strip("-")
    return cleaned or fallback


def _make_session_manager(actor_id: str, session_id: str):
    """Build an AgentCore Memory session manager for one actor/session pair."""
    if not MEMORY_ID:
        return None
    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        actor_id=actor_id,
        session_id=session_id,
        retrieval_config={MEMORY_NAMESPACE: RetrievalConfig(top_k=10, relevance_score=0.2)},
        # The entrypoint drives the agent with stream_async, so the per-turn
        # boto3 calls are offloaded instead of blocking the event loop.
        async_mode=True,
    )
    return AgentCoreMemorySessionManager(config, region_name=MEMORY_REGION)


# Reuses one Agent per (actor_id, session_id) so each user keeps their own
# conversation history. With MEMORY_ID set, history is durable in AgentCore
# Memory and is restored on a cold start or after re-login; the cache is only a
# warm-start optimization. The cache is bounded to 128 entries with LRU eviction
# so a single process serving many sessions cannot leak history between them or
# grow without limit.
def agent_factory():
    cache = OrderedDict()
    def get_or_create_agent(actor_id, session_id):
        key = (actor_id, session_id)
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[key] = Agent(
            model=load_model(),
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            tools=tools,
            conversation_manager=_make_conversation_manager(),
            session_manager=_make_session_manager(actor_id, session_id),
            hooks=[
            ],
        )
        return cache[key]
    return get_or_create_agent
get_or_create_agent = agent_factory()


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise ValueError("each message content value must be a list of content blocks")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError("tool_results must contain objects with a toolUseId string")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


def _has_inline_function_call(messages) -> bool:
    """Return True if messages contains an assistant toolUse for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """Check if a contentBlockStart event is for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES



@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    # actor_id identifies the user and selects their memory namespace; session_id
    # scopes one conversation thread for that user. The caller supplies both, and
    # the runtime session id is the fallback so direct invokes still work.
    actor_id = _sanitize_id(payload.get("actor_id"), DEFAULT_ACTOR_ID)
    session_id = _sanitize_id(
        payload.get("session_id") or getattr(context, "session_id", None),
        "default-session",
    )
    log.info("Resolved actor_id=%s session_id=%s", actor_id, session_id)

    agent = get_or_create_agent(actor_id, session_id)

    prompt = _extract_prompt(payload)


    async for event in agent.stream_async(
        prompt,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
