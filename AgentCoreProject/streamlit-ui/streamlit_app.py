"""Streamlit chat UI for the Returns & Refunds Assistant.

Authentication is handled by the workshop Cognito User Pool (see
../cognito_config.json). Chat messages are forwarded to the deployed AgentCore
Runtime agent recorded in ../agentcore/.cli/deployed-state.json.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Iterator

import boto3
import streamlit as st
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-west-2"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COGNITO_CONFIG_PATH = PROJECT_ROOT / "cognito_config.json"
DEPLOYED_STATE_PATH = PROJECT_ROOT / "agentcore" / ".cli" / "deployed-state.json"
RUNTIME_NAME = "CustomerAssistantAgent"

# Workshop convenience defaults for the login form.
DEFAULT_USERNAME = "administrator@example.com"
DEFAULT_PASSWORD = "Workshop1!"

WELCOME_MESSAGE = (
    "Hello! I'm your Returns & Refunds Assistant. I can help you look up orders, "
    "check return eligibility, calculate refunds and answer policy questions. "
    "How can I help you today?"
)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_cognito_config() -> dict[str, str]:
    """Read User Pool ID and app client ID from the project's Cognito config."""
    if not COGNITO_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Cognito config not found at {COGNITO_CONFIG_PATH}")
    config = json.loads(COGNITO_CONFIG_PATH.read_text())

    # Prefer the UI (public, USER_PASSWORD_AUTH) client. The `client_id` entry is
    # the gateway machine-to-machine client and only supports client_credentials.
    client_id = config.get("ui_client_id")
    if not client_id:
        raise KeyError(
            "No 'ui_client_id' in cognito_config.json. Create a public app client "
            "with ALLOW_USER_PASSWORD_AUTH and record its ID under 'ui_client_id'."
        )
    return {
        "user_pool_id": config["user_pool_id"],
        "client_id": client_id,
        "region": config.get("region", REGION),
    }


@st.cache_data(show_spinner=False)
def load_agent_runtime_arn() -> str:
    """Read the deployed AgentCore Runtime ARN from the CLI deployed state."""
    if not DEPLOYED_STATE_PATH.exists():
        raise FileNotFoundError(
            f"Deployed state not found at {DEPLOYED_STATE_PATH}. Run 'agentcore deploy' first."
        )
    state = json.loads(DEPLOYED_STATE_PATH.read_text())
    targets = state.get("targets", {})
    for target in targets.values():
        runtimes = target.get("resources", {}).get("runtimes", {})
        runtime = runtimes.get(RUNTIME_NAME) or next(iter(runtimes.values()), None)
        if runtime and runtime.get("runtimeArn"):
            return runtime["runtimeArn"]
    raise KeyError(f"No deployed runtime ARN found in {DEPLOYED_STATE_PATH}")


# --------------------------------------------------------------------------- #
# AWS clients
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def cognito_client():
    return boto3.client("cognito-idp", region_name=REGION)


