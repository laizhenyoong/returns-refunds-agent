import os

from strands.models.bedrock import BedrockModel

DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"


def load_model() -> BedrockModel:
    """Get a Bedrock model client using IAM credentials.

    Override the model with the MODEL_ID env var (see envVars in agentcore.json).
    """
    return BedrockModel(model_id=os.environ.get("MODEL_ID") or DEFAULT_MODEL_ID)
