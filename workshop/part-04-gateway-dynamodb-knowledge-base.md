# Part 4: Connect to Real Data — DynamoDB & Knowledge Base

**Estimated time:** ~35 minutes

In this part, you'll connect your agent to real data sources through an AgentCore
Gateway. You'll explore pre-created DynamoDB tables containing order, customer, and
product data, create Lambda functions to query those tables and retrieve return
policies from a Knowledge Base, and wire everything together through a gateway.

> **Pre-created resources:** The workshop CloudFormation template has already
> created the following for you:
> - **DynamoDB tables** — three tables (`workshop-customers`, `workshop-orders`,
>   `workshop-products`) pre-populated with seed data from CSV files
> - **Bedrock Knowledge Base** — containing Amazon return policy documents for the
>   US, UK, and India
> - **SSM Parameters** — storing the Knowledge Base ID for use in Lambda functions
>
> You do not need to create or load any data manually.

**Architecture:** Full gateway with DynamoDB, Knowledge Base, Identity, and
Observability.

---

## Step 1: Explore DynamoDB Data

Before connecting DynamoDB to your agent, explore the seed data to understand what's
available. The tables contain customer, order, and product records that your agent
will query through the gateway.

Open Kiro and query the orders table for a specific customer:

🤖 **Kiro Vibe Prompt:**

```
Query the DynamoDB `workshop-orders` table to find all orders for customer C-01 using CLI.
Use the AWS region us-west-2.
```

> The terminal may show long output that requires paging. Press `f` to skip to the
> next page, or `q` to exit the pager.

**Expected output:**

Kiro should query the DynamoDB tables and return results similar to:

```json
{
    "Items": [
        {
            "customer_id": { "S": "C-01" },
            "purchased_date": { "S": "2024-01-15" },
            "status": { "S": "DELIVERED" },
            "product_id": { "S": "P-001" }
        }
    ]
}
```

This shows customer Rajesh Kumar (C-01) has orders across different statuses
including iPhone 15 Pro (P-001), Kindle Paperwhite (P-002), PlayStation 5 (P-006),
Echo Dot (P-007), and ThinkPad X1 Carbon (P-005).

> The seed data includes three customers: C-01 (Rajesh Kumar, India), C-02 (Emily
> Johnson, UK), and C-03 (Michael Smith, US). Products range from P-001 through P-007
> covering phones, e-books, tablets, laptops, gaming consoles, and smart speakers.

## Step 2: Explore the Knowledge Base

The workshop environment includes a pre-created Bedrock Knowledge Base containing
Amazon return policy documents for the US, UK, and India. Query it to see what policy
information is available before connecting it to the agent.

🤖 **Kiro Vibe Prompt:**

```
Query the Bedrock Knowledge Base to retrieve the return policy for electronics in the US.
Use AWS CLI for each step.
The Knowledge Base ID is stored in SSM parameter `/app/workshop/kb/knowledge-base-id`.
Use the AWS region us-west-2.
Show me the relevant policy excerpts.
```

**Expected output:**

Kiro should retrieve policy excerpts from the Knowledge Base, including return
windows, refund conditions, and product-specific rules for electronics.

> The Knowledge Base contains three PDF documents covering Amazon return policies
> for the US, UK, and India. Each document includes product category-specific
> rules, return windows, and refund conditions. Your agent will use this information
> to answer customer policy questions through the gateway.

## Step 3: Create Lambda Functions

Now create two Lambda functions that your agent will access through the gateway:

- **Data Lookup Lambda** — queries DynamoDB tables to retrieve order, customer, and
  product information
- **Policy Retrieval Lambda** — queries the Bedrock Knowledge Base to retrieve return
  policy information

Both Lambda functions read their configuration from SSM Parameter Store, so they
automatically connect to the pre-created resources.

🤖 **Kiro Vibe Prompt:**

