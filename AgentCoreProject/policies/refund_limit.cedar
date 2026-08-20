// Allow refunds under $500 for any authenticated caller
permit(
  principal,
  action == AgentCore::Action::"refund-agent___process_refund",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-west-2:442829247723:gateway/agentcoreproject-workshop-gateway-dbnfulnhn1"
) when {
  context.input.amount < 500
};
