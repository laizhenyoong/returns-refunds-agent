# Part 3: Add Persistent Memory for Cross-Session Recall

**Estimated time:** ~25 minutes

In this part, you'll add persistent memory to your agent so it can remember customer
preferences and past interactions across sessions. You'll use the AgentCore CLI to
create a memory resource, then use Kiro to integrate the memory session manager into
your agent code. Finally, you'll seed the memory with customer data and verify the
agent can recall it.

> **Prerequisites:** You must have completed Part 2 with a deployed returns and
> refunds agent. Make sure you're in your agent project directory
> (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

**Architecture:** Adding AgentCore Memory.

---

## Step 1: Add a Memory Resource

The `agentcore add memory` command creates and configures an AgentCore Memory
resource for your agent. Memory gives your agent the ability to persist information
across conversations — customer preferences, interaction history, and semantic facts
— so it can provide personalized, context-aware responses.

💻 **Terminal Command:**

```bash
agentcore add
```

You will see prompts to ask options to select. Follow the steps below:

- Select **Memory**
- Type your memory name. For example `CustomerAssistantMemory`
- Select **7 days** for expiry duration
- Select **No** for memory record streaming
- Select only the **User preference** strategy
- **Confirm**

Then deploy the project again:

💻 **Terminal Command:**

```bash
agentcore deploy
```

It will start deployment of the project. It will deploy incremental changes only.

> Memory resource creation takes 2-3 minutes. The CLI provisions the underlying
> storage and configures the memory strategy for your agent. You can read the next
> section about memory strategies while you wait.

### Understanding Memory Strategies

AgentCore Memory supports several complementary strategies to store and retrieve
information from conversations. For this workshop we'll use **User preference**
memory, but it's worth knowing what the others do.

**User Preference Memory (used in this workshop)**

Extracts and stores explicit user preferences mentioned during conversations. When a
customer says "I prefer email communication" or "My favorite product category is
electronics," the memory service captures these as structured preference records. The
agent can retrieve them in future sessions to personalize responses. This is the
strategy most directly useful for a returns and refunds assistant.

**Other strategies (not used in this workshop)**

- **Summary Memory** — Stores a running summary of each conversation session, helping
  the agent recall general context across sessions.
- **Semantic Memory** — Stores factual information as embeddings so the agent can
  retrieve specific facts using vector similarity, even when the query doesn't match
  the original wording.
- **Episodic Memory** — Captures meaningful slices of interactions as structured
  episodes (situation, intent, outcome) and generates reflections across multiple
  episodes to learn from past outcomes.

You can layer these on top of User preference later by running `agentcore add`
again. For now, User preference is enough to demonstrate cross-session recall.

## Step 2: Integrate Memory into Agent Code

Now that the memory resource is created, you need to update your agent code to use
it.

Open `app/CustomerAssistantAgent/main.py` in Kiro and use the following prompt to
integrate memory:

🤖 **Kiro Vibe Prompt:**

```
I have added a new memory using AgentCore CLI.
Update app/CustomerAssistantAgent/main.py to integrate it.
Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/strands-sdk-memory.html
Find the new memory ID (not ARN) using CLI and update agentcore/.env.local.
Add memory ID to envVars of the runtime in agentcore/agentcore.json — write the **literal memory ID value** (e.g., `RefundAgentMemory-AbCdEf12`), NOT a `${VARIABLE}` placeholder. The AgentCore CLI does not expand env vars in this file; placeholders propagate verbatim into the runtime IAM policy and cause AccessDenied errors at invoke time.
Specify the region as us-west-2.
Default the actor_id to "administrator".
Read agentcore.json to find the memory namespaces and use them for the retrieval config. Use low relevance_score as 0.3 for testing.
Do not make a common mistake: f"/users/{{{actor_id}}}/preference". Correct one is f"/users/{actor_id}/preference/"
Refer to https://strandsagents.com/docs/community/session-managers/agentcore-memory/ for the correct Strands memory integration pattern.
```

**What Kiro will update:**

- `agentcore/.env.local` — This file stores environment variables for local
  development (`agentcore dev`). Kiro adds the `MEMORY_ID` variable here so your
  agent can find the memory resource when running locally.
- `agentcore/agentcore.json` — This is the project configuration file that the
  AgentCore CLI uses for deployment. Kiro updates it to include the memory resource
  reference so that `agentcore deploy` passes the memory ID as an environment
  variable to AgentCore Runtime.

Both files need the memory ID so the agent can access memory in both local and
deployed environments.

> Review the generated code to make sure the memory integration doesn't remove your
> existing tools or system prompt. The `AgentCoreMemorySessionManager` connects to
> the memory resource you created with `agentcore add`.

## Step 3: Test Locally

With memory integrated, let's populate it with customer information by running the
agent locally and sending a message.

💻 **Terminal Command:**

```bash
agentcore dev
```

Once the agent is running, send a message to seed customer preferences:

💬 **Agent Test Prompt:**

```
Customer C-01, Rajesh Kumar, prefers email communication and his favorite product category is electronics.
```

After the agent responds, the memory service will save the conversation summary,
extracted preferences, and semantic facts within 20-30 seconds.

## Step 4: Test Memory Recall

Now verify the agent remembers the customer information from the previous
conversation. This proves memory is persisting across sessions.

Start a new local development session:

💻 **Terminal Command:**

```bash
agentcore dev
```

Query the agent about previously stored information:

💬 **Agent Test Prompt:**

```
What are the communication preferences for customer C-01?
```

The agent should recall Rajesh Kumar's preferences (email communication,
electronics) from the previous session.

