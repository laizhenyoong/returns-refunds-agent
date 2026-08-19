# Clean Up

**Estimated time:** ~5 minutes

In this final part, you'll remove all the resources created during the workshop to
avoid ongoing AWS charges.

> **Destructive operations ahead.** The commands below permanently delete
> resources and data. Only proceed if you are finished with the workshop and no
> longer need these resources.

---

## Step 1: Remove AgentCore Resources

The AgentCore CLI manages the deployed agent, memory, and gateway resources through
CDK. To clean up, first remove all resources from your local configuration, then
deploy to tear down the AWS resources.

Make sure you're in your agent project directory:

💻 **Terminal Command:**

```bash
cd ~/ReturnsRefundsAgentProject/AgentCoreProject
```

Remove all resources from the project configuration using the interactive TUI:

💻 **Terminal Command:**

```bash
agentcore
```

Select **remove** from the TUI home screen, then choose the resources to remove
(agent, memory, gateway, targets). Remove all of them.

Then deploy to tear down the corresponding AWS resources:

💻 **Terminal Command:**

```bash
agentcore deploy
```

The remove command resets the `agentcore/agentcore.json` configuration while
preserving `agentcore/aws-targets.json` and deployment state. The subsequent
deploy detects the removed resources and tears down the corresponding AWS
infrastructure (CloudFormation stacks, IAM roles, etc.).

> If the deploy step reports that a resource was already removed, that's expected
> — it handles missing resources gracefully.

## Step 2: Remove Lambda Functions and Cognito

The Lambda functions and Cognito User Pool were created outside of the AgentCore
CDK stack, so they need to be removed separately. Ask Kiro to clean them up.

🤖 **Kiro Vibe Prompt:**

```
Delete all the Lambda functions and IAM roles we created during this workshop.
Also delete the Cognito User Pool we created for gateway authentication.
Use the configuration files in the project to find the resource IDs.
Handle missing resources gracefully.
```

> Kiro will read the project's configuration files to find the Lambda ARNs,
> Cognito User Pool ID, and IAM role names, then delete them using the AWS CLI or
> boto3.

## Step 3: Remove Evaluation Resources

If you completed Part 9, you have an online evaluation config and a custom
evaluator to remove. Online evaluation configs must be paused before deletion.

> If you skipped Part 9, skip this step and proceed to Step 4.

Pause the online evaluation if it's still running:

💻 **Terminal Command:**

```bash
agentcore pause
```

Select `returns-agent-quality-monitor` when prompted.

Remove the online evaluation config and custom evaluator from your project:

💻 **Terminal Command:**

```bash
agentcore remove
```

Select **online-eval** and remove `returns-agent-quality-monitor`. Then run
`agentcore remove` again and select **evaluator** to remove
`ReturnsWorkflowCompliance`.

Deploy to delete the AWS resources:

💻 **Terminal Command:**

```bash
agentcore deploy
```

## Step 4: Remove Policy and Interceptor Resources

If you completed Part 10, remove the policy engine, interceptor Lambdas, and the
`refund-target`.

> If you skipped Part 10, skip this step and proceed to Step 5.

Remove the policy engine from your project:

💻 **Terminal Command:**

```bash
agentcore remove policy-engine --name returns-policy-engine
```

Remove the refund gateway target:

💻 **Terminal Command:**

```bash
agentcore remove
```

Select **Gateway Target** and remove `refund-target`.

Deploy to tear down the policy engine and target:

💻 **Terminal Command:**

```bash
agentcore deploy
```

Delete the interceptor and refund Lambda functions:

🤖 **Kiro Vibe Prompt:**

```
Delete the following Lambda functions we created in Part 10:
- refund_processing
- response_interceptor
- request_interceptor

Use the AWS CLI. Handle missing functions gracefully.
```

## Step 5: CloudFormation-Managed Resources

Resources provisioned by the workshop CloudFormation template (EC2 instance,
Knowledge Base, DynamoDB tables) are automatically cleaned up when the
CloudFormation stack is deleted. If you're at an AWS event, this happens
automatically when the event ends. No manual action is needed for these resources.

## Congratulations!

You've completed the entire AgentCore CLI workshop. Here's what you built:

- Scaffolded and deployed a basic agent with the AgentCore CLI
- Customized it into a returns and refunds assistant with Kiro
- Added persistent memory for cross-session recall
- Connected external data via gateway (DynamoDB tables + Knowledge Base)
- Built a Streamlit UI with Cognito authentication
- Explored observability with logs, traces, and the GenAI dashboard
- Evaluated agent quality with on-demand, online, and batch evaluations
- Secured tool access with Cedar policies and Lambda interceptors
- Cleaned up all workshop resources

---

⬅️ [Back: Part 10 — Secure Tool Access with Policies](part-10-secure-tool-access-policies.md) | [Overview](README.md)
