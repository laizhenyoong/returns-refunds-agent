# Part 8: Try the AgentCore Harness (Preview)

**Estimated time:** ~20 minutes

So far in this workshop you've built and deployed a Strands agent to AgentCore
Runtime. You wrote tools, wired up memory, plugged in a gateway, and shipped a UI.
Every line of agent logic is code you (or Kiro) authored.

In this part, you'll try a different deployment shape: the **AgentCore Harness**
(currently in preview). The harness flips the model from "code-first" to
"config-first" — instead of writing the orchestration loop yourself, you declare
what the agent should do (model, system prompt, tools, memory) and AgentCore runs
the loop for you in a managed microVM.

You'll create a sibling harness called `CustAssistantHarness` in the same project
and wire it up with three complementary tools:

- The `workshop-gateway` you built in Part 4 (for `order_lookup`, `user_lookup`,
  `product_lookup`, `policy_retrieval`)
- The built-in **AgentCore Browser** for live external lookups (verifying policies
  on amazon.com, checking current product prices)
- The built-in **AgentCore Code Interpreter** for deterministic math (refund
  line-item calculations, return-window date math)

> **Preview note:** AgentCore Harness is in public preview in `us-east-1`,
> `us-west-2`, `eu-central-1`, and `ap-southeast-2`. APIs and CLI flags may evolve.
> See the official preview docs for the latest.

> **Prerequisites:** You must have completed Parts 1–7. Part 4 in particular is
> required because the harness will reuse the `workshop-gateway` you created there.

---

## Step 1: Understand How Harness Differs

Both Runtime agents and Harnesses are first-class AgentCore primitives, but they
target different developer flows.

| | Runtime Agent (Parts 1-7) | Harness (this part) |
|---|---|---|
| What you write | Python code with the Strands SDK, custom `@tool` functions, memory wiring | A `harness.json` config — model, prompt, tools, memory references |
| Where the loop runs | Your code defines the loop; AgentCore Runtime executes your code | AgentCore runs a managed Strands loop on your behalf |
| Container | You deploy your code as a runtime agent | Each session gets its own isolated microVM with filesystem + shell |
| Switching models | Edit code, redeploy | Override `--model-id` at invoke time, no redeploy |
| Built-in tools | You wire them in via Strands | `agentcore_browser`, `agentcore_code_interpreter` available out of the box |
| Best for | Long-lived production agents with custom logic | Rapid experimentation, multi-tool agents that need a fresh environment per session |

The harness is roughly: "managed Strands as a service." When the workflow you need
is conversation + tool calls + maybe a fresh sandbox per session, the harness
handles all the plumbing — and it can plug straight into the same AgentCore Gateway
your runtime agent uses, so the same tools are available to both.

## Step 2: Add a Harness with All Three Tools

You'll add the harness alongside your existing runtime agent. The AgentCore CLI
supports both in the same project, and the `agentcore add` wizard lets you select
the gateway, browser, and code interpreter in one shot.

Make sure you're in your project directory:

💻 **Terminal Command:**

```bash
cd ~/ReturnsRefundsAgentProject/AgentCoreProject
```

Then add a harness using the interactive wizard:

💻 **Terminal Command:**

```bash
agentcore add
```

Walk through the wizard with the selections below. The wizard will pause at the
gateway question to ask for the Gateway ARN and the credential provider for
outbound OAuth — you'll use Kiro to look those up while the wizard waits.

- Resource: **Harness**
- Harness name: `CustAssistantHarness`
- Model provider: **Amazon Bedrock**
- Model: same Claude inference profile you used for the runtime agent
- Custom environment: **Default Environment**
- Memory: **Enabled** (you can attach the `CustomerAssistantMemory` resource from
  Part 3, or skip to a fresh memory)
- Advanced settings: Tools selected → pick **AgentCore Browser**, **AgentCore Code
  Interpreter**, **AgentCore Gateway**
- Gateway ARN: paste the value Kiro returns (see prompt below)
- Gateway outbound auth: **OAuth**
- Credential provider ARN: paste the value Kiro returns (see prompt below)
- OAuth scopes: paste the scope value from `cognito_config.json` (Part 4 wrote it
  during gateway setup — `https://gateway.workshop.local/invoke`)
- **Confirm**

> The wizard does not ask for a system prompt. It scaffolds
> `app/CustAssistantHarness/harness.json` with default settings; you'll set the
> system prompt by editing that file in the next step.

### While the wizard is paused, get the Gateway ARN

🤖 **Kiro Vibe Prompt:**

```
Get me the ARN of the workshop-gateway we created in Part 4.
Run `agentcore status` and look for the gateway entry, or read the gateway ARN from the agentcore project config files. Print just the ARN.
```

### While the wizard is paused, create the OAuth credential provider

The gateway uses Custom JWT (Cognito) for inbound auth, so the harness needs
outbound OAuth credentials to call it. We'll register the existing Cognito client as
an OAuth2 credential provider in AgentCore Identity.

🤖 **Kiro Vibe Prompt:**

