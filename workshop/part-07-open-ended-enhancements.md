# Part 7: Make It Yours — Open-Ended Enhancements

**Estimated time:** Open-ended

You've built a fully functional Returns & Refunds agent with memory, gateway, and a
Streamlit UI. Now it's your turn to improve the solution using your own ideas. Use
Kiro to implement enhancements — describe what you want in natural language, and
Kiro will generate the code.

> This is your chance to have a real conversation with Kiro. Don't just copy
> prompts — talk to Kiro about your ideas, ask questions, iterate on the results,
> and guide it when things don't work as expected. Kiro works best when you
> collaborate with it like a pair programming partner.

---

## Suggested Ideas

Here are some ideas to get you started. Pick one or more, or come up with your own.

### Add Multiple Users to the App

The current Streamlit app has a single test user. Add more users so the agent can
handle multiple administrators with separate sessions.

🤖 **Kiro Prompt (example):**

```
Add two more Cognito users to the Streamlit app:
- admin2@example.com with password "Workshop2!"
- admin3@example.com with password "Workshop3!"
Each user should have their own memory session so the agent remembers interactions per user.
```

### Add More DynamoDB Query Tools

The current gateway has `order_lookup`, `user_lookup`, and `product_lookup`. Add
more tools to give the agent richer data access.

Ideas for new tools:

- `list_products` — list all products or filter by category
- `search_users_by_name` — find customers by name instead of ID
- `find_returned_products` — query orders with `RETURNED` status
- `get_orders_by_status` — filter orders by status (`DELIVERED`, `SHIPPED`,
  `RETURNED`, etc.)

🤖 **Kiro Prompt (example):**

```
Add a new Lambda tool called "find_returned_products" to the data_lookup Lambda.
It should query the workshop-orders table for all orders with status "RETURNED", enrich with product names from workshop-products, and return the results.
Update the tool spec, redeploy the Lambda, and update the gateway target.
```

### Add Order Management Features

The current agent is read-only. Add tools that can update order data — creating new
orders, cancelling orders, or processing refunds.

Ideas for new tools:

- `create_order` — add a new order for a customer
- `cancel_order` — update an order's status to `CANCELLED`
- `process_refund` — mark an order as `REFUNDED` and calculate the refund amount
- `update_order_status` — change an order's status (e.g., `SHIPPED` → `DELIVERED`)

🤖 **Kiro Prompt (example):**

```
Add a "process_refund" tool to the data_lookup Lambda.
It should accept an order_id, look up the order in workshop-orders, update its status to "REFUNDED", and return the refund confirmation with the product details.
Update the tool spec and redeploy.
```

> After adding new tools, remember to:
> 1. Update the Lambda code
> 2. Update the tool spec JSON (as an array)
> 3. Redeploy the Lambda
> 4. Update the gateway target if the tool spec changed
> 5. Redeploy with `agentcore deploy`
> 6. Test with `agentcore dev` or `agentcore invoke`

## Tips

- Use Kiro's Vibe chat to describe what you want in natural language
- Test locally with `agentcore dev` before deploying
- Check `agentcore logs` if something doesn't work as expected
- Ask Kiro to help debug errors — paste the error message and ask for a fix

When you're done experimenting, proceed to the AgentCore Harness preview, then the
cleanup section.

---

⬅️ [Back: Part 6 — Explore Observability](part-06-observability.md) | [Overview](README.md) | ➡️ [Next: Part 8 — Try the AgentCore Harness](part-08-agentcore-harness-preview.md)
