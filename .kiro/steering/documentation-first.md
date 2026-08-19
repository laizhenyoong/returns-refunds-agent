# Documentation-First Workflow

**Do not rely on your own knowledge of AWS or Strands Agents.** These platforms change
frequently. Always confirm APIs, patterns, and CLI usage against the most up-to-date
official documentation using the configured MCP tools before writing or changing code.

## Mandatory: Search Before You Write

Before writing or modifying any Python code that touches **AgentCore** or **Strands
Agents**, search the relevant documentation first. This is not optional.

### For Strands Agents topics

Use the `strands-agents` MCP server:
- `search_docs` — find relevant Strands documentation for the concept you need.
- `fetch_doc` — read the specific page/section returned by the search.

Apply this to: the `@tool` decorator, agent construction, model configuration, tool
wiring, streaming, sessions, and any other Strands SDK usage.

### For AWS and AgentCore topics

Use the `awslabs.aws-documentation-mcp-server` MCP server:
- `search_documentation` — find the relevant AWS / Bedrock AgentCore pages.
- `read_documentation` — read the specific page returned by the search.

Apply this to: AgentCore CLI usage, deployment/runtime configuration, Bedrock model
access, IAM/permissions, and any other AWS service interaction.

## Workflow

1. **Identify** the AWS/Strands concept the task requires.
2. **Search** the appropriate MCP documentation server for it.
3. **Read** the specific returned document(s) to confirm current APIs and best practices.
4. **Implement** following exactly what the current documentation prescribes.
5. **Cite** the source doc (title/URL) in your explanation so the choice is traceable.

## Best Practices

- All code must follow **AWS best practices and official documentation**. When docs and
  prior assumptions disagree, the documentation wins.
- If a search returns nothing useful, refine the query before falling back to memory, and
  state clearly when documentation could not be found.
