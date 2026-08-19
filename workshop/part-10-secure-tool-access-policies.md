# Part 10: Secure Tool Access with AgentCore Policies

**Estimated time:** ~30 minutes

Your agent authenticates callers through Cognito (Part 4), but authentication only
proves identity. It does not restrict what an authenticated caller can do. Right
now, any valid JWT grants access to every tool on the gateway. A support agent can
process refunds the same way an admin can. Policies add fine-grained authorization
at the gateway boundary, controlling which principals can call which tools with
what parameters.

> **Prerequisites:** You must have completed Parts 1-6, especially Part 4 (gateway
> setup) and Part 5 (Streamlit UI with Cognito). Make sure you're in your agent
> project directory (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

---

## Step 1: Understand the Authorization Gap

IAM policies control who can manage AWS resources (deploy agents, create
gateways). Bedrock Guardrails filter model output (block harmful content, redact
PII). Neither of these controls which tools an agent can call or what parameter
values it can pass. That gap is what AgentCore Policies fill.

The critical property: **policies enforce outside agent code, at the gateway
boundary**. A prompt injection that tricks the agent into calling `process_refund`
with a large amount still fails because the gateway evaluates the policy before
forwarding the request to the Lambda.

| Mechanism | Enforcement point | Controls | Best for |
|---|---|---|---|
| AgentCore Policy | Gateway boundary (pre-tool-call) | Which tools, which parameters, which principals | Authorization: "can this user do this action?" |
| Bedrock Guardrails | Model input/output | Content filtering, topic denial, PII redaction | Safety: "should this content exist?" |
| IAM | AWS API layer | AWS resource operations | Infrastructure: "who manages what?" |
| Lambda Interceptor | Inside the Lambda target | Custom business logic, external lookups | Dynamic decisions requiring runtime state |

### Cedar Basics

AgentCore Policies use the Cedar policy language. Three rules to remember:

1. **Default deny** — if no policy explicitly permits an action, it is denied.
2. **Permit/Forbid** — you write `permit(...)` and `forbid(...)` statements.
3. **Forbid wins** — if both a permit and a forbid match the same request, the
   forbid overrides. Always.

## Step 2: Add a `process_refund` Tool

Before writing policies, you need a sensitive action worth protecting. Create a
mock refund-processing Lambda that accepts an order ID, amount, and reason, then
register it as a new gateway target.

### Create the Lambda function

🤖 **Kiro Vibe Prompt:**

```
Create a new Lambda function at /lambda_functions/refund_processing/handler.py that implements a mock process_refund tool.

Input parameters:
- order_id (str): The order to refund
- amount (int): Refund amount in dollars
- reason (str): Why the refund is being issued

The function should:
1. Follow the same AgentCore Gateway Lambda input/output format as our existing data_lookup Lambda
2. Use the bedrockAgentCoreToolName from context to identify the tool call
3. Return a mock confirmation message like: "Refund of ${amount} processed for order {order_id}. Reason: {reason}. Confirmation ID: REF-{random 6 digits}"
4. Do NOT actually process anything - this is a mock for testing policies

Also create a requirements.txt (just boto3) and a tool spec file at tool_specs/refund_processing.json with a single tool definition for process_refund.
```

### Deploy the Lambda

🤖 **Kiro Vibe Prompt:**

```
Deploy the refund_processing Lambda function to AWS in region us-west-2.
Zip the code, create the Lambda using the execution role ARN from SSM parameter /app/workshop/lambda/execution-role-arn.
Print the Lambda ARN after deployment.
```

### Register the gateway target

💻 **Terminal Command:**

```bash
agentcore add
```

Walk through the wizard:

- Select **Gateway Target**
- Name: `refund-target`
- Target type: **Lambda function**
- Paste the Lambda ARN Kiro printed
- Tool schema file path: `./tool_specs/refund_processing.json`
- Select `workshop-gateway`
- **Confirm**

Deploy the updated project:

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Verify the new tool works

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Process a refund of $200 for order ORD-001. Reason: customer received damaged item.
```

The agent should call `process_refund` through the gateway and return a
confirmation with a random reference ID. Press <kbd>Ctrl+C</kbd> to exit.

## Step 3: Create a Policy Engine (LOG_ONLY)

A policy engine is the container that holds your Cedar policies and attaches to a
gateway. `LOG_ONLY` mode evaluates every request against your policies and logs
the decision (ALLOW or DENY) to CloudWatch, but never blocks traffic. This lets you
validate rules against real usage before enforcing them.

💻 **Terminal Command:**

```bash
agentcore add policy-engine --name returns-policy-engine --attach-to-gateways workshop-gateway --attach-mode LOG_ONLY
```

Deploy:

💻 **Terminal Command:**

```bash
agentcore deploy
```

Verify it appears in your project status:

💻 **Terminal Command:**

```bash
agentcore status
```

You should see `returns-policy-engine` listed with mode `LOG_ONLY` and attached to
`workshop-gateway`.

> In `LOG_ONLY` mode, the gateway continues to allow all authenticated requests.
> The policy engine evaluates and logs decisions without affecting behavior. Think
> of it as a dry-run for your authorization rules.

## Step 4: Write the First Cedar Policy (Permit Read Tools)

Create a `policies/` directory in your project and write a policy that permits any
authenticated user to call the read-only tools (data lookup and policy retrieval).

💻 **Terminal Command:**

```bash
mkdir -p policies
```

Create the file `policies/allow_read_tools.cedar` with the following content:

```text
// Allow any authenticated caller to invoke read-only tools
permit(
  principal,
  action in [
    Action::"data-lookup___order_lookup",
    Action::"data-lookup___user_lookup",
    Action::"data-lookup___product_lookup",
    Action::"policy-retrieval___policy_retrieval"
  ],
  resource
);
```

> **Action naming format:** AgentCore Gateway constructs Cedar action names as
> `TargetName___tool_name`. The triple underscore separates the gateway target
> name from the tool function name. You can find the exact names in your tool
> spec files.

Add the policy to your engine:

💻 **Terminal Command:**

```bash
agentcore add policy --name AllowReadTools --engine returns-policy-engine --source policies/allow_read_tools.cedar
```

Deploy:

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Test the read tools

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Look up customer C-01 and tell me about their most recent order.
```

The agent responds normally. The tools work exactly as before, but the policy
engine now logs an ALLOW decision for each tool call. You can confirm this in
CloudWatch:

💻 **Terminal Command:**

```bash
agentcore logs --since 5m --query "policy"
```

Look for log entries showing `decision: ALLOW` for the `data-lookup___order_lookup`
and `data-lookup___user_lookup` actions.

Press <kbd>Ctrl+C</kbd> to exit the invoke session.

## Step 5: Add a Parameter Constraint (Refund Limit)

Now write a policy that permits refunds, but only when the amount is below $500.
This demonstrates Cedar's ability to inspect tool parameters, not just tool names.

Create `policies/refund_limit.cedar`:

```text
// Allow refunds under $500 for any authenticated caller
permit(
  principal,
  action == Action::"refund-target___process_refund",
  resource
) when {
  context.input.amount < 500
};
```

Add and deploy:

💻 **Terminal Command:**

```bash
agentcore add policy --name RefundLimit --engine returns-policy-engine --source policies/refund_limit.cedar
```

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Test both cases

💻 **Terminal Command:**

```bash
agentcore invoke
```

First, a refund under the limit:

💬 **Agent Test Prompt:**

```
Process a refund of $200 for order ORD-003. Reason: wrong size shipped.
```

The agent processes the refund successfully. The policy engine logs
`decision: ALLOW`.

Now, a refund over the limit:

💬 **Agent Test Prompt:**

```
Process a refund of $1500 for order ORD-001. Reason: full order return.
```

The agent still processes this refund because you're in `LOG_ONLY` mode. But check
the logs:

💻 **Terminal Command:**

```bash
agentcore logs --since 5m --query "policy"
```

You'll see `decision: DENY` logged for the $1500 refund. The log tells you exactly
what would have been blocked if the engine were in `ENFORCE` mode.

> `LOG_ONLY` is for validation only. Both requests succeed right now regardless of
> the policy decision. The logs show you the authorization outcome without
> impacting traffic. You'll switch to `ENFORCE` in Step 7.

Press <kbd>Ctrl+C</kbd> to exit the invoke session.

## Step 6: Add RBAC via JWT Claims

Real-world authorization often depends on who the caller is, not just what
they're doing. In this step, you'll create a second Cognito user with a "manager"
role and write a policy that grants managers a higher refund limit.

### Create a manager user in Cognito

🤖 **Kiro Vibe Prompt:**

```
Add a "managers" group to the Cognito User Pool we created for the workshop gateway (workshop-gateway-auth).

Then create a second app client for the managers group:
1. Add a custom scope "managers" to the existing resource server
2. Create a new app client named "workshop-gateway-manager-client" with client_credentials grant, using both the existing invoke scope and the new managers scope
3. Save the new client credentials (client_id, client_secret) to a file called cognito_manager_config.json

Use region us-west-2. Print the new client ID when done.
```

### Write the manager policy

Create `policies/manager_refund_limit.cedar`:

```text
// Managers can process refunds up to $5000
permit(
  principal,
  action == Action::"refund-target___process_refund",
  resource
) when {
  principal.getTag("scope") like "*managers*" &&
  context.input.amount < 5000
};
```

> **How JWT claims become Cedar attributes:** When the gateway validates a Custom
> JWT token, it maps token claims to Cedar principal attributes. The OAuth scopes
> from the token become available through `principal.getTag("scope")`. Group
> membership, custom attributes, and other claims are accessible through similar
> tag lookups.

Add and deploy:

💻 **Terminal Command:**

```bash
agentcore add policy --name ManagerRefundLimit --engine returns-policy-engine --source policies/manager_refund_limit.cedar
```

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Verify with the manager client

To test the manager policy, you would need to invoke the agent with a token
obtained from the manager app client. The token includes the `managers` scope,
which the Cedar policy checks. In `LOG_ONLY` mode, both clients succeed, but the
logs show different decisions:

- Regular client requesting $1500 refund: `decision: DENY` (exceeds the $500 limit
  from Step 5, no manager scope)
- Manager client requesting $1500 refund: `decision: ALLOW` (manager policy
  permits up to $5000)

You'll see this enforcement in action after switching to `ENFORCE` mode in the
next step.

## Step 7: Switch to ENFORCE Mode

You've validated your policies in `LOG_ONLY` mode and confirmed the decisions are
correct. Now switch to `ENFORCE` so the gateway actually blocks unauthorized
requests.

> **Before switching to ENFORCE:** confirm your permit policies cover all the
> tools your agent calls during normal operation. If you miss a permit rule, the
> gateway will deny those tool calls and the agent will receive errors. The
> read-tools policy from Step 4 covers `data-lookup` and `policy-retrieval`. The
> refund policies from Steps 5-6 cover `process_refund`.

Remove the existing policy engine and re-add it with `ENFORCE` mode:

💻 **Terminal Command:**

```bash
agentcore remove policy-engine --name returns-policy-engine
```

💻 **Terminal Command:**

```bash
agentcore add policy-engine --name returns-policy-engine --attach-to-gateways workshop-gateway --attach-mode ENFORCE
```

> Removing and re-adding the policy engine preserves your Cedar policy files in
> the `policies/` directory. The policies are re-associated when you deploy. Your
> Cedar files are the source of truth.

Re-add all policies:

💻 **Terminal Command:**

```bash
agentcore add policy --name AllowReadTools --engine returns-policy-engine --source policies/allow_read_tools.cedar
```

💻 **Terminal Command:**

```bash
agentcore add policy --name RefundLimit --engine returns-policy-engine --source policies/refund_limit.cedar
```

💻 **Terminal Command:**

```bash
agentcore add policy --name ManagerRefundLimit --engine returns-policy-engine --source policies/manager_refund_limit.cedar
```

Deploy:

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Test the denied case

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Process a refund of $1500 for order ORD-001. Reason: full order return.
```

This time the gateway blocks the tool call. The agent receives an authorization
error from the gateway instead of a refund confirmation. Watch how the agent
handles it. It should explain to the user that the refund request was denied due
to authorization constraints (the amount exceeds the allowed limit).

Now confirm that permitted actions still work:

💬 **Agent Test Prompt:**

```
Process a refund of $150 for order ORD-003. Reason: item arrived late.
```

This succeeds normally because $150 is below the $500 limit.

💬 **Agent Test Prompt:**

```
Look up customer C-02 and their orders.
```

Read-only lookups continue to work as expected.

Press <kbd>Ctrl+C</kbd> to exit.

## Step 8: Add a Forbid Rule

Forbid rules are unconditional overrides. Because Cedar's forbid-wins semantics
guarantee that no permit can override a forbid, they are ideal for absolute
restrictions: business-hours-only access, emergency shutoffs, or compliance
requirements.

### Time-based restriction

Create `policies/business_hours_only.cedar`:

```text
// Block refund processing outside business hours (9am-5pm UTC)
forbid(
  principal,
  action == Action::"refund-target___process_refund",
  resource
) when {
  context.system.now.toTime() < duration("9h") ||
  context.system.now.toTime() > duration("17h")
};
```

Add and deploy:

💻 **Terminal Command:**

```bash
agentcore add policy --name BusinessHoursOnly --engine returns-policy-engine --source policies/business_hours_only.cedar
```

💻 **Terminal Command:**

```bash
agentcore deploy
```

If you're running this outside 9am-5pm UTC, try processing a refund. The gateway
will deny it regardless of the amount or the caller's role. The forbid overrides
both the `RefundLimit` and `ManagerRefundLimit` permits.

### Emergency kill switch pattern

For incident response, you may need to disable a tool immediately. A blanket
forbid with no conditions blocks all access:

```text
// EMERGENCY: disable all refund processing immediately
forbid(
  principal,
  action == Action::"refund-target___process_refund",
  resource
);
```

You do not need to add this policy now. It is shown as a reference pattern. If you
ever need to shut down a tool instantly, add a forbid like this, deploy, and the
tool becomes inaccessible. Removing the policy file and redeploying restores
access.

> **Forbid-wins in practice:** Even if ten permit policies match a request, a
> single matching forbid overrides all of them. This is by design. It means you
> can add safety constraints (time-of-day, deny-lists, emergency blocks) without
> auditing every existing permit policy for conflicts.

### Summary of your policy set

At this point your `policies/` directory contains:

| File | Effect |
|---|---|
| `allow_read_tools.cedar` | Permits all authenticated callers to use data-lookup and policy-retrieval tools |
| `refund_limit.cedar` | Permits refunds under $500 for any caller |
| `manager_refund_limit.cedar` | Permits refunds under $5000 for callers with manager scope |
| `business_hours_only.cedar` | Forbids refund processing outside 9am-5pm UTC |

These compose together through Cedar's evaluation model: a request must match at
least one permit, and must not match any forbid.

## Step 9: Add a Response Interceptor (Business-Data Redaction)

Cedar policies control who can call what. But they cannot modify data coming back
from a tool. If a tool response contains internal business fields (wholesale
costs, profit margins, internal notes), the agent sees that raw data and may
surface it in conversation.

A response interceptor sits between the tool and the agent, filtering data before
it enters the LLM context.

> This is **not** PII filtering. Bedrock Guardrails handle PII redaction at the
> model layer (emails, phone numbers, credit cards). Those patterns are
> standardized and Guardrails knows how to detect them. Business data like
> wholesale costs, supplier IDs, and margin percentages have no standard pattern.
> Guardrails cannot know your internal schema. The response interceptor does.

### How interceptors relate to policies

```
Agent --> Gateway --> [Cedar Policy] --> [Target Lambda]
                                               |
Agent <-- Gateway <-- [RESPONSE Interceptor] <-+
```

Policies run before the tool call (authorization). The response interceptor runs
after the tool responds (data filtering). They solve different problems at
different points in the request lifecycle.

### Create the response interceptor Lambda

🤖 **Kiro Vibe Prompt:**

```
Create a Lambda function at /lambda_functions/response_interceptor/handler.py that acts as an AgentCore Gateway RESPONSE interceptor.

The function should:
1. Receive the gateway RESPONSE interceptor event (mcp.gatewayResponse)
2. Parse the response body JSON
3. Recursively scan all keys in the response and redact values for keys matching a blocklist: wholesale_cost, cost_price, profit_margin, margin_pct, internal_notes, internal_flag, supplier_id
4. Replace matched values with "[INTERNAL - REDACTED]"
5. Return the modified response as transformedGatewayResponse with interceptorOutputVersion "1.0"
6. Log how many fields were redacted

Keep it simple. Use only json and re (no external libraries).
Also create a requirements.txt with just boto3.
```

### Deploy the interceptor Lambda

🤖 **Kiro Vibe Prompt:**

```
Deploy the response_interceptor Lambda function to AWS in us-west-2.
Use the same execution role ARN from SSM parameter /app/workshop/lambda/execution-role-arn.
Print the Lambda ARN.
```

### Attach the interceptor to the gateway

The gateway service role needs permission to invoke the interceptor Lambda. Update
it and then attach the interceptor.

🤖 **Kiro Vibe Prompt:**

```
Update the workshop-gateway to add a RESPONSE Lambda interceptor.

Steps:
1. Get the gateway ID from `agentcore status`
2. Add lambda:InvokeFunction permission for the response interceptor Lambda ARN to the gateway service role
3. Use the AWS CLI to update the gateway with the interceptor configuration:
   aws bedrock-agentcore-control update-gateway \
     --gateway-identifier <gateway-id> \
     --interceptor-configurations '[{
       "interceptor": {"lambda": {"arn": "<interceptor-lambda-arn>"}},
       "interceptionPoints": ["RESPONSE"],
       "inputConfiguration": {"passRequestHeaders": false}
     }]'
