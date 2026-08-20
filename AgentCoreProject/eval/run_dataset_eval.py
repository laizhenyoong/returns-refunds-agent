"""Run an on-demand dataset evaluation against the deployed Returns & Refunds agent.

Invokes the agent once per dataset scenario, waits for CloudWatch to ingest the
telemetry, then scores each scenario with four evaluators and prints a summary table.

Usage:
    app/CustomerAssistantAgent/.venv/bin/python eval/run_dataset_eval.py

Requires the `bedrock-agentcore` SDK and AWS credentials with permissions for
bedrock-agentcore, bedrock-agentcore-control, and CloudWatch Logs.
"""

import json
import sys
from pathlib import Path

import boto3

try:
    from bedrock_agentcore.evaluation import (
        AgentInvokerInput,
        AgentInvokerOutput,
        CloudWatchAgentSpanCollector,
        EvaluationRunConfig,
        EvaluatorConfig,
        FileDatasetProvider,
        OnDemandEvaluationDatasetRunner,
    )
except ModuleNotFoundError:
    sys.exit(
        "bedrock-agentcore is not installed for this interpreter.\n"
        "Run with the project venv instead:\n"
        "    app/CustomerAssistantAgent/.venv/bin/python eval/run_dataset_eval.py"
    )

REGION = "us-west-2"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTCORE_CONFIG = PROJECT_ROOT / "agentcore" / "agentcore.json"
DEPLOYED_STATE = PROJECT_ROOT / "agentcore" / ".cli" / "deployed-state.json"
DATASET_PATH = PROJECT_ROOT / "eval" / "golden-dataset.json"

# Scored per scenario. Levels differ (SESSION / TRACE / TOOL_CALL); the runner
# handles level-aware targeting, so they can be listed together.
EVALUATORS = {
    "Builtin.GoalSuccessRate": "goal_success",
    "Builtin.Correctness": "correctness",
    "Builtin.ToolSelectionAccuracy": "tool_accuracy",
    "Builtin.TrajectoryAnyOrderMatch": "trajectory_match",
}

ATTENTION_THRESHOLD = 0.5


def resolve_runtime() -> tuple[str, str]:
    """Return the runtime name from the project config and its deployed ARN."""
    runtimes = json.loads(AGENTCORE_CONFIG.read_text())["runtimes"]
    if not runtimes:
        sys.exit(f"No runtimes defined in {AGENTCORE_CONFIG}")
    name = runtimes[0]["name"]

    if not DEPLOYED_STATE.exists():
        sys.exit(f"{DEPLOYED_STATE} not found — run `agentcore deploy` first.")
    deployed = json.loads(DEPLOYED_STATE.read_text())
    resources = deployed["targets"]["default"]["resources"]["runtimes"]
    if name not in resources:
        sys.exit(f"Runtime '{name}' is not deployed — run `agentcore deploy` first.")

    return name, resources[name]["runtimeArn"]


def make_agent_invoker(agent_arn: str):
    """Build the per-turn invoker the runner calls for each dataset turn."""
    client = boto3.client("bedrock-agentcore", region_name=REGION)

    def agent_invoker(invoker_input: AgentInvokerInput) -> AgentInvokerOutput:
        payload = invoker_input.payload
        # The agent entrypoint expects a JSON object with a "prompt" string.
        if isinstance(payload, str):
            payload = {"prompt": payload}
        body = json.dumps(payload).encode()

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=invoker_input.session_id,
            payload=body,
        )
        raw = response["response"].read().decode()
        try:
            return AgentInvokerOutput(agent_output=json.loads(raw))
        except json.JSONDecodeError:
            # The runtime streams text for some responses; keep it as-is.
            return AgentInvokerOutput(agent_output=raw)

    return agent_invoker


def average_score(results: list[dict]) -> float | None:
    """Mean of the `value` fields, ignoring entries the Evaluate API errored on.

    A trace- or tool-level evaluator returns one entry per trace/tool span, so a
    scenario can carry several scores for a single evaluator.
    """
    values = [r["value"] for r in results if r.get("value") is not None]
    return sum(values) / len(values) if values else None


def format_score(score: float | None) -> str:
    return "  -  " if score is None else f"{score:.2f} "


def print_summary(result) -> bool:
    """Print the per-scenario table. Returns True if any scenario needs attention."""
    columns = list(EVALUATORS.values())
    header = f"{'scenario_id':<22}" + "".join(f"{c:>18}" for c in columns) + "   status"
    print("\n" + header)
    print("-" * len(header))

    needs_attention = False

    for scenario in result.scenario_results:
        if scenario.status == "FAILED":
            print(f"{scenario.scenario_id:<22}" + "".join(f"{'  -  ':>18}" for _ in columns) + "   FAILED")
            print(f"    error: {scenario.error}")
            needs_attention = True
            continue

        by_id = {e.evaluator_id: average_score(e.results) for e in scenario.evaluator_results}
        scores = {label: by_id.get(eid) for eid, label in EVALUATORS.items()}

        low = [c for c in columns if scores[c] is not None and scores[c] < ATTENTION_THRESHOLD]
        status = "NEEDS ATTENTION" if low else "ok"
        if low:
            needs_attention = True

        row = f"{scenario.scenario_id:<22}" + "".join(f"{format_score(scores[c]):>18}" for c in columns)
        print(f"{row}   {status}")
        if low:
            print(f"    below {ATTENTION_THRESHOLD}: {', '.join(low)}")

    return needs_attention


def main() -> int:
    runtime_name, agent_arn = resolve_runtime()
    log_group = f"/aws/bedrock-agentcore/runtimes/{agent_arn.rsplit('/', 1)[-1]}-DEFAULT"

    dataset = FileDatasetProvider(str(DATASET_PATH)).get_dataset()

    print(f"Runtime:  {runtime_name}")
    print(f"Dataset:  {DATASET_PATH.name} ({len(dataset.scenarios)} scenarios)")
    print(f"Region:   {REGION}")
    print("\nInvoking agent, waiting for span ingestion, then evaluating...")

    result = OnDemandEvaluationDatasetRunner(region=REGION).run(
        config=EvaluationRunConfig(
            evaluator_config=EvaluatorConfig(evaluator_ids=list(EVALUATORS)),
        ),
        dataset=dataset,
        agent_invoker=make_agent_invoker(agent_arn),
        span_collector=CloudWatchAgentSpanCollector(log_group_name=log_group, region=REGION),
    )

    needs_attention = print_summary(result)

    out_path = PROJECT_ROOT / "eval" / "dataset-eval-results.json"
    out_path.write_text(result.model_dump_json(indent=2))
    print(f"\nFull results: {out_path}")

    return 1 if needs_attention else 0


if __name__ == "__main__":
    raise SystemExit(main())