```
Create an OAuth2 credential provider in AgentCore Identity that the harness can use to authenticate against the workshop-gateway.

Steps:
1. Read Cognito credentials from cognito_config.json in the project root: client_id, client_secret, token_endpoint, and the scope value (the scope is a Cognito resource-server identifier like https://gateway.workshop.local/invoke — use the exact value from the file).
2. Use the AWS CLI (bedrock-agentcore-control) or the AgentCore SDK to create a credential provider named "workshop-gateway-cognito" with grant type client_credentials, the Cognito token endpoint, and the scope from cognito_config.json.
3. Print the resulting credential provider ARN — I'll paste it into the agentcore add wizard.

Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-outbound-credential-provider.html
```

Once the wizard accepts both ARNs and the OAuth scope, it scaffolds
`app/CustAssistantHarness/` with a `harness.json` containing all three tools.

After confirmation, your `harness.json` should include the `agentcore_gateway`
entry with OAuth outbound auth, plus the browser and code_interpreter entries — for
example:

```json
"tools": [
  { "type": "agentcore_browser", "name": "browser" },
  { "type": "agentcore_code_interpreter", "name": "code_interpreter" },
  {
    "type": "agentcore_gateway",
    "name": "workshop-gateway",
    "config": {
      "agentCoreGateway": {
        "gatewayArn": "arn:aws:bedrock-agentcore:us-west-2:<account>:gateway/workshop-gateway-...",
        "outboundAuth": {
          "oauth": {
            "credentialProviderName": "workshop-gateway-cognito",
            "scopes": ["https://gateway.workshop.local/invoke"]
          }
        }
      }
    }
  }
]
```

### Set the harness system prompt

The wizard didn't ask for a system prompt, so the scaffolded harness uses a default.
Replace it with the same Returns & Refunds prompt the runtime agent uses, so both
agents have an identical persona and instructions.

> Depending on your AgentCore CLI version, the system prompt lives in one of two
> places under `app/CustAssistantHarness/`:
> - a sibling `system-prompt.md` (or similar) Markdown file referenced from
>   `harness.json`, or
> - a `systemPrompt` field directly inside `harness.json`.
>
> Kiro will inspect your scaffold and update the right one.

🤖 **Kiro Vibe Prompt:**

```
Open the harness scaffold under app/CustAssistantHarness/ and update the system prompt so it matches exactly the SYSTEM_PROMPT we used for the runtime agent in Part 2 (in app/CustomerAssistantAgent/main.py).

The system prompt may live in one of two places depending on the CLI version:
- a sibling Markdown file like app/CustAssistantHarness/system-prompt.md (or system_prompt.md) referenced from harness.json, OR
- a systemPrompt field directly inside harness.json.

Inspect both files and update whichever one is the active source of the prompt. Replace the entire prompt content with this exact text:

You are a Returns & Refunds Assistant. You help administrators with:
- Looking up customer orders and account information
- Checking return eligibility for customer orders
- Calculating refund amounts
- Answering questions about return policies

The user is an administrator who can access all customer data.
Be helpful and concise. Always confirm details before
processing any return or refund.

After the edit, run `agentcore validate` to confirm the configuration is well-formed.
```

## Step 3: Deploy the Harness

Deploy the project the same way you've deployed runtime agents:

💻 **Terminal Command:**

```bash
agentcore deploy
```

This creates the harness alongside your existing runtime agent and provisions the
OAuth credential provider. The first deployment takes 2–3 minutes.

Confirm both resources exist:

💻 **Terminal Command:**

```bash
agentcore status
```

You should see two agents: the runtime `CustomerAssistantAgent` (READY) and the
harness `CustAssistantHarness` (READY), plus your existing `workshop-gateway`.

## Step 3b: Pre-subscribe the Harness's Default Model

The harness defaults to `global.anthropic.claude-sonnet-4-6` on first use. The
harness's execution role has permission to invoke that model but not to subscribe to
it through AWS Marketplace, so a first invocation from inside the harness fails
with an `AccessDeniedException` on the model subscription.

The fix is to invoke the model once from your own credentials (which can complete
the Marketplace subscription) before the harness ever calls it. After that, the
model is subscribed account-wide and every subsequent harness invocation just works.

🤖 **Kiro Vibe Prompt:**

```
Invoke the Claude Sonnet 4.6 cross-region inference profile once from my own AWS credentials so it gets subscribed in this account before the AgentCore Harness tries to call it. The harness execution role has bedrock:InvokeModel but not the AWS Marketplace subscribe permissions, so the first call has to come from a principal that can complete the Marketplace subscription.

Steps:
1. Use the AWS CLI in the workshop region to call `bedrock-runtime invoke-model` (or `converse`) against the inference profile `global.anthropic.claude-sonnet-4-6` with a trivial prompt like "ping".
2. If the call returns a Marketplace subscription requirement instead of completing, accept/complete the subscription on the model in the Bedrock console (or via the AWS Marketplace SubscribeAgreement API), then retry.
3. Confirm the call returns a normal model response on the second try.

This only needs to run once per AWS account.
```