4. Verify the gateway shows the interceptor attached
```

### Test the business-data redaction

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Look up order ORD-001 and show me all details including pricing.
```

If the DynamoDB data contains fields like `wholesale_cost`, `profit_margin`, or
`supplier_id`, those values now appear as `[INTERNAL - REDACTED]` in the agent's
response. The interceptor removed them before the LLM saw the data.

If your data does not currently have those fields, the interceptor passes the
response through cleanly. You can add mock internal fields to the DynamoDB items
to test redaction explicitly, or simply observe the interceptor logging
"0 fields redacted" in CloudWatch.

Press <kbd>Ctrl+C</kbd> to exit.

## Step 10: Add a Request Interceptor (Short-Circuit with Caching)

A request interceptor normally enriches a request and passes it through. But it
can also skip the target entirely by returning `transformedGatewayResponse`
instead of `transformedGatewayRequest`. The gateway returns that response directly
to the agent without ever calling the Lambda target. This enables caching
expensive operations and returning custom blocking messages.

**Use case for this workshop:** The `policy_retrieval` tool queries a Bedrock
Knowledge Base. Knowledge Base queries are slow and cost tokens. If the same
policy question was asked recently, the interceptor returns a cached answer
instantly. The target Lambda is never invoked.

### Create the request interceptor Lambda

