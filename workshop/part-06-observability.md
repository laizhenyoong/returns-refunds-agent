# Part 6: Explore Observability — Logs, Traces & GenAI Dashboard

**Estimated time:** ~10 minutes

In this part, you'll explore three ways to monitor and debug your deployed agent:
the AgentCore CLI for logs and traces, local log files from the project scaffold, and
the GenAI Observability dashboard in the AWS Console.

> **Prerequisites:** You must have completed Part 5 with a fully deployed agent.
> Make sure you're in your agent project directory
> (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

> **Transaction Search:** The workshop CloudFormation template has already enabled
> CloudWatch Transaction Search, which is required for trace indexing. It takes
> approximately 10 minutes after deployment for traces to become fully indexed and
> searchable.

---

## Option 1: AgentCore CLI for Logs and Traces

### Agent Logs

The `agentcore logs` command streams or searches agent runtime logs.

By default (no options), it waits and streams future logs in real time:

💻 **Terminal Command:**

```bash
agentcore logs
```

Press <kbd>Ctrl+C</kbd> to stop streaming.

To pull past logs, use `--since` and `--limit`:

💻 **Terminal Command:**

```bash
agentcore logs --since 30m --limit 100
```

**Available options:**

| Option | Description | Example |
|---|---|---|
| `--since <time>` | Start time (defaults to 1h ago in search mode) | `30m`, `2d`, ISO 8601 |
| `--until <time>` | End time (defaults to now) | `now`, ISO 8601 |
| `--level <level>` | Filter by log level | `error`, `warn`, `info`, `debug` |
| `-n, --limit <count>` | Maximum log lines to return | `100` |
| `--query <text>` | Server-side text filter | `"order_lookup"` |
| `--json` | Output as JSON Lines | |

**Examples:**

💻 **Terminal Command:**

```bash
agentcore logs --since 1h --level error
```

💻 **Terminal Command:**

```bash
agentcore logs --since 30m --query "gateway"
```

### Agent Traces

The `agentcore traces` command lets you list and download execution traces.

List recent traces:

💻 **Terminal Command:**

```bash
agentcore traces list
```

Download a specific trace to a JSON file:

💻 **Terminal Command:**

```bash
agentcore traces get <traceId>
```

Replace `<traceId>` with the trace ID from the list output. Each trace represents a
single agent invocation showing the full execution path including LLM calls, tool
executions, memory operations, and gateway requests.

## Option 2: Local Log Files

The AgentCore CLI stores log files locally in your project directory under
`agentcore/.cli/logs/`. These logs capture output from local development
(`agentcore dev`) and deployment operations (`agentcore deploy`).

Browse the local logs:

💻 **Terminal Command:**

```bash
ls agentcore/.cli/logs/
```

You'll see subdirectories for different operations:

```
agentcore/.cli/logs/
|-- dev/          # Logs from agentcore dev sessions
|-- deploy/       # Logs from agentcore deploy operations
```

View the most recent dev session log:

💻 **Terminal Command:**

```bash
ls -lt agentcore/.cli/logs/dev/ | head -5
```

These local logs are useful for debugging issues that occurred during local testing
or deployment, without needing to access CloudWatch.

## Option 3: AWS Console — GenAI Observability Dashboard

The AWS Console provides a visual GenAI Observability dashboard that aggregates
metrics, traces, and sessions across all your agent invocations.

### Navigate to the Dashboard

1. Open the GenAI Observability dashboard in the AWS Console
2. Make sure you're in the `us-west-2` region
3. Select the **Amazon Bedrock AgentCore** tab

### Agents View

The Agents View lists all your agents (both on and off runtime). Select your agent
to view:

- Runtime metrics
- Sessions associated with the agent
- Traces specific to the agent

### Sessions View

The Sessions View lets you navigate across all sessions associated with your
agents. Each session represents a conversation with a unique `runtimeSessionId`.

### Traces View

The Traces View shows detailed trace and span information for agent invocations.
Select a trace to explore:

- The trace trajectory showing the full execution path
- Timeline view with duration of each span (LLM calls, tool executions, memory
  operations, gateway requests)
- Status of each span (success/failure)

### View Logs in CloudWatch

You can also view logs directly in CloudWatch:

1. In the CloudWatch console, expand **Logs** and select **Log groups**
2. Search for your agent's log group:
   - Standard logs (stdout/stderr):
     `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/[runtime-logs] <UUID>`
   - OTEL structured logs:
     `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs`

### View Traces in Transaction Search

1. In the CloudWatch console, select **Transaction Search**
2. Navigate to `/aws/spans/default`
3. Filter by service name or other criteria
4. Select a trace to view the detailed execution graph

> The dashboard may take a few minutes to populate with data after your first
> invocations. If the charts appear empty, wait 2-3 minutes and refresh the page.

## Understanding Observability Data

Each option serves a different purpose:

| Option | Best For | Access |
|---|---|---|
| `agentcore logs` / `agentcore traces` | Real-time debugging, quick inspection of recent activity | Terminal (CLI) |
| Local logs (`agentcore/.cli/logs/`) | Debugging local dev sessions and deployment issues | File system |
| GenAI Observability Dashboard | Visual monitoring, session navigation, trace exploration, metrics over time | AWS Console |

**When to use each:**

- Something broke in production? Start with `agentcore logs` to find the error.
- Local dev session failed? Check `agentcore/.cli/logs/dev/` for the session log.
- Need a visual overview of agent performance? Use the GenAI Observability
  dashboard.
- Want to understand the full execution path of a specific invocation? Use the
  Traces View in the dashboard or `agentcore traces list`.

## Summary

You've explored three ways to monitor and debug your agent:

- AgentCore CLI commands (`agentcore logs`, `agentcore traces list`) for
  terminal-based debugging
- Local log files in `agentcore/.cli/logs/` for dev and deployment logs
- GenAI Observability dashboard in the AWS Console for visual monitoring, session
  navigation, and trace exploration

In the final part, you'll clean up all the resources created during this workshop.

---

⬅️ [Back: Part 5 — Build a Web Chat UI](part-05-streamlit-ui-cognito.md) | [Overview](README.md) | ➡️ [Next: Part 7 — Make It Yours](part-07-open-ended-enhancements.md)