@st.cache_resource(show_spinner=False)
def agentcore_client():
    # Agent calls fan out to memory, gateway and Knowledge Base, so allow a
    # generous read timeout before giving up on the stream.
    return boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(read_timeout=300, connect_timeout=15, retries={"max_attempts": 2}),
    )


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
def sign_in(username: str, password: str) -> None:
    """Run USER_PASSWORD_AUTH and store tokens (or a pending challenge) in state."""
    cfg = load_cognito_config()
    response = cognito_client().initiate_auth(
        ClientId=cfg["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )

    if response.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        st.session_state.challenge = {
            "name": "NEW_PASSWORD_REQUIRED",
            "session": response["Session"],
            "username": username,
        }
        return

    if "AuthenticationResult" not in response:
        raise RuntimeError(
            f"Unsupported Cognito challenge: {response.get('ChallengeName', 'unknown')}"
        )

    _store_tokens(username, response["AuthenticationResult"])


def complete_new_password(new_password: str) -> None:
    """Answer the NEW_PASSWORD_REQUIRED challenge for a first-time login."""
    cfg = load_cognito_config()
    challenge = st.session_state.challenge
    response = cognito_client().respond_to_auth_challenge(
        ClientId=cfg["client_id"],
        ChallengeName="NEW_PASSWORD_REQUIRED",
        Session=challenge["session"],
        ChallengeResponses={
            "USERNAME": challenge["username"],
            "NEW_PASSWORD": new_password,
        },
    )

    if "AuthenticationResult" not in response:
        raise RuntimeError(
            f"Unexpected follow-up challenge: {response.get('ChallengeName', 'unknown')}"
        )

    _store_tokens(challenge["username"], response["AuthenticationResult"])
    st.session_state.challenge = None


def _store_tokens(username: str, auth_result: dict[str, Any]) -> None:
    st.session_state.tokens = {
        "access_token": auth_result["AccessToken"],
        "id_token": auth_result["IdToken"],
        "refresh_token": auth_result.get("RefreshToken"),
    }
    st.session_state.user_email = username
    # actor_id is the local part of the email, matching the seeded memory actors.
    st.session_state.actor_id = username.split("@")[0]
    # runtimeSessionId must be at least 33 characters; a uuid4 hex is 32.
    st.session_state.session_id = f"ui-{uuid.uuid4().hex}"
    st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]


def sign_out() -> None:
    for key in ("tokens", "user_email", "actor_id", "session_id", "messages", "challenge"):
        st.session_state.pop(key, None)


def is_authenticated() -> bool:
    return bool(st.session_state.get("tokens"))


# --------------------------------------------------------------------------- #
# Agent invocation
# --------------------------------------------------------------------------- #
def _text_from_event(value: Any) -> str:
    """Pull display text out of one decoded stream chunk.

    The agent yields Strands stream events, so text arrives inside
    event.contentBlockDelta.delta.text. Plain strings are passed through.
    """
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    event = value.get("event", value)
    if isinstance(event, dict):
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            return delta["text"]
    # Non-streaming fallbacks used by some agent responses.
    for key in ("result", "response", "output", "text"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            return candidate
    return ""


def stream_agent_response(prompt: str) -> Iterator[str]:
    """Invoke the deployed agent and yield response text as it arrives."""
    payload = json.dumps(
        {
            "prompt": prompt,
            "actor_id": st.session_state.actor_id,
            "session_id": st.session_state.session_id,
        }
    ).encode("utf-8")

    response = agentcore_client().invoke_agent_runtime(
        agentRuntimeArn=load_agent_runtime_arn(),
        runtimeSessionId=st.session_state.session_id,
        qualifier="DEFAULT",
        payload=payload,
    )

    content_type = response.get("contentType", "")
    body = response["response"]

    if "text/event-stream" in content_type:
        for raw_line in body.iter_lines(chunk_size=64):
            if not raw_line:
                continue
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:") :].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                # Parse JSON first so quoted strings lose their extra quotes.
                text = _text_from_event(json.loads(chunk))
            except json.JSONDecodeError:
                text = chunk
            if text:
                yield text
        return

    # Non-streaming response: buffer, then emit whatever text we can find.
    raw = b"".join(body).decode("utf-8") if not isinstance(body, bytes) else body.decode("utf-8")
    try:
        yield _text_from_event(json.loads(raw)) or raw
    except json.JSONDecodeError:
        yield raw


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
def render_login() -> None:
    st.title("Returns & Refunds Assistant")

    challenge = st.session_state.get("challenge")
    if challenge and challenge["name"] == "NEW_PASSWORD_REQUIRED":
        st.info(f"First login for {challenge['username']}. Please set a new password.")
        with st.form("new_password_form"):
            new_password = st.text_input("New password", type="password")
            confirm = st.text_input("Confirm new password", type="password")
            submitted = st.form_submit_button("Set New Password")
        if submitted:
            if len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    complete_new_password(new_password)
                    st.rerun()
                except (ClientError, BotoCoreError, RuntimeError) as exc:
                    st.error(f"Could not set new password: {exc}")
        if st.button("Back to login"):
            st.session_state.challenge = None
            st.rerun()
        return

    st.subheader("Sign in")
    with st.form("login_form"):
        email = st.text_input("Email", value=DEFAULT_USERNAME)
        password = st.text_input("Password", value=DEFAULT_PASSWORD, type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        try:
            sign_in(email.strip(), password)
            st.rerun()
        except cognito_client().exceptions.NotAuthorizedException:
            st.error("Incorrect email or password.")
        except cognito_client().exceptions.UserNotFoundException:
            st.error("User not found in the Cognito User Pool.")
        except (ClientError, BotoCoreError, RuntimeError) as exc:
            st.error(f"Login failed: {exc}")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("**Signed in as**")
        st.write(st.session_state.user_email)
        st.markdown("**Session ID**")
        st.code(st.session_state.session_id, language=None)
        st.markdown("**Actor ID**")
        st.code(st.session_state.actor_id, language=None)
        if st.button("Log out", use_container_width=True):
            sign_out()
            st.rerun()


def render_chat() -> None:
    st.title("Returns & Refunds Assistant")
    render_sidebar()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about orders, returns, refunds or policies...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(stream_agent_response(prompt))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            reply = f"Agent invocation failed ({code}): {exc.response.get('Error', {}).get('Message', exc)}"
            st.error(reply)
        except (BotoCoreError, OSError) as exc:
            reply = f"Could not reach the agent (connection or timeout error): {exc}"
            st.error(reply)

    if isinstance(reply, list):
        reply = "".join(str(part) for part in reply)
    st.session_state.messages.append({"role": "assistant", "content": reply or "(no response)"})


def main() -> None:
    st.set_page_config(page_title="Returns & Refunds Assistant", page_icon="📦")

    try:
        load_cognito_config()
        load_agent_runtime_arn()
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        st.error(f"Configuration problem: {exc}")
        st.stop()

    st.session_state.setdefault("challenge", None)

    if is_authenticated():
        render_chat()
    else:
        render_login()


if __name__ == "__main__":
    main()