🤖 **Kiro Vibe Prompt:**

```
Create a Lambda function at /lambda_functions/request_interceptor/handler.py that acts as an AgentCore Gateway REQUEST interceptor.

The function should:
1. Receive the gateway REQUEST interceptor event (mcp.gatewayRequest)
2. Extract the method and tool name from the request body
3. For policy_retrieval tool calls: check a simple in-memory cache (Python dict at module level, persists across warm invocations):
   - If the query string matches a cached entry added in the last 5 minutes, return transformedGatewayResponse with the cached result (short-circuit, target is never called)
   - If no cache hit, pass through with transformedGatewayRequest and let the target handle it
4. For all other tools: pass through unchanged
5. Include a hardcoded MAINTENANCE_MODE flag (set to False by default). When True, short-circuit ALL process_refund calls with a friendly MCP error:
   {"jsonrpc": "2.0", "id": <original_id>, "error": {"code": -32600, "message": "Refund processing is temporarily suspended for quarterly audit. Please try again after June 15."}}
6. Log whether the request was served from cache, short-circuited for maintenance, or passed through

Use only standard library modules (json, time, base64, logging). Also create a requirements.txt with just boto3.
```

> **About the module-level cache:** This is a simple demo. The Python dict
> persists across warm Lambda invocations because AWS reuses execution contexts.
> In production, use DynamoDB or ElastiCache with proper TTL and eviction. The
> module-level dict works here because workshop traffic stays on a single warm
> container.

