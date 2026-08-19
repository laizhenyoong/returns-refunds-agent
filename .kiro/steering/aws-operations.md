# AWS Operations & CLI

Guidance for running AWS and AgentCore operations for this project.

## Region

- **Target `us-west-2` for every AWS operation.** Pass the region explicitly:
  - AWS CLI: `--region us-west-2`
  - boto3 / SDK clients: `region_name="us-west-2"`
  - AgentCore configuration: set the region explicitly, don't rely on defaults.

## AWS CLI Conventions

- **Always include `--no-cli-pager`** when running AWS CLI commands from a terminal.
  The pager blocks non-interactive execution, so it must be disabled on every invocation.

  ```bash
  aws sts get-caller-identity --region us-west-2 --no-cli-pager
  ```

- Prefer non-interactive flags. Avoid commands that open editors or prompt for input.

## AgentCore CLI

- Confirm current AgentCore CLI commands and options against the official AWS
  documentation before running them (see the documentation-first steering).
- Keep AgentCore configuration explicit and minimal, targeting `us-west-2`.

## Best Practices & Safety

- Follow AWS best practices as described in the official documentation.
- Treat deployments, IAM changes, and anything affecting live/shared resources as
  higher-risk: explain the action and confirm before running it.
- Prefer least-privilege IAM and explicit configuration over broad defaults.
