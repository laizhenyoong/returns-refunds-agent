// Allow any authenticated caller to invoke read-only tools
permit(
  principal,
  action in [
    AgentCore::Action::"data-lookup___order_lookup",
    AgentCore::Action::"data-lookup___user_lookup",
    AgentCore::Action::"data-lookup___product_lookup",
    AgentCore::Action::"policy-retrieval___policy_retrieval"
  ],
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-west-2:442829247723:gateway/agentcoreproject-workshop-gateway-dbnfulnhn1"
);