## Step 5: Redeploy the Agent with Memory

With memory integrated and tested locally, redeploy your agent to AgentCore Runtime
so the cloud version also has memory capabilities:

💻 **Terminal Command:**

```bash
agentcore deploy
```

> Redeployment typically takes 1-2 minutes since infrastructure is already
> provisioned.

## Step 5b: Patch the Runtime IAM Role for Memory Access

Before testing the deployed agent, we need to fix one IAM detail in the AgentCore
Runtime execution role.

The current AgentCore CLI generates IAM policies using the older
`bedrock-agentcore:namespace` condition key, which only supports exact-string
matches. Our memory namespace template `/users/{actorId}/preferences` resolves at
runtime to a value like `/users/customer_001/preferences`, which won't match the
policy's hard-coded template string.

AgentCore Memory introduced `bedrock-agentcore:namespacePath` to handle this with
`StringLike` prefix matching. Until the CLI is updated to emit the new key, we attach
an inline policy to the runtime role to grant memory operations with the correct
condition.

🤖 **Kiro Vibe Prompt:**

```
Find the AgentCore Runtime execution role created during `agentcore deploy`. You can locate it by running `agentcore status` and reading the role ARN from the output, or by reading the executionRole field from agentcore/agentcore.json.

Attach an inline IAM policy named "MemoryNamespacePathFix" to that role that allows the deployed agent to call memory operations on our memory resource using the corrected condition key:

- Use `bedrock-agentcore:namespacePath` with the `StringLike` operator
- The pattern should match the actual memory namespace template configured in `agentcore/agentcore.json` (e.g., the value resolved from `/users/{actorId}/preference/` template). Read it from the config and substitute `*` for `{actorId}` to produce the IAM pattern, e.g., `/users/*/preference/`. Do not hardcode — the trailing `/` and singular/plural ending must match exactly what the wizard configured.
- Cover these actions: RetrieveMemoryRecords, CreateEvent, GetEvent, ListEvents, BatchCreateMemoryRecords, BatchUpdateMemoryRecords, BatchDeleteMemoryRecords
- Scope the Resource to our memory ARN (read it from agentcore/agentcore.json or agentcore/.env.local; the format is arn:aws:bedrock-agentcore:<region>:<account>:memory/<memory_id>)

Use AWS CLI in the workshop region. Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html
```

> **Why a separate inline policy?** The AgentCore CLI manages the runtime role's main
> policy via CDK and would revert any direct edits on the next `agentcore deploy`. An
> inline policy attached out-of-band is invisible to CDK, so the fix survives
> redeployments. Once the AgentCore CLI is updated to emit `namespacePath`, you can
> remove this inline policy.

## Step 6: Test the Deployed Agent with Memory

Verify that memory works on the deployed agent in the cloud, not just locally. Use
`agentcore invoke` to start a session and seed some customer data, then start a new
session to test recall.

💻 **Terminal Command:**

```bash
agentcore invoke
```

Introduce a customer:

💬 **Agent Test Prompt:**

```
Customer C-02, Sarah Johnson, prefers phone calls and mostly buys books.
```

The agent should acknowledge the preferences. Press <kbd>Ctrl+C</kbd> to end the
session.

Now start a new session and test recall:

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
What do you know about customer C-02?
```

The agent should recall Sarah Johnson's preferences (phone calls, books) from the
previous session. This confirms memory is working end-to-end on the deployed agent.

> **Think about this:** What would happen if you ask "What do you know about customer
> C-01?" — the customer whose preferences you seeded during local testing with
> `agentcore dev`? Will the deployed agent remember it? Think about your answer,
> then try the question.

Press <kbd>Ctrl+C</kbd> to exit.

> In this workshop, both local (`agentcore dev`) and deployed (`agentcore invoke`)
> agents connect to the same AgentCore Memory resource. This means memories seeded
> during local testing are also available to the deployed agent, and vice versa. Try
> it — ask the deployed agent about Rajesh Kumar (C-01) whose preferences you seeded
> during local testing in Step 3.

## What You Just Built

You've added persistent memory to your returns and refunds agent:

- ✅ Created a memory resource with `agentcore add`
- ✅ Integrated the Strands memory session manager via Kiro
- ✅ Updated `.env.local` and `agentcore.json` with the memory ID
- ✅ Seeded memory with customer preferences and interaction history
- ✅ Verified memory recall across sessions
- ✅ Redeployed the memory-enabled agent with `agentcore deploy`

Your agent now remembers customers across conversations. In the next part, you'll
connect it to real data by adding a gateway with DynamoDB tables and a Knowledge Base
for return policy retrieval.

---

⬅️ [Back: Part 2 — Build the Returns & Refunds Agent](part-02-build-returns-refunds-agent.md) | [Overview](README.md) | ➡️ [Next: Part 4 — Connect to Real Data](part-04-gateway-dynamodb-knowledge-base.md)
