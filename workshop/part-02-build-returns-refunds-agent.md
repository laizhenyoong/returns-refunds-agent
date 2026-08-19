# Part 2: Build the Returns & Refunds Agent

**Estimated time:** ~25 minutes

In this part, you'll use Kiro to transform your basic agent into a domain-specific
returns and refunds assistant. You'll add a system prompt that defines the agent's
persona and create custom inline tools using the Strands `@tool` decorator. Then
you'll test locally and redeploy to AgentCore Runtime.

> **Prerequisites:** You must have completed Part 1 with a deployed agent. Make sure
> you're in your agent project directory (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

---

## Step 1: Add a Domain-Specific System Prompt

Right now your agent is a generic assistant. Let's give it a focused role — a returns
and refunds specialist that helps customers with return eligibility, refund
calculations, and return policies.

Open `AgentCoreProject/app/CustomerAssistantAgent/main.py` in Kiro and use the
following prompt to update the system prompt:

🤖 **Kiro Vibe Prompt:**

```
Update AgentCoreProject/app/CustomerAssistantAgent/main.py
to add a system prompt for a returns and refunds assistant:
- The agent should introduce itself as a Returns & Refunds Assistant
- The user is an administrator who can access customer data, orders, and return policies
- It helps administrators check return eligibility, calculate refund amounts, and answer questions about return policies on behalf of customers
- The system prompt should instruct the agent to be helpful, concise, and always confirm details before processing any return or refund
- Keep the existing agent setup and just add the system_prompt parameter to the Agent constructor
```

**Expected output in `main.py`:**

Kiro should update the `Agent()` constructor to include a `system_prompt` parameter
with instructions for the returns and refunds role. The file should look something
like this:

```python
from strands import Agent

SYSTEM_PROMPT = """You are a Returns & Refunds Assistant. You help administrators with:
- Looking up customer orders and account information
- Checking return eligibility for customer orders
- Calculating refund amounts
- Answering questions about return policies

The user is an administrator who can access all customer data.
Be helpful and concise. Always confirm details before
processing any return or refund."""

agent = Agent(system_prompt=SYSTEM_PROMPT)
```

Review the generated code to make sure the system prompt looks reasonable, then move
on to the next step.

## Step 2: Add Custom Tools

Now let's give the agent real capabilities by adding inline tools. Strands uses the
`@tool` decorator to turn regular Python functions into tools that the agent can call
during a conversation. Each tool has a docstring that tells the agent when and how to
use it.

We'll add the following four tools to our agent:

| Tool | Purpose | Implementation |
|---|---|---|
| `get_current_time` | Returns current date and time | Strands built-in tool |
| `order_lookup` | Looks up order details by order ID | Dummy/mock (replaced with real data in Part 4) |
| `user_lookup` | Retrieves customer information by user ID | Dummy/mock (replaced with real data in Part 4) |
| `product_lookup` | Retrieves product information by product ID | Dummy/mock (replaced with real data in Part 4) |
| `policy_retrieval` | Retrieves return policy for a product category and country | Dummy/mock (replaced with real data in Part 4) |

The `get_current_time` tool uses the Strands built-in `current_time` tool. The other
three are dummy implementations with mock data for now — we'll replace them with real
data sources (DynamoDB and Knowledge Base) in Part 4 when we add the gateway.

> We're providing a comprehensive prompt here for simplicity during the event. In
> practice, you can achieve the same result using a more conversational approach with
> Kiro — adding one tool at a time, iterating on the implementation, and refining as
> you go.

🤖 **Kiro Vibe Prompt:**

```
Update AgentCoreProject/app/CustomerAssistantAgent/main.py to add the following tools:

1. get_current_time()
   - Use the Strands built-in current_time tool from strands_tools
   - Returns the current date and time

2. order_lookup(order_id: str)
   - A dummy @tool that looks up order details by order ID
   - Use mock data with sample orders:
     - "ORD-001": customer C-01, product P-001 (iPhone 15 Pro), status DELIVERED, purchased 5 days ago
     - "ORD-002": customer C-02, product P-003 (Kindle Paperwhite), status DELIVERED, purchased 45 days ago
     - "ORD-003": customer C-01, product P-005 (PlayStation 5), status SHIPPED
   - Return order details as a formatted string

3. user_lookup(user_id: str)
   - A dummy @tool that retrieves customer information by user ID
   - Use mock data:
     - "C-01": Rajesh Kumar, country IN, email rajesh@example.com
     - "C-02": Sarah Johnson, country US, email sarah@example.com
     - "C-03": James Wilson, country UK, email james@example.com
   - Return customer details as a formatted string

4. product_lookup(product_id: str)
   - A dummy @tool that retrieves product information by product ID
   - Use mock data:
     - "P-001": iPhone 15 Pro, Apple, phone
     - "P-002": Kindle Paperwhite, Amazon, e-book
     - "P-003": iPad Air, Apple, tablet
   - Return product details as a formatted string

5. policy_retrieval(query: str)
   - A dummy @tool that retrieves return policy information
   - Use mock data with policies for categories: "electronics" (30-day return, 100% refund if unopened), "clothing" (60-day return, full refund), "books" (14-day return, 50% refund)
   - Return the policy details as a string

Make sure to update dependencies in pyproject.toml.
```

**Expected output in `main.py`:**

Kiro should add the tool functions and wire them into the agent. The key parts
should look like this:

```python
from strands import Agent
from strands.tool import tool
from strands_tools import current_time

@tool
def order_lookup(order_id: str) -> str:
    """Look up order details by order ID."""
    ...

@tool
def user_lookup(user_id: str) -> str:
    """Retrieve customer information by user ID."""
    ...

@tool
def product_lookup(product_id: str) -> str:
    """Retrieve product information by product ID."""
    ...

@tool
def policy_retrieval(query: str) -> str:
    """Retrieve return policy information."""
    ...

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[current_time, order_lookup, user_lookup, product_lookup, policy_retrieval],
)
```

### Understanding the `@tool` Decorator

The Strands `@tool` decorator is how you give agents capabilities beyond
conversation. Here's what it does:

- **Turns a function into a tool** — The agent can decide to call the function
  during a conversation when it's relevant to the user's question.
- **Uses the docstring as the tool description** — The agent reads the docstring to
  understand when to use the tool. Write clear, descriptive docstrings.
- **Uses type hints for parameters** — The agent uses the function signature to know
  what arguments to pass. Always include type hints.
- **Returns a string** — The tool's return value is passed back to the agent as
  context for generating its response.

This pattern keeps tools simple and testable — they're just regular Python functions
with a decorator.

> Review the generated code carefully. Make sure `current_time` is imported from
> `strands_tools`, the `@tool` decorator is imported from `strands.tool`, and all
> four tools are included in the `tools` list passed to the `Agent()` constructor in
> `main.py`.

## Step 3: Add a Dependency Sync Hook

When Kiro modifies your agent code, it may add new imports that require updating
`pyproject.toml`. To keep dependencies in sync automatically, let's create an agent
hook that runs `uv sync` whenever `pyproject.toml` changes.

🤖 **Kiro Vibe Prompt:**

```
Create an agent hook that watches for changes to pyproject.toml.
When the file is edited, it should automatically run "uv sync" to install any new or updated dependencies.
Invoke the hook for initial sync up.
```

Kiro will create a hook configuration under `.kiro/hooks/`. From now on, any time a
dependency is added to `pyproject.toml`, the hook will automatically sync your Python
environment.

> This hook saves you from manually running `uv sync` every time dependencies
> change. It's especially useful as we add more packages in later parts of the
> workshop.

## Step 4: Test Locally

Let's verify the system prompt and tools work correctly before redeploying. Start the
local development server:

💻 **Terminal Command:**

```bash
agentcore dev
```

**Expected output:**

```
Dev Server

Agent: CustomerAssistantAgent
Server: http://localhost:8080/invocations
Status: running

>
```

Test the order lookup tool:

💬 **Agent Test Prompt:**

```
Look up order ORD-001
```

The agent should call `order_lookup` and return details about Rajesh Kumar's iPhone
15 Pro order.

Now test the return policy tool:

💬 **Agent Test Prompt:**

```
What's the return policy for electronics?
```

The agent should call `policy_retrieval` and return the 30-day return window with
100% refund if unopened.

Try looking up a customer:

💬 **Agent Test Prompt:**

```
Get info for customer C-02
```

The agent should call `user_lookup` and return Sarah Johnson's details.

Press <kbd>Ctrl+C</kbd> to stop the local development server.

> The agent's exact wording will vary, but it should use the correct tool and return
> accurate information from the mock data. If the agent doesn't call the tools,
> check that the `tools` parameter is correctly passed to the `Agent()` constructor
> in `main.py`.

## Step 5: Redeploy to AgentCore Runtime

Your agent now has a domain-specific system prompt and custom tools. Redeploy it to
AgentCore Runtime so the cloud version is updated:

💻 **Terminal Command:**

```bash
agentcore deploy
```

> This redeployment is faster than the first one since infrastructure is already
> provisioned. It typically takes 1-2 minutes.

**Expected output:** The agent will be updated in AWS.

## Step 6: Test the Deployed Agent

Verify the deployed agent uses your custom tools correctly by invoking it in the
cloud:

💻 **Terminal Command:**

```bash
agentcore invoke
```

Test with an order lookup:

💬 **Agent Test Prompt:**

```
Look up order ORD-003 and tell me its status
```

The agent should call `order_lookup` and report that ORD-003 (PlayStation 5) is
currently SHIPPED.

Test a combined query:

💬 **Agent Test Prompt:**

```
Look up customer C-01 and check the return policy for their electronics order.
```

The agent should use both `user_lookup` and `policy_retrieval` to provide a
personalized response.

Press <kbd>Ctrl+C</kbd> to exit the session.

## What You Just Built

You've transformed a generic agent into a domain-specific returns and refunds
assistant:

- ✅ Added a system prompt that defines the agent's role and behavior
- ✅ Created five tools: `get_current_time` (Strands built-in), `order_lookup`,
  `user_lookup`, `product_lookup`, `policy_retrieval` (dummy/mock)
- ✅ Tested locally with `agentcore dev`
- ✅ Redeployed with `agentcore deploy`
- ✅ Verified tools work on the deployed agent with `agentcore invoke`

The agent currently uses mock data for orders, users, and policies. In Part 4, we'll
replace the dummy tools with real data from DynamoDB and a Knowledge Base via the
gateway. But first, in Part 3, you'll add persistent memory so the agent can remember
customer preferences across sessions.

> **Why memory before real data?** The mock tools are intentional — they let you test
> the agent's behavior without worrying about infrastructure. We'll replace them with
> real DynamoDB and Knowledge Base data in Part 4. But first, adding memory in Part 3
> means your agent can recall customer preferences when we connect real data — making
> the full experience much more powerful.

---

⬅️ [Back: Part 1 — Create and Deploy a Basic Agent](part-01-create-and-deploy-basic-agent.md) | [Overview](README.md) | ➡️ [Next: Part 3 — Add Persistent Memory](part-03-persistent-memory.md)