### Deploy and attach the request interceptor

🤖 **Kiro Vibe Prompt:**

```
Deploy the request_interceptor Lambda to AWS in us-west-2 using the same execution role.

Then update the workshop-gateway interceptor configuration to include BOTH interceptors:
- REQUEST interceptor: the new request_interceptor Lambda (passRequestHeaders: true)
- RESPONSE interceptor: the existing response_interceptor Lambda (passRequestHeaders: false)

Use the AWS CLI:
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier <gateway-id> \
  --interceptor-configurations '[
    {
      "interceptor": {"lambda": {"arn": "<request-interceptor-arn>"}},
      "interceptionPoints": ["REQUEST"],
      "inputConfiguration": {"passRequestHeaders": true}
    },
    {
      "interceptor": {"lambda": {"arn": "<response-interceptor-arn>"}},
      "interceptionPoints": ["RESPONSE"],
      "inputConfiguration": {"passRequestHeaders": false}
    }
  ]'

Print the gateway status after the update.
```

### Test the caching behavior

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
What is the UK return policy for electronics?
```

This first call hits the Bedrock Knowledge Base through the target Lambda. Note
the response time.

💬 **Agent Test Prompt:**

```
What is the UK return policy for electronics?
```

Ask the same question again. The second call is served from the interceptor
cache. The target Lambda is never invoked. You should notice a faster response.

Press <kbd>Ctrl+C</kbd> to exit.

### Maintenance mode (reference pattern)

The `MAINTENANCE_MODE` flag in the request interceptor is set to `False` by
default. If you flip it to `True` and redeploy the Lambda, all `process_refund`
calls are blocked with a friendly error message. The agent receives an MCP error
and explains to the user that refunds are temporarily suspended.

This is a production pattern for planned outages: deploy a one-line change to the
interceptor, and the tool becomes unavailable with a clear explanation. No agent
code changes needed. No Cedar policy changes needed. Flip it back when the outage
ends.

## Step 11: Extend the Request Interceptor (Context Enrichment for Policy)

The same request interceptor can also inject dynamic context that Cedar policies
evaluate. This is the combined pattern: the interceptor enriches the request, then
Cedar decides based on that enrichment.

### Update the request interceptor

🤖 **Kiro Vibe Prompt:**

```
Update the existing request_interceptor Lambda at /lambda_functions/request_interceptor/handler.py to add context enrichment.

