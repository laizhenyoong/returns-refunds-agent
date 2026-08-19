# Part 1: Create and Deploy a Basic Agent

**Estimated time:** ~20 minutes

In this part, you'll learn the core AgentCore CLI workflow: scaffold a new agent
project, test it locally, deploy it to AgentCore Runtime, and invoke it in the cloud.
No Kiro prompts here — this is pure CLI learning so you understand the foundation
before customizing your agent.

> **Prerequisites:** Make sure you've completed Lab 1 and have your EC2 environment
> ready. Your instance comes pre-installed with Node.js 20+, Python 3.12+, AWS CDK,
> and the AgentCore CLI (`@aws/agentcore`).

**Architecture:** Generic chat agent on AgentCore Runtime.

---

## Step 1: Scaffold the Agent Project

First, open the integrated terminal in Kiro:

- macOS: Press <kbd>Ctrl+Shift+\`</kbd>
- Windows/Linux: Press <kbd>Ctrl+\`</kbd>
- Or: Go to the menu **View > Terminal**

The `agentcore create` command scaffolds a new Strands agent project with all the
boilerplate you need — an agent entry point, configuration files, and Python
dependencies. This gives you a working agent in seconds without writing any code from
scratch.

From the terminal, run the following command:

💻 **Terminal Command:**

```bash
agentcore create
```

The CLI will walk you through an interactive wizard. Enter the following when
prompted:

**Project name:**

```
Create a new AgentCore project
This will create a directory with your project name.
Project name
> AgentCoreProject
```

**What would you like to build?** — select `Agent`:

```
What would you like to build?
❯ Agent
```

**Agent name:**

```
Agent name:
> CustomerAssistantAgent
```

**Agent type** — select `Create new agent`:

```
Select agent type
❯ Create new agent
  Bring my own code
  Import from Bedrock Agents
```

For the remaining prompts, choose the following options:

- **Python** as the language
- **Direct Code Deploy** as the build
- **HTTP** as the protocol
- **Strands Agents SDK** as the framework
- **Amazon Bedrock** as the model
- **None** as the memory option
- Select **nothing** for the advanced option

Review the summary of your selections and **confirm**.

**Expected output:** A new project folder is created with the agent scaffolding.

Navigate into the newly created project directory and explore the structure in the
Kiro IDE:

- `agentcore/` — Deployment resources including JSON configurations and a CDK project
- `app/` — Agent definitions and application code to be deployed

## Step 2: Test Locally

Before deploying to the cloud, test your agent locally using `agentcore dev`. This
command starts a local development server that lets you chat with your agent in the
terminal — a fast feedback loop for development.

💻 **Terminal Command:**

```bash
cd AgentCoreProject
agentcore dev
```

**Expected output:** A Strands Agent starts running locally and prompts you for
input:

```
Dev Server

Agent: CustomerAssistantAgent
Server: http://localhost:8080/invocations
Status: running
Log: agentcore/.cli/logs/dev/dev-00000000-123456.log

>
```

Once the agent is running, try a simple message:

💬 **Agent Test Prompt:**

```
What is the capital of France?
```

The agent will answer your question using the LLM. When you're done testing, press
<kbd>Ctrl+C</kbd> to stop the local development server.

> **What happened here?** The AgentCore CLI created a project folder with a simple
> Strands agent as a starting point. It works, but has no domain-specific resources
> yet — no custom system prompt, no tools, and no memory. Check out the generated
> code in `AgentCoreProject/app/CustomerAssistantAgent/main.py`.
>
> The `agentcore dev` command uses your local AWS credentials. On the provided EC2
> environment, it uses the instance profile for IAM credentials. If you're using your
> local Kiro environment, make sure you've copied the AWS credentials from the
> workshop page.

## Step 3: Deploy to AgentCore Runtime

Now that you've verified the agent works locally, deploy it to AgentCore Runtime. The
`agentcore deploy` command packages your agent code, uploads it to AWS, and
provisions the serverless runtime infrastructure using AWS CDK — all in one command.

💻 **Terminal Command:**

```bash
# Make sure you are in the AgentCoreProject folder
agentcore deploy
```

> The first deployment takes 1-5 minutes as it packages the code, bootstraps CDK (if
> needed), and provisions the runtime infrastructure. Subsequent deployments are
> faster. You can review the agent code in `app/CustomerAssistantAgent/main.py` while
> you wait.

**Expected output:**

```
Deployed 1 stack(s): AgentCore-AgentCoreProject-default

Note: Transaction search enabled. It takes ~10 minutes for transaction search
to be fully active and for traces from invocations to be indexed.

Next: Run agentcore invoke to test your agent, or agentcore status to view
deployment status
```

Your agent is now running in the cloud with auto-scaling and monitoring built in.

## Step 4: Test the Deployed Agent

With your agent deployed, use `agentcore invoke` to send messages to the live cloud
agent. This verifies the deployment was successful and the agent responds correctly
from AgentCore Runtime.

💻 **Terminal Command:**

```bash
agentcore invoke
```

This opens an interactive session with your deployed agent. Try a test message:

💬 **Agent Test Prompt:**

```
Hi there! Tell me something interesting.
```

The response comes from your agent running on AgentCore Runtime in `us-west-2`, not
from your local machine. Press <kbd>Ctrl+C</kbd> to exit the session.

This basic agent is your foundation. In the next part, you'll use Kiro to transform
it into a domain-specific returns and refunds assistant with custom tools.

## Step 5: Update Steering Files

Before moving on, update your steering documents to include a validation rule for the
AgentCore configuration file.

🤖 **Kiro Vibe Prompt:**

```
Update the steering documents to add the following rules:
- ALWAYS run `agentcore validate` after editing agentcore.json
- In agentcore.json, runtime envVars are arrays like:
  "envVars": [{ "name": "KEY", "value": "VALUE" }]
- NEVER write `${SHELL_VARIABLE}` or `${PARAM}` placeholders into agentcore.json. The CLI does not expand environment variables in this file — placeholders propagate verbatim into the deployed CDK stack and the runtime IAM policy, producing AccessDenied errors at invoke time. Always resolve the variable yourself first (e.g., run the lookup CLI command to get the real memory ID) and write the literal value into agentcore.json.
```

This ensures Kiro will automatically validate the AgentCore configuration whenever it
makes changes to `agentcore.json` throughout the rest of the workshop.

## What You Just Built

You've completed the core AgentCore CLI workflow:

- ✅ Scaffolded a new agent project with `agentcore create`
- ✅ Tested locally with `agentcore dev`
- ✅ Deployed to AgentCore Runtime with `agentcore deploy`
- ✅ Invoked the live agent with `agentcore invoke`
- ✅ Updated steering documents with AgentCore-specific rules

This basic agent is your foundation. In the next part, you'll use Kiro to transform
it into a domain-specific returns and refunds assistant with custom tools.

---

⬅️ [Back to overview](README.md) | ➡️ [Next: Part 2 — Build the Returns & Refunds Agent](part-02-build-returns-refunds-agent.md)