```
First, describe the DynamoDB tables (workshop-customers, workshop-orders, workshop-products) to understand their key structure and attributes.

Then create two Lambda functions in a `/lambda_functions/` directory inside my root project:

1. `/lambda_functions/data_lookup/handler.py` -- A Lambda function that handles order, customer, and product lookups from DynamoDB.
   It should support three tools: `order_lookup`, `user_lookup`, and `product_lookup`.
   Use the `bedrockAgentCoreToolName` from the Lambda context to determine which tool was called.
   Use boto3 in region us-west-2.

2. `/lambda_functions/policy_retrieval/handler.py` -- A Lambda function that retrieves return policies from the Bedrock Knowledge Base.
   Read the Knowledge Base ID from SSM parameter `/app/workshop/kb/knowledge-base-id`.
   Use the Bedrock Agent Runtime `retrieve` API.
   Use region us-west-2.

For each Lambda, create a `requirements.txt` with dependencies.

Follow the Lambda function input/output format for AgentCore Gateway targets as described in:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html
```

**Expected output:**

Kiro should create the following file structure:

```
lambda_functions/
|-- data_lookup/
|   |-- handler.py
|   +-- requirements.txt
+-- policy_retrieval/
    |-- handler.py
    +-- requirements.txt
```

The `data_lookup/handler.py` should route between `order_lookup`, `user_lookup`, and
`product_lookup` based on the tool name from the context, querying DynamoDB tables
(`workshop-customers`, `workshop-orders`, `workshop-products`). The
`policy_retrieval/handler.py` should read the Knowledge Base ID from SSM parameter
`/app/workshop/kb/knowledge-base-id`.

## Step 4: Deploy Lambda Functions

Now deploy both Lambda functions to AWS.

🤖 **Kiro Vibe Prompt:**

```
Deploy both Lambda functions to AWS in region us-west-2.
Zip each function's code, create the Lambda functions using boto3, Use the pre-created Lambda execution role ARN from SSM parameter `/app/workshop/lambda/execution-role-arn`.
Print the Lambda ARNs after deployment.
```

## Step 5: Test the Lambda Functions

Before wiring the Lambdas into the gateway, verify they work correctly by invoking
them directly.

🤖 **Kiro Vibe Prompt:**

```
Test the two Lambda functions we just deployed:
1. Invoke the data lookup Lambda with customer_id "C-01" to test order lookup and show the response
2. Invoke the policy retrieval Lambda with query "What is the return policy for electronics in the US?" and show the response
Use AWS CLI in region us-west-2.
```

The order lookup should return Rajesh Kumar's customer details and orders with
product information. The policy retrieval should return relevant excerpts from the
US return policy document.

> If either Lambda returns an error, Kiro will capture the response and work to
> identify the cause. You can guide Kiro with your ideas and work together to
> resolve the issue.

> **Checkpoint** — Nice work! You've explored the data, built two Lambda functions,
> and verified they work. That's the data layer done. Now let's wire it all together
> — you'll create tool specs, set up Cognito authentication, and connect everything
> through the AgentCore Gateway.

## Step 6: Create Tool Specifications

The AgentCore Gateway requires tool specification files that describe each Lambda
function's interface. These specs define how the gateway routes requests from your
agent to the correct Lambda function.

🤖 **Kiro Vibe Prompt:**

```
Create tool specification JSON files for the AgentCore Gateway in `AgentCoreProject/tool_specs/` directory.
File names: data_lookup.json and policy_retrieval.json
Use the Lambda functions we created as the targets.
Make sure you are using the AgentCore Gateway Lambda tool spec format.
Look up the latest AWS documentation for the correct format.
Make each JSON as an array.
Do NOT include outputSchema — only name, description, and inputSchema are needed.
```

**Expected output:**

Kiro should create two JSON files:

```
tool_specs/
|-- data_lookup.json
+-- policy_retrieval.json
```

The `data_lookup.json` should contain an array with three tool definitions
(`order_lookup`, `user_lookup`, and `product_lookup`). The `policy_retrieval.json`
should contain an array with one tool definition (`policy_retrieval`). Each file
defines the tool names, descriptions, and input schemas that the gateway uses to
expose the Lambda functions as MCP tools to your agent.

## Step 7: Create Cognito User Pool for Gateway Authentication

The AgentCore Gateway requires authentication to secure access. Create a Cognito
User Pool with a machine-to-machine (M2M) client that the agent will use to
authenticate with the gateway.

🤖 **Kiro Vibe Prompt:**

