# Part 5: Build a Web Chat UI with Streamlit and Cognito

**Estimated time:** ~25 minutes

In this part, you'll build a web-based chat interface for your agent using
Streamlit. The Cognito User Pool created in Part 4 will handle user authentication.
You'll create a Streamlit application that connects to your deployed agent endpoint,
providing a browser-based UI where users can log in, chat with the agent, and see
memory, gateway, and Knowledge Base capabilities all working together.

> **Prerequisites:** You must have completed Part 4 with a fully deployed agent that
> has memory, gateway (DynamoDB + Knowledge Base) capabilities, and a Cognito User
> Pool. Make sure you're in your agent project directory
> (`~/ReturnsRefundsAgentProject/AgentCoreProject`).

---

## Step 1: Create a Cognito User for the UI

The Cognito User Pool was already created in Part 4 for gateway authentication. Now
create a test user that can log in through the Streamlit UI.

🤖 **Kiro Vibe Prompt:**

```
Using the existing Cognito User Pool configuration, create a test user for the Streamlit UI:
- Find the Cognito User Pool ID from the project's configuration files
- Create a user with email "administrator@example.com" and a temporary password "Workshop1!"
- Enable the user and set email as verified
- Use region us-west-2
```

> The test user is created with a temporary password. When you first log in through
> the Streamlit UI, Cognito will prompt you to set a new password.

## Step 2: Create the Streamlit Application

Now you'll create the Streamlit chat application that authenticates users via
Cognito and connects to your deployed agent endpoint. The app provides a chat
interface where users can interact with the agent through the browser.

Open Kiro and use the following prompt to create the Streamlit application:

🤖 **Kiro Vibe Prompt:**

```
Create a Streamlit chat application in a file called `streamlit_app.py` in /streamlit-ui/ folder under root.
The app should:

1. **Authentication with Cognito:**
   - Read the Cognito User Pool ID and App Client ID from the existing Cognito configuration files in the project
   - Show a login form with email and password fields when the user is not authenticated
     (For convinience during the workshop, use the Cognito user name and password as the default values)
   - Handle the Cognito USER_PASSWORD_AUTH flow using boto3 cognito-idp client
   - Handle the NEW_PASSWORD_REQUIRED challenge for first-time login (show a "Set New Password" form)
   - Store the authentication tokens in Streamlit session state
   - Show a logout button in the sidebar when authenticated

2. **Chat Interface:**
   - Display a chat history using `st.chat_message` components
   - Provide a chat input box at the bottom for user messages
   - When the user sends a message, invoke the deployed agent using the AgentCore Runtime API
   - Read the agent endpoint URL from the agentcore configuration
   - Display the agent's response in the chat
   - Maintain chat history in Streamlit session state

3. **AgentCore Runtime Integration:**
   - Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html
   - Use AgentCore Runtime ARN from the previous steps.
   - Use the user name (part before @) as actor_id.
   - Pass a consistent session_id per user session so the agent's memory works across messages
   - Include proper error handling for connection failures and timeouts

4. **UI Layout:**
   - Page title: "Returns & Refunds Assistant"
   - Sidebar showing: user email, session ID, and a logout button
   - Render streaming response properly. Tries to parse each chunk as JSON first. If successful, yields the parsed value (without the extra quotes) If not JSON, yields the chunk as-is
   - Welcome message when chat starts: "Hello! I'm your Returns & Refunds Assistant. I can help you look up orders, check return eligibility, calculate refunds and answer policy questions. How can I help you today?"

Use region us-west-2 for all AWS service calls.
```

**Expected output:**

Kiro should create a `streamlit_app.py` file with the following structure:

```python
import streamlit as st
import boto3
import os

# Cognito configuration from existing Part 4 config
# ... authentication functions ...
# ... chat interface ...
# ... agent invocation ...
```

> Review the generated code to verify it reads the Cognito configuration from the
> existing project config files and the agent endpoint from the agentcore
> configuration.

## Step 3: Install Dependencies

Install the Python packages required by the Streamlit application:

💻 **Terminal Command:**

```bash
pip install streamlit boto3
```

**Expected output:**

```
Successfully installed streamlit boto3 python-dotenv ...
```

## Step 4: Run and Test

Start the Streamlit application locally to test the full end-to-end workflow:

💻 **Terminal Command:**

```bash
cd streamlit-ui
streamlit run streamlit_app.py --server.port 8501
```

**Expected output:**

```
You can now view your Streamlit app in your browser.

Local URL: http://localhost:8501
Network URL: http://<ec2-private-ip>:8501
```

Open a browser and navigate to `http://localhost:8501` (or use the DCV remote
desktop browser on your EC2 instance).

### Test the Authentication Flow

- You should see a login form with email and password fields
- Enter the test credentials:
  - Email: `administrator@example.com`
  - Password: `Workshop1!`
- Since this is the first login, Cognito will prompt you to set a new password
- Enter a new password (minimum 8 characters) and submit
- You should now see the chat interface with the welcome message

### Test the Chat Interface

Once logged in, test the full agent workflow through the UI.

**Test 1 — Memory recall:**

💬 **Agent Test Prompt:**

```
What do you know about customer C-01?
```

The agent should recall Rajesh Kumar's preferences from the memory you seeded in
Part 3 — preferred email communication and favorite category electronics.

**Test 2 — Order lookup (Gateway + DynamoDB):**

💬 **Agent Test Prompt:**

```
What is product P-006
```

The agent should return Emily Johnson's orders from DynamoDB through the gateway,
showing product names, dates, and statuses.

**Test 3 — Policy retrieval (Gateway + Knowledge Base):**

💬 **Agent Test Prompt:**

```
What is the return policy for electronics in the UK?
```

The agent should retrieve the UK return policy from the Knowledge Base, including
return windows and refund details.

**Test 4 — Combined capabilities:**

💬 **Agent Test Prompt:**

```
Can customer C-03 return their iPad Air? What's the US return policy for tablets?
```

The agent should combine multiple capabilities:

- Look up customer C-03 (Michael Smith, US) from memory or gateway
- Retrieve the US return policy for tablets from the Knowledge Base
- Provide a comprehensive answer using all three data sources

**Expected UI behavior:**

- The chat interface displays messages in a conversational format with user
  messages on the right and agent responses on the left
- The sidebar shows the logged-in user's email and session ID
- Agent responses may take a few seconds as they invoke memory, gateway, and
  Knowledge Base services
- The logout button clears the session and returns to the login form

Press <kbd>Ctrl+C</kbd> in the terminal to stop the Streamlit server when you're done
testing.

## What You Just Built

You've created a complete web-based chat interface for your agent:

- ✅ Created a test user in the existing Cognito User Pool
- ✅ Built a Streamlit chat application with login and chat UI
- ✅ Connected the UI to your deployed agent endpoint
- ✅ Tested the full workflow: authentication → chat → memory + gateway + Knowledge
  Base responses

Your agent now has a production-style web UI with authentication. In the next part,
you'll explore the observability features to monitor and debug your agent in
production.

---

⬅️ [Back: Part 4 — Connect to Real Data](part-04-gateway-dynamodb-knowledge-base.md) | [Overview](README.md) | ➡️ [Next: Part 6 — Explore Observability](part-06-observability.md)