Add a new section to the handler that:
1. Extracts the Authorization header (passRequestHeaders is already true)
2. Base64-decodes the JWT payload (no signature verification needed since the gateway already validated it)
3. Looks up the user department from a hardcoded mapping:
   - The regular client_id (from cognito_config.json) maps to "support"
   - The manager client_id (from cognito_manager_config.json) maps to "finance"
   - Default: "unknown"
4. Injects "department" into params.arguments of the request body
5. This enrichment should happen BEFORE the cache check so that cached responses also carry department context

Keep the existing caching and maintenance mode logic intact. Just add the department injection as an early step.

Redeploy the Lambda after updating.
```

### Write a policy using the enriched context

The request interceptor now injects `department` into every tool call's
arguments. Write a Cedar policy that restricts refund processing to the finance
department.

Create `policies/finance_only_refunds.cedar`:

```text
// Only the finance department can process refunds
forbid(
  principal,
  action == Action::"refund-target___process_refund",
  resource
) when {
  context.input has department &&
  context.input.department != "finance"
};
```

Add and deploy:

💻 **Terminal Command:**

```bash
agentcore add policy --name FinanceOnlyRefunds --engine returns-policy-engine --source policies/finance_only_refunds.cedar
```

💻 **Terminal Command:**

```bash
agentcore deploy
```

### Test the combined pattern

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Process a refund of $100 for order ORD-003. Reason: product defective.
```

