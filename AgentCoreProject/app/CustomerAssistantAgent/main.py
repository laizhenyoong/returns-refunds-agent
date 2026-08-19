import os
import re
from collections import OrderedDict

from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from strands_tools.current_time import current_time
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

SYSTEM_PROMPT = """
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

# AgentCore Memory gives each user durable, isolated conversation history.
# MEMORY_ID is injected as a runtime env var (see agentcore.json). Without it the
# agent still works, but history is in-process only and lost on restart.
MEMORY_ID = os.environ.get("MEMORY_ID", "").strip()
AWS_REGION = os.environ.get("AWS_REGION") or None

# Must match the namespaceTemplates on the CustomerAssistantMemory resource and the
# namespacePath condition on the runtime role's IAM policy. {actorId} is substituted
# by the session manager at retrieval time.
MEMORY_NAMESPACE = "/users/{actorId}/preference/"
MEMORY_TOP_K = 10
MEMORY_RELEVANCE_SCORE = 0.2

DEFAULT_ACTOR_ID = "anonymous"
DEFAULT_SESSION_ID = "default-session"
MAX_ID_LENGTH = 128
MAX_CACHED_AGENTS = 128

_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]")

# The gateway MCP client exposes the data_lookup Lambda's order_lookup/user_lookup/
# product_lookup tools and the policy_retrieval Lambda's policy_retrieval tool.
# Authentication is handled by GatewayTokenManager (see mcp_client/gateway_auth.py);
# GATEWAY_* env vars are read lazily on first use, not at import time.
gateway_client = get_gateway_mcp_client()
tools = [current_time] + ([gateway_client] if gateway_client else [])

# One Agent per (actor_id, session_id) so each user keeps their own conversation
# history. With MEMORY_ID set, history is durable in AgentCore Memory and restored on
# a cold start, so this cache is only a warm-start optimization. It is bounded with
# LRU eviction so a long-lived process cannot grow without limit.
_agents: OrderedDict[tuple[str, str], Agent] = OrderedDict()


def _sanitize_id(value: object, fallback: str) -> str:
    """Coerce a caller-supplied actor/session id into a safe, non-empty token.

    Callers control these values, so they are restricted to characters that are valid
    in an AgentCore actor/session id and cannot escape the /users/<actor>/preference/
    namespace the runtime role is scoped to.
    """
    if not isinstance(value, str):
        return fallback
    cleaned = _ID_SAFE.sub("-", value.strip())[:MAX_ID_LENGTH].strip("-")
    return cleaned or fallback


def _make_session_manager(actor_id: str, session_id: str) -> AgentCoreMemorySessionManager | None:
    """Build an AgentCore Memory session manager for one actor/session pair."""
    if not MEMORY_ID:
        return None
    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        actor_id=actor_id,
        session_id=session_id,
        retrieval_config={
            MEMORY_NAMESPACE: RetrievalConfig(
                top_k=MEMORY_TOP_K, relevance_score=MEMORY_RELEVANCE_SCORE
            )
        },
        # The entrypoint drives the agent with stream_async, so the per-turn boto3
        # calls are offloaded instead of blocking the event loop.
        async_mode=True,
    )
    return AgentCoreMemorySessionManager(config, region_name=AWS_REGION)


def get_or_create_agent(actor_id: str, session_id: str) -> Agent:
    key = (actor_id, session_id)
    if key in _agents:
        _agents.move_to_end(key)
        return _agents[key]
    if len(_agents) >= MAX_CACHED_AGENTS:
        _agents.popitem(last=False)
    _agents[key] = Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        conversation_manager=NullConversationManager(),
        session_manager=_make_session_manager(actor_id, session_id),
    )
    return _agents[key]


def _extract_prompt(payload: dict) -> str:
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload, context):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    # actor_id identifies the user and selects their memory namespace; session_id
    # scopes one conversation thread for that user. The caller supplies both, and the
    # runtime session id is the fallback so direct invokes still work.
    actor_id = _sanitize_id(payload.get("actor_id"), DEFAULT_ACTOR_ID)
    session_id = _sanitize_id(
        payload.get("session_id") or getattr(context, "session_id", None),
        DEFAULT_SESSION_ID,
    )
    log.info("Invoking agent for actor_id=%s session_id=%s", actor_id, session_id)

    agent = get_or_create_agent(actor_id, session_id)

    async for event in agent.stream_async(_extract_prompt(payload)):
        if not isinstance(event, dict) or "event" not in event:
            continue
        content_block_start = event["event"].get("contentBlockStart")
        if content_block_start is not None and not content_block_start.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
