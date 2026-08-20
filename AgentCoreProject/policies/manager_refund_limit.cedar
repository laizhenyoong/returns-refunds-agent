// Managers can process refunds up to $5000
permit(
  principal,
  action == AgentCore::Action::"refund-agent___process_refund",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-west-2:442829247723:gateway/agentcoreproject-workshop-gateway-dbnfulnhn1"
) when {
  principal.hasTag("scope") &&
  principal.getTag("scope") like "*managers*" &&
  context.input.amount < 5000
};