```
Create a Cognito User Pool for the workshop gateway authentication:
- User Pool name: workshop-gateway-auth
- Create a domain prefix for OAuth endpoints
- Create a resource server with a custom scope for gateway invocation
- Create an app client configured for machine-to-machine (client_credentials) flow
- Save all credentials (user_pool_id, domain, client_id, client_secret, token_endpoint, discovery_url) to a config file - cognito_config.json
- Use the IDP-based discovery URL format: https://cognito-idp.us-west-2.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
- Region: us-west-2
```

> The Cognito User Pool provides OAuth2 authentication for the gateway. The M2M
> client uses the `client_credentials` grant type, which is designed for
> service-to-service communication — no user login required.

## Step 8: Add Gateway

Now use the AgentCore CLI to create a gateway that connects your agent to the Lambda
functions. The gateway acts as a secure bridge, receiving tool calls from your agent
in AgentCore Runtime and routing them to the appropriate Lambda function.

### Understanding Gateway Architecture

```
+------------------+   Custom JWT     +-------------------+     Invoke     +------------------+
|  AgentCore       | ----------------> |  AgentCore        | -------------> |  Lambda          |
|  Runtime         |   (Cognito)      |  Gateway          |                |  Functions       |
|  (Your Agent)    | <---------------- |  (MCP Tools)      | <------------- |                  |
+------------------+    Tool Results   +-------------------+   Response     +------------------+
                                              |                                    |
                                              |                                    |-- data_lookup
                                              |                                    |   +-- queries DynamoDB
                                              |                                    |
                                              |                                    +-- policy_retrieval
                                              |                                        +-- queries Knowledge Base
```

The gateway uses Custom JWT authentication backed by the Cognito User Pool you just
created. When your agent needs to look up an order or retrieve a policy, it obtains a
JWT token from Cognito and makes an authenticated tool call through the gateway.

Firstly, open `cognito_config.json` created in the previous step for reference.

Add the gateway to your agent project:

💻 **Terminal Command:**

```bash
agentcore add
```

Then use the following selections interactively:

- Select **Gateway**
- Gateway name: `workshop-gateway`
- Choose **Custom JWT** for authorizer type
- Discovery URL: paste the `discovery_url` from `cognito_config.json` (format:
  `https://cognito-idp.us-west-2.amazonaws.com/{user_pool_id}/.well-known/openid-configuration`)
- Select **Allowed Clients** only in
- Client ID: paste the `client_id` from `cognito_config.json`
- When prompted to Configure Custom JWT Authorizer (optional OAuth credentials for
  bearer token fetching), press **Enter** to skip — leave the OAuth Client ID blank
- Select **Semantic Search only** for advanced config
- **Confirm**

Next, configure the gateway targets by running `agentcore add` again. You will need
the Lambda ARNs from the previous step.

First, ask Kiro:

```
Show me the lambda ARNs.
```

Kiro will show you the ARNs of the two Lambda functions created earlier. Keep them
in the Kiro IDE screen. Now, add AgentCore Gateway targets by running `agentcore add`
command again.

💻 **Terminal Command:**

```bash
agentcore add
```

Then use the following selections interactively:

- Select **Gateway Target**
- Name: `data-lookup`
- Target type: **Lambda function**
- Paste the Lambda ARN of the Data Lookup function
- Tool schema file path: `./tool_specs/data_lookup.json`
- Select the gateway created above
- **Confirm**

Repeat the same steps for the policy retrieval Lambda.

> When adding the second target, make sure to use the policy retrieval Lambda ARN
> and set the Tool schema file path to `./tool_specs/policy_retrieval.json` (not
> `data_lookup.json`). A suggested name is `policy-retrieval`.

Finally, deploy the updated project with AgentCore Gateway:

💻 **Terminal Command:**

```bash
agentcore deploy
```

## Step 9: Test the Gateway MCP Endpoint

Before integrating the gateway into your agent code, verify the MCP endpoint is
working correctly by calling it directly.

🤖 **Kiro Vibe Prompt:**

```
Test the AgentCore Gateway MCP endpoint.
Get the gateway URL from the agentcore configuration.
Use the Cognito credentials from cognito_config.json to obtain a JWT token, then call the gateway's /mcp endpoint to list available tools.
Show me the tools that the gateway exposes.
```

