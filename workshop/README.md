# Returns & Refunds Agent Workshop — Step Guides

This folder contains the full workshop walkthrough, split into one file per part so
each step is easy to open, follow, and check off independently.

Follow the parts in order — each one builds on the agent, resources, and config
created in the previous part.

| # | Part | Est. time |
|---|------|-----------|
| 1 | [Create and Deploy a Basic Agent](part-01-create-and-deploy-basic-agent.md) | ~20 min |
| 2 | [Build the Returns & Refunds Agent](part-02-build-returns-refunds-agent.md) | ~25 min |
| 3 | [Add Persistent Memory for Cross-Session Recall](part-03-persistent-memory.md) | ~25 min |
| 4 | [Connect to Real Data — DynamoDB & Knowledge Base](part-04-gateway-dynamodb-knowledge-base.md) | ~35 min |
| 5 | [Build a Web Chat UI with Streamlit and Cognito](part-05-streamlit-ui-cognito.md) | ~25 min |
| 6 | [Explore Observability — Logs, Traces & GenAI Dashboard](part-06-observability.md) | ~10 min |
| 7 | [Make It Yours — Open-Ended Enhancements](part-07-open-ended-enhancements.md) | open-ended |
| 8 | [Try the AgentCore Harness (Preview)](part-08-agentcore-harness-preview.md) | ~20 min |
| 9 | [Evaluate Agent Quality with AgentCore Evaluations](part-09-evaluate-agent-quality.md) | ~30 min |
| 10 | [Secure Tool Access with AgentCore Policies](part-10-secure-tool-access-policies.md) | ~30 min |
| — | [Clean Up](part-11-cleanup.md) | ~5 min |

## Legend

Throughout the parts you'll see two kinds of instructions:

- 💻 **Terminal Command** — run this in a terminal (the AgentCore CLI, AWS CLI, etc).
- 🤖 **Kiro Prompt** — paste this into a Kiro chat and let Kiro make the code/resource
  changes for you.

## Prerequisites

- Completed Lab 1: Kiro IDE installed and configured on your EC2 instance (or local
  equivalent with AWS credentials).
- An AWS account with permissions for Bedrock, Cognito, Lambda, IAM, and CloudWatch.
- Node.js 20+, Python 3.12+, AWS CDK, the AgentCore CLI (`@aws/agentcore`), and Docker
  installed.

See the [project README](../README.md) for the full architecture overview and what
you'll build.
