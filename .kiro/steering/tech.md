# Tech Stack & Conventions

## Core Stack

- **Language**: Python
- **Agent framework**: Strands Agents SDK
- **Deployment / operations**: Amazon Bedrock AgentCore CLI
- **Cloud provider**: AWS (region `us-west-2`)

## Python Conventions

- **Type hints are required.** Annotate function parameters, return types, and
  non-obvious variables. Prefer precise types (`list[str]`, `dict[str, Any]`,
  `Optional[...]`) over bare containers.
- **Educational inline comments.** Explain *why* code exists, not just *what* it does.
  Comments should help a reader learning Strands and AgentCore understand the reasoning
  behind each step.
- Keep functions small, focused, and readable. One concept per function where practical.
- Follow standard Python style (PEP 8) and idiomatic patterns.

## Agent Code Conventions

- Define agent tools using the **Strands `@tool` decorator pattern**. Each tool should:
  - Have clear type hints on all parameters and the return value.
  - Include a docstring the model can use to understand when and how to call it.
  - Do one thing and demonstrate one concept.

## AWS Region

- **All AWS operations target `us-west-2`.** Set the region explicitly in SDK clients,
  AgentCore configuration, and CLI commands. Do not rely on ambient/default region
  configuration.

## Minimalism

- Prefer the smallest implementation that clearly demonstrates the concept.
- Do not add features, abstractions, or configuration beyond what the current task needs.