You should see the gateway return the tool definitions for `order_lookup`,
`user_lookup`, `product_lookup`, and `policy_retrieval`. This confirms the gateway,
Lambda targets, and authentication are all working correctly.

## Step 10: Integrate Gateway Tools into the Agent

Now that the gateway and targets are configured, update your agent code to replace
the dummy tools from Part 2 with the real gateway-connected tools.

🤖 **Kiro Vibe Prompt:**

```
Update app/CustomerAssistantAgent/main.py to replace the dummy order_lookup, user_lookup, product_lookup, and policy_retrieval tools with real gateway tools.

The agent should connect to the AgentCore Gateway as an MCP client to discover and call the data_lookup and policy_retrieval Lambda functions.
The data_lookup Lambda handles order_lookup, user_lookup, and product_lookup calls.
Remove the dummy mock data functions.

The agent must handle OAuth token management for gateway authentication:
- Read GATEWAY_CLIENT_ID, GATEWAY_CLIENT_SECRET, GATEWAY_TOKEN_ENDPOINT, and GATEWAY_SCOPE from environment variables
- Obtain a JWT access token from Cognito using the client_credentials grant type
- Pass the token as an Authorization Bearer header when making MCP calls to the gateway URL
- Cache and auto-refresh the token before expiry

Keep the get_current_time tool and the memory integration intact.
Update agentcore.json and .env.local with the gateway endpoint URL and the Cognito credentials (client_id, client_secret, token_endpoint, scope).
Look up the latest AgentCore Gateway integration documentation for the correct MCP client pattern.
Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-agent-integration.html for the Strands MCP client integration.
```

> Review the updated code to ensure the dummy tools are removed and the gateway
> tools are properly connected. The agent should now call the Lambda functions
> through the gateway instead of using hardcoded mock data.

## Step 11: Test Gateway Integration

With the gateway connected, your agent can now access real order data and return
policies. Test both capabilities.

### Test Locally

Ask Kiro to run the agent locally and test the gateway integration:

🤖 **Kiro Vibe Prompt:**

```
Test the gateway integration locally by running these commands one by one and showing me the results:
1. `agentcore dev --runtime CustomerAssistantAgent "Look up orders for customer C-01"`
2. `agentcore dev --runtime CustomerAssistantAgent "What is the return policy for electronics in India?"`
3. `agentcore dev --runtime CustomerAssistantAgent "Can I return the PlayStation 5 I ordered? What's the policy for gaming consoles in India?"`
```

The agent should:

- Return Rajesh Kumar's order details from DynamoDB through the gateway
- Return India electronics return policy from the Knowledge Base
- Combine order lookup, policy retrieval, and memory context for a personalized
  response

### Test Deployed Agent

Redeploy your agent with the gateway integration:

💻 **Terminal Command:**

```bash
agentcore deploy
```

> Redeployment with gateway changes takes 2-3 minutes as the CLI updates both the
> runtime agent and the gateway configuration.

Test the deployed agent:

💻 **Terminal Command:**

```bash
agentcore invoke
```

💬 **Agent Test Prompt:**

```
Look up orders for customer C-02 and tell me about the UK return policy
```

The agent should return Emily Johnson's orders from DynamoDB and the UK return
policy from the Knowledge Base.

Press <kbd>Ctrl+C</kbd> to exit the session.

## What You Just Built

You've connected your agent to real data sources through an AgentCore Gateway:

- Explored DynamoDB seed data and Knowledge Base policies using Kiro
- Created and deployed Lambda functions for order lookup and policy retrieval
- Created tool specification files for the gateway
- Added a gateway with Custom JWT authentication (Cognito) using `agentcore add`
- Tested order lookups and policy retrieval both locally and on the deployed agent
- Verified the agent combines memory, tools, and gateway capabilities

Your agent can now look up real orders, retrieve return policies, and remember
customer preferences. In the next part, you'll build a Streamlit web UI so users can
interact with the agent through a browser.

---

⬅️ [Back: Part 3 — Add Persistent Memory](part-03-persistent-memory.md) | [Overview](README.md) | ➡️ [Next: Part 5 — Build a Web Chat UI](part-05-streamlit-ui-cognito.md)