If you are using the regular agent client (mapped to "support" department), this
refund is denied. The request interceptor injected `department: "support"`, and
the Cedar forbid policy blocked it because the department is not "finance".

The agent explains that the refund was blocked due to department restrictions.

The key insight: the agent code knows nothing about departments. The interceptor
and policy handle this entirely at the gateway layer, outside the LLM's reach.

Press <kbd>Ctrl+C</kbd> to exit.

## Step 12: View Policy Decisions in CloudWatch

Policy evaluation decisions are emitted as CloudWatch metrics under the
`AWS/Bedrock-AgentCore` namespace. You can track authorization trends and set
alarms on denial spikes.

Open the CloudWatch Metrics console and look under the `AWS/Bedrock-AgentCore`
namespace. The available metrics include:

| Metric | What it measures |
|---|---|
| `AllowDecisions` | Count of permitted tool calls |
| `DenyDecisions` | Count of blocked tool calls |
| `Latency` | Policy evaluation time in milliseconds |

Each metric has dimensions for `PolicyEngine`, `ToolName`, and `Mode`, so you can
filter by specific policies or tools.

In production, set a CloudWatch Alarm on `DenyDecisions` to alert when denials
spike (could indicate a misconfigured policy or an attack). You already know how
to create alarms from Part 9.

