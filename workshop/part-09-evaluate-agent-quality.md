# Part 9: Evaluate Agent Quality with AgentCore Evaluations

**Estimated time:** ~30 minutes

You've deployed a production agent, wired up memory and a gateway, added a UI, and
explored logs and traces. But how do you know the agent is actually doing a good
job? Are refund calculations correct? Does it call the right tools? Does it
hallucinate policy details?

AgentCore Evaluations answers these questions by scoring agent sessions against
measurable criteria. It uses LLM-as-a-Judge techniques (where a separate model
grades agent behavior) alongside programmatic checks, and writes the results back
to CloudWatch so you can track quality over time.

In this part you'll set up all three evaluation modes for your Returns & Refunds
agent:

- **On-demand evaluation** to score a single session and verify the agent works
  correctly
- A **custom evaluator** tailored to your return-policy domain
- **Online evaluation** to continuously monitor production quality
- **Batch evaluation** with a golden dataset to run regression tests

> **Prerequisites:** You must have completed Parts 1-6 with a fully deployed agent.
> Part 6 (Observability) is required because evaluations read trace data from
> CloudWatch. Make sure you're in your agent project directory
> (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

> **Transaction Search:** Evaluations depend on CloudWatch Transaction Search,
> which the workshop CloudFormation template already enabled. If you deployed your
> agent fewer than 10 minutes ago, wait for traces to become indexed before
> proceeding.

---

## The Five-Axis Quality Framework

Before writing evaluation configs, it helps to have a mental model for what
"quality" means for an AI agent. AgentCore's built-in evaluators map to five
quality axes:

| Axis | What it measures | Built-in evaluators |
|---|---|---|
| Task success | Does the agent accomplish the user's goal over the full conversation? | `Builtin.GoalSuccessRate` (session-level) |
| Faithfulness and correctness | Are statements supported by retrieved information and factually accurate? | `Builtin.Correctness`, `Builtin.Faithfulness`, `Builtin.Coherence` |
| Safety and policy compliance | Does the agent avoid harmful content, PII leakage, or disallowed actions? | `Builtin.Harmfulness`, `Builtin.Stereotyping`, `Builtin.Refusal` |
| Tooling behavior | Does the agent choose the right tools with correct parameters? | `Builtin.ToolSelectionAccuracy`, `Builtin.ToolParameterAccuracy`, trajectory evaluators |
| Cost and latency | Are response times and token usage within acceptable bounds? | CloudWatch metrics from AgentCore Observability (not evaluator-based) |

The first four axes are evaluated by LLM judges or programmatic checks. The fifth
(cost/latency) is already visible in your GenAI Observability dashboard from Part 6.
Evaluations focus on the quality dimensions that metrics alone cannot capture.

## Step 1: Generate Test Traffic

Evaluations need sessions to score. Generate a few representative conversations so
there's trace data available for the evaluator to read.

💻 **Terminal Command:**

```bash
agentcore invoke
```

Run these prompts one at a time in the invoke session:

💬 **Agent Test Prompt:**

```
Look up customer C-01 and tell me their most recent order. Is it eligible for return?
```

💬 **Agent Test Prompt:**

```
What is the return policy for electronics in India? Calculate the refund for a $299.99 item returned on day 5 of a 30-day window with a 15% restocking fee.
```

💬 **Agent Test Prompt:**

```
Customer C-02 wants to return order ORD-002. Look up the order, check the return policy for their country, and tell me if the return is eligible.
```

Exit the invoke session with <kbd>Ctrl+C</kbd> after the third prompt completes.
Wait 1-2 minutes for traces to propagate to CloudWatch before continuing.

## Step 2: Run an On-Demand Evaluation

On-demand evaluation scores a specific session synchronously. You point it at a
session and tell it which evaluators to apply. The result comes back immediately,
making it ideal for spot-checking during development or debugging a problematic
conversation.

List recent traces to find a session to evaluate:

💻 **Terminal Command:**

```bash
agentcore traces list
```

The output shows recent trace IDs and timestamps. Pick any trace from the
invocations you just ran.

Now run an on-demand evaluation against your agent's most recent activity, using
three built-in evaluators that cover different quality axes:

💻 **Terminal Command:**

```bash
agentcore run eval \
  --evaluator "Builtin.Helpfulness" \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.ToolSelectionAccuracy"
```

> The CLI automatically discovers recent sessions from your agent's CloudWatch
> logs. If prompted to select a session, pick the one from your most recent
> invocation.

The output shows each evaluator's score, label, and explanation. For example:

```
On-demand evaluation completed

Evaluator                        Score    Label
────────────────────────────────────────────────────
Builtin.Helpfulness              0.83     Very Helpful
Builtin.GoalSuccessRate          1.00     Yes
Builtin.ToolSelectionAccuracy    1.00     Yes

Explanation (Builtin.Helpfulness):
  The agent correctly identified the customer, retrieved the order,
  checked return eligibility, and provided a clear summary.
```

Each evaluator produces three pieces of data:

- **Score:** Numeric value (0-1 normalized)
- **Label:** Human-readable category (e.g., "Very Helpful", "Yes/No", "Partially
  Correct")
- **Explanation:** The judge model's reasoning for the score it assigned

## Step 3: Understand the Built-in Evaluators

AgentCore ships 14 built-in evaluators across three granularity levels. Each one
targets a different aspect of agent quality.

### Session-Level Evaluators

These evaluate the full conversation:

| Evaluator | Scoring | What it checks |
|---|---|---|
| `Builtin.GoalSuccessRate` | Yes / No | Did the agent accomplish all user goals in the session? |
| `Builtin.TrajectoryExactOrderMatch` | Pass / Fail | Did tools execute in exactly the expected sequence? (programmatic) |
| `Builtin.TrajectoryInOrderMatch` | Pass / Fail | Did expected tools appear in order (extras allowed between)? |
| `Builtin.TrajectoryAnyOrderMatch` | Pass / Fail | Were all expected tools called regardless of order? |

### Trace-Level Evaluators

These evaluate individual request-response turns:

| Evaluator | Scoring | What it checks |
|---|---|---|
| `Builtin.Helpfulness` | 7 levels (0-6) | How useful is the response? |
| `Builtin.Correctness` | 3 levels | Is the response factually accurate? |
| `Builtin.Faithfulness` | 5 levels | Does it stay consistent with provided context? |
| `Builtin.Coherence` | 5 levels | Is the reasoning logically consistent? |
| `Builtin.Conciseness` | 3 levels | Is the response appropriately brief? |
| `Builtin.Harmfulness` | Harmful / Not Harmful | Does it contain harmful content? |
| `Builtin.InstructionFollowing` | Yes / No | Does it follow the system prompt? |
| `Builtin.ResponseRelevance` | 5 levels | Does it address what was asked? |

### Tool-Level Evaluators

These evaluate individual tool calls:

| Evaluator | Scoring | What it checks |
|---|---|---|
| `Builtin.ToolSelectionAccuracy` | Yes / No | Was the tool choice justified given the context? |
| `Builtin.ToolParameterAccuracy` | Yes / No | Were the parameters extracted correctly from the conversation? |

## Step 4: Create a Custom Evaluator

Built-in evaluators cover general quality. For your Returns & Refunds domain, you
need evaluators that check domain-specific behavior, such as: did the agent verify
return eligibility before suggesting a refund?

Create a custom LLM-as-a-Judge evaluator that checks whether the agent follows the
correct returns workflow. The AgentCore CLI manages evaluators as project resources
(just like memory and gateway), so the creation follows the same add-then-deploy
pattern.

First, create the evaluator config file:

🤖 **Kiro Vibe Prompt:**

```
Create a file called `eval/returns_workflow_evaluator.json` in the project root with the following custom evaluator configuration:

{
  "llmAsAJudge": {
    "instructions": "You are evaluating a returns and refunds assistant. Review the full conversation and determine whether the agent followed the correct workflow.\n\nThe correct workflow is:\n1. Look up the order using order_lookup or user_lookup tools\n2. Retrieve the return policy for the customers country using policy_retrieval\n3. Check whether the item is within the return eligibility window\n4. Only after confirming eligibility, calculate or suggest a refund amount\n5. Confirm details with the user before finalizing\n\nEvaluate whether these steps happened in a logical order. Minor deviations are acceptable if the agent still verified eligibility before suggesting a refund.\n\nConversation:\n{context}\n\nTools available:\n{available_tools}\n\nActual tool trajectory:\n{actual_tool_trajectory}",
    "ratingScale": {
      "numerical": [
        {"value": 1.0, "label": "Fully Compliant", "definition": "All workflow steps followed in correct order"},
        {"value": 0.75, "label": "Mostly Compliant", "definition": "Key steps present but minor ordering issue"},
        {"value": 0.5, "label": "Partially Compliant", "definition": "Some steps skipped but eligibility was checked"},
        {"value": 0.25, "label": "Mostly Non-Compliant", "definition": "Major steps skipped or refund suggested without eligibility check"},
        {"value": 0.0, "label": "Non-Compliant", "definition": "Agent suggested refund without checking eligibility or looking up order"}
      ]
    },
    "modelConfig": {
      "bedrockEvaluatorModelConfig": {
        "modelId": "anthropic.claude-sonnet-4-6-v1",
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.0}
      }
    }
  }
}
```

Now add the evaluator to your AgentCore project:

💻 **Terminal Command:**

```bash
agentcore add evaluator \
  --name "ReturnsWorkflowCompliance" \
  --config eval/returns_workflow_evaluator.json \
  --level "SESSION"
```

This registers the evaluator in your `agentcore.json` project config. Deploy it to
create the resource in AWS:

💻 **Terminal Command:**

```bash
agentcore deploy
```

After deployment completes, verify the evaluator exists:

💻 **Terminal Command:**

```bash
agentcore status
```

You should see `ReturnsWorkflowCompliance` listed as a project evaluator resource.

Run your custom evaluator against the same session you tested earlier:

💻 **Terminal Command:**

```bash
agentcore run eval \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.ToolSelectionAccuracy" \
  --evaluator "ReturnsWorkflowCompliance"
```

The custom evaluator scores sessions alongside the built-in ones, checking whether
your agent follows the correct returns workflow. Since the evaluator uses
`{actual_tool_trajectory}` in its prompt, the judge model can see exactly which
tools were called and in what order.

## Step 5: Set Up Online Evaluation (Continuous Monitoring)

Online evaluation continuously samples production traffic and scores it in the
background. Scores flow to CloudWatch metrics under the
`Bedrock-AgentCore/Evaluations` namespace, where you can set alarms and track
trends on the GenAI Observability dashboard.

Add an online evaluation config to your project:

💻 **Terminal Command:**

```bash
agentcore add online-eval
```

Walk through the interactive wizard:

- Config name: `returns-agent-quality-monitor`
- Sampling rate: `100` (100% for the workshop; in production you'd sample 10-25%)
- Evaluators: Select `Builtin.Helpfulness`, `Builtin.GoalSuccessRate`,
  `Builtin.ToolSelectionAccuracy`
- Enable on create: **Yes**

Deploy the updated configuration:

💻 **Terminal Command:**

```bash
agentcore deploy
```

Verify the online evaluation is active:

💻 **Terminal Command:**

```bash
agentcore status
```

You should see the online evaluation config listed with status `ENABLED`.

### Generate traffic to trigger online evaluation

Invoke the agent a few more times so the online evaluator has sessions to score:

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
I'm customer C-01. I want to return the laptop I ordered last week. Can you check if it's still eligible?
```

💬 **Agent Test Prompt:**

```
What's the refund policy for clothing in the UK?
```

Exit with <kbd>Ctrl+C</kbd>. Wait 2-3 minutes for the online evaluation to pick up
and score these sessions. The session timeout (default 15 minutes) determines when
the system considers a session complete and ready for evaluation. Since you exited
the invoke session, it should process within a few minutes.

### View results in the GenAI Observability dashboard

1. Open the GenAI Observability dashboard in the AWS Console
2. Select the **Amazon Bedrock AgentCore** tab
3. Select your agent from the agents list
4. Navigate to the **Evaluations** tab

The dashboard shows:

- Per-evaluator score distributions as bar charts
- Score trends over time
- Click any session row to drill into trace-level scores and read the judge
  model's explanation

> The Evaluations tab may take 3-5 minutes to populate after the first scored
> session. Refresh the page if results aren't visible yet.

### Set a quality alarm

You can create a CloudWatch alarm that fires when evaluation scores drop below a
threshold. In the Evaluations tab, click the bell icon on any evaluator's bar chart
to create an alarm directly. Alternatively:

1. Open CloudWatch > Alarms > Create alarm
2. Select metric > navigate to `Bedrock-AgentCore/Evaluations` namespace
3. Choose the `Builtin.Helpfulness` metric for your agent
4. Set a static threshold (e.g., alarm when average drops below 0.6)
5. Add an SNS notification action

For this workshop, viewing the dashboard is sufficient. In production, alarms on
`GoalSuccessRate` and your custom `ReturnsWorkflowCompliance` evaluator would catch
regressions before customers notice.

## Step 6: Build a Golden Dataset

A golden dataset defines test scenarios with known-correct answers. Batch
evaluation runs these scenarios against your agent and compares actual behavior to
expected behavior, catching regressions when you change the agent's prompt, model,
or tools.

For the Returns & Refunds agent, a useful golden dataset covers:

- **Happy path:** return-eligible order gets a correct refund calculation
- **Edge case:** order outside the return window gets rejected
- **Tool trajectory:** the agent calls tools in the expected sequence

Create a golden dataset file:

🤖 **Kiro Vibe Prompt:**

```
Create a file called `eval/golden-dataset.json` in the project root with test scenarios for our Returns & Refunds agent.

The file should follow the AgentCore predefined dataset schema (AGENTCORE_EVALUATION_PREDEFINED_V1). Include 4 scenarios:

1. "happy-path-return" -- Customer C-01 asks about returning order ORD-001. Expected trajectory: user_lookup, order_lookup, policy_retrieval. Assertions: "Agent confirmed the order is eligible for return", "Agent mentioned the return window".

2. "refund-calculation" -- Ask to calculate a refund for a $199.99 item with 10% tax and $9.99 shipping, 15% restocking fee. Expected response should include the correct math: restocking = $30.00, refund = $169.99 + tax portion. Assertions: "Agent applied the restocking fee before calculating the final refund".

3. "ineligible-return" -- Customer asks about returning an order that is past the return window (use order ORD-003 which is 45 days old). Assertions: "Agent informed the customer that the item is not eligible for return", "Agent did not suggest a refund for an ineligible item".

4. "policy-lookup" -- Ask about the UK returns policy for clothing. Expected trajectory: policy_retrieval. Assertions: "Agent retrieved the UK-specific policy", "Agent mentioned the return window duration".

Use this exact schema structure:
{
  "schemaType": "AGENTCORE_EVALUATION_PREDEFINED_V1",
  "scenarios": [
    {
      "scenario_id": "...",
      "turns": [{"input": "..."}],
      "expected_trajectory": ["tool1", "tool2"],
      "assertions": ["...", "..."],
      "metadata": {}
    }
  ]
}

For turns that have a known correct answer, add "expected_response": "..." to that turn object.
```

Verify the file was created:

💻 **Terminal Command:**

```bash
cat eval/golden-dataset.json | python3 -m json.tool | head -40
```

## Step 7: Run a Batch Evaluation

Batch evaluation processes multiple sessions asynchronously. It pulls sessions from
CloudWatch Logs, applies evaluators to each one, and returns aggregate scores plus
per-session details. Use it for regression testing after changing the agent's
prompt, switching models, or modifying tool implementations.

Run a batch evaluation across all sessions from the last hour:

💻 **Terminal Command:**

```bash
agentcore run batch-evaluation \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.Helpfulness" \
  --evaluator "Builtin.Faithfulness" \
  --evaluator "Builtin.ToolSelectionAccuracy"
```

The CLI starts the batch job, polls until completion, and prints aggregate results:

```
Batch evaluation completed: returns-eval-a1b2c3d4

Sessions: 5 completed, 0 failed, 5 total

Evaluator                        Avg Score
─────────────────────────────────────────────
Builtin.GoalSuccessRate          0.8000
Builtin.Helpfulness              0.8500
Builtin.Faithfulness             0.9000
Builtin.ToolSelectionAccuracy    1.0000

Results saved to .cli/eval-job-results/
```

These aggregate scores are your baseline. After any change to the agent (prompt
edits, model upgrades, new tools), re-run this batch evaluation and compare the
numbers. A drop in `GoalSuccessRate` or `ToolSelectionAccuracy` signals a
regression.

### View per-session details

The batch results are saved locally. Inspect individual session scores:

💻 **Terminal Command:**

```bash
ls agentcore/.cli/eval-job-results/
```

Each result file contains the per-session breakdown with scores and judge
explanations, useful for understanding which specific conversations scored poorly
and why.

## Step 8: Run a Dataset Evaluation (Ground Truth Comparison)

Dataset evaluation goes further than batch: it invokes the agent with your golden
dataset scenarios, collects the traces, and then evaluates them against the
expected responses and trajectories you defined. This is a full end-to-end
regression test.

🤖 **Kiro Vibe Prompt:**

```
Create a Python script at `eval/run_dataset_eval.py` that runs a dataset evaluation using the AgentCore Python SDK.

The script should:
1. Install/import the bedrock-agentcore SDK: `from bedrock_agentcore.evaluations import DatasetEvaluation`
2. Load the golden dataset from `eval/golden-dataset.json`
3. Use the OnDemandEvaluationDatasetRunner to:
   - Invoke the agent with each scenario's turns
   - Collect traces
   - Run evaluators: Builtin.GoalSuccessRate, Builtin.Correctness, Builtin.ToolSelectionAccuracy, Builtin.TrajectoryAnyOrderMatch
4. Print a summary table showing scenario_id, goal_success, correctness, tool_accuracy, trajectory_match
5. Flag any scenario that scored below 0.5 on any evaluator as "NEEDS ATTENTION"

Use the agent runtime name from our agentcore project config. The script should be runnable with: python3 eval/run_dataset_eval.py

Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations.html
```

Run the dataset evaluation:

💻 **Terminal Command:**

```bash
cd ~/ReturnsRefundsAgentProject/AgentCoreProject
pip install bedrock-agentcore --quiet
python3 eval/run_dataset_eval.py
```

**Expected output:**

```
Running dataset evaluation with 4 scenarios...

Scenario                  Goal    Correct  ToolAcc  Trajectory
──────────────────────────────────────────────────────────────
happy-path-return         1.00    0.83     1.00     1.00
refund-calculation        1.00    1.00     1.00     N/A
ineligible-return         1.00    1.00     1.00     N/A
policy-lookup             1.00    0.83     1.00     1.00

All scenarios passed. No regressions detected.
```

If any scenario shows "NEEDS ATTENTION", investigate the explanation to understand
what the agent did differently from the expected behavior.

## Evaluation Modes: When to Use Each

| Mode | Trigger | Speed | Best for |
|---|---|---|---|
| On-demand | Manual (CLI or API) | Synchronous, seconds | Spot-checking a specific session, debugging, trying a new evaluator |
| Online | Automatic (sampling) | Background, minutes | Continuous production monitoring, quality trend tracking, alerting |
| Batch | Manual (CLI or API) | Async, minutes | Regression testing after changes, baseline measurement, pre/post comparison |
| Dataset | Manual (script) | Minutes | End-to-end testing with ground truth, CI/CD gates, golden dataset validation |

A production workflow typically combines all four:

1. Dataset evaluation in CI/CD before deploying changes (gate on passing scores)
2. On-demand evaluation during development to iterate on prompts
3. Online evaluation in production with alarms on score drops
4. Batch evaluation weekly or after incidents to audit quality trends

## Step 9: Pause Online Evaluation

Online evaluation runs continuously and consumes evaluator tokens. For the
workshop, pause it before moving to cleanup:

💻 **Terminal Command:**

```bash
agentcore pause
```

Select the `returns-agent-quality-monitor` config when prompted. You can resume it
later with `agentcore resume`.

## Summary

You set up a complete evaluation pipeline for the Returns & Refunds agent:

- **On-demand evaluation** scored individual sessions with built-in evaluators
  (Helpfulness, GoalSuccessRate, ToolSelectionAccuracy)
- A **custom evaluator** (`ReturnsWorkflowCompliance`) checks domain-specific
  workflow compliance using LLM-as-a-Judge
- **Online evaluation** continuously monitors production traffic and writes scores
  to CloudWatch, visible in the GenAI Observability dashboard
- A **golden dataset** defines test scenarios with expected tool trajectories and
  assertions
- **Batch evaluation** measured aggregate quality across multiple sessions for
  regression detection
- **Dataset evaluation** ran end-to-end tests against ground truth for CI/CD gating

The five-axis quality framework (task success, faithfulness, safety, tooling
behavior, cost/latency) gives you full coverage. Built-in evaluators handle the
general axes, custom evaluators handle domain-specific checks, and CloudWatch
metrics from Part 6 cover cost and latency.

---

⬅️ [Back: Part 8 — Try the AgentCore Harness](part-08-agentcore-harness-preview.md) | [Overview](README.md) | ➡️ [Next: Part 10 — Secure Tool Access with Policies](part-10-secure-tool-access-policies.md)