> **Why this is needed.** The execution role attached to a freshly-deployed harness
> can call `bedrock:InvokeModel`, but Marketplace-fronted Anthropic models require
> an account-level subscription that's normally established the first time someone
> in the account invokes the model. Workshop participants typically have that
> subscribe permission on their own role; the harness role doesn't. Doing the first
> invocation manually completes the subscription so the harness can use the model
> afterward.

## Step 4: Explore the Harness in the Agent Inspector

`agentcore dev` provisions any missing AWS resources, starts a local server, and
opens a browser-based agent inspector where you can chat with the harness, watch
every tool call execute, and inspect traces in real time. The inspector is the
primary way you'll explore a multi-tool harness.

💻 **Terminal Command:**

```bash
agentcore dev
```

When the inspector opens, select `CustAssistantHarness` from the resource picker
(the project also contains the runtime agent, so you need to pick which one to
attach to).

Once the inspector loads, run the following prompts one by one to exercise each
tool surface. Watch the Traces panel in the inspector to see exactly which tool the
harness calls for each prompt.

### Gateway-backed lookups (DynamoDB + Knowledge Base)

💬 **Agent Test Prompt:**

```
Look up customer C-01 and list their orders.
```

The harness routes through `workshop-gateway` to call the `user_lookup` and
`order_lookup` Lambdas, returning Rajesh Kumar's profile and orders from DynamoDB.

💬 **Agent Test Prompt:**

```
What is the return policy for electronics in India?
```

This time it's `policy_retrieval` reaching the Bedrock Knowledge Base.

### Browser — verify against an external source

💬 **Agent Test Prompt:**

```
Visit amazon.com's official US returns policy page and quote the standard return window for electronics. Then compare it against what our internal knowledge base says (use the policy_retrieval tool). Tell me whether they agree.
```

The harness uses the browser to navigate to amazon.com's public help page, then
chains to `policy_retrieval` through the gateway, and compares the two.

### Code interpreter — refund math

💬 **Agent Test Prompt:**

```
Compute the refund for an order with these details: subtotal $349.99, shipping $19.99, sales tax 10%, the customer is requesting return on day 8 of a 30-day return window, restocking fee 15% per our policy. Show every line item and the final refund amount.
```

The agent calls `code_interpreter`, writes a small Python snippet to compute each
line, and returns a clear breakdown — the kind of math LLMs are unreliable at
without a sandbox.

### Combined — all three tools in one conversation

💬 **Agent Test Prompt:**

```
Customer C-02 is asking about returning order ORD-002.

1. Use the gateway to look up the order details and the customer's country.
2. Use the gateway to fetch the return policy for that product category in the customer's country.
3. Use the browser to verify the return window against amazon.com's published policy for the same country.
4. Use code_interpreter to compute the refund: assume subtotal is the order price, shipping was $9.99, sales tax 8%, and apply any restocking fee from the policy if applicable.

Give me a final summary with the refund amount and whether the request is within the return window.
```

This single prompt exercises all three tool surfaces in a coordinated workflow —
the kind of multi-tool reasoning the harness orchestrates without any extra code.

> Expand **Harness Settings → Override** in the inspector to tweak config (model,
> prompt, tools) for the current session without redeploying. When you find a
> config you like, copy it into `app/CustAssistantHarness/harness.json` and run
> `agentcore deploy` to make it the new default.

Press <kbd>Ctrl+C</kbd> in the terminal to stop the dev server when you're done.

## What You Just Built

You've added a managed AgentCore Harness to the same project as your custom Strands
runtime agent, with three complementary tool surfaces:

- `workshop-gateway` (with OAuth outbound auth via Cognito) for internal
  customer/order/product/policy lookups
- AgentCore Browser for live external verification (e.g., Amazon's public policy
  pages)
- AgentCore Code Interpreter for deterministic refund math and date arithmetic

You exercised:

- Gateway-only queries (`Look up customer C-01`) in the agent inspector
- Browser-only verification (compare internal KB against amazon.com)
- Code-interpreter math (line-item refund breakdown)
- A combined workflow chaining all three tools in one prompt
- Live exploration in the `agentcore dev` browser inspector (selecting the harness
  from the resource picker), with per-session config overrides via **Harness
  Settings → Override**

**When to pick which?**

- Reach for a **runtime agent** when you have custom domain logic, Lambda-backed
  tools, and a stable production workload that benefits from full code control.
  That's exactly what Parts 1–7 built.
- Reach for a **harness** when you want to spin up an agent fast, experiment across
  models, mix internal and external tools without writing orchestration, and rely
  on a managed per-session sandbox. Internal tools, prototypes, and complex
  multi-tool workflows are where the harness shines.

The two are complementary, not competing — the same project can host both, and they
share infrastructure like gateways and memory resources.

---

⬅️ [Back: Part 7 — Make It Yours](part-07-open-ended-enhancements.md) | [Overview](README.md) | ➡️ [Next: Part 9 — Evaluate Agent Quality](part-09-evaluate-agent-quality.md)