## Summary

You added a full authorization and data-filtering layer to the existing gateway
without modifying agent code:

- Policy engine attached to `workshop-gateway`, first in `LOG_ONLY` for safe
  testing, then in `ENFORCE` for real blocking
- Permit policies for read-only tools (unrestricted) and refund processing
  (parameter-constrained, RBAC via JWT scopes)
- Forbid policies for time-based restrictions and emergency shutdowns,
  demonstrating forbid-wins semantics
- Response interceptor that redacts internal business data (wholesale costs,
  margins, supplier IDs) from tool responses, distinct from Guardrails PII
  filtering which operates at the model layer
- Request interceptor with short-circuit that caches expensive Knowledge Base
  queries and supports a maintenance-mode pattern for planned outages
- Request interceptor with context enrichment that injects department from JWT
  claims, enabling Cedar policies to make decisions based on dynamic context

The three-layer model for production agents:

| Layer | Mechanism | What it handles |
|---|---|---|
| Authorization | Cedar policies | Declarative permit/forbid rules (who can call what, with what parameters) |
| Dynamic logic | Lambda interceptors | Runtime enrichment, caching, redaction, maintenance blocking |
| Content safety | Bedrock Guardrails | PII filtering, topic denial, harmful content blocking at the model layer |

All three layers enforce outside agent code, where prompt injection cannot reach
them.

---

⬅️ [Back: Part 9 — Evaluate Agent Quality](part-09-evaluate-agent-quality.md) | [Overview](README.md) | ➡️ [Next: Clean Up](part-11-cleanup.md)
