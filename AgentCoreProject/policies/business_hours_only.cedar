// Block refund processing outside business hours (9am-5pm UTC)
forbid(
  principal,
  action == AgentCore::Action::"refund-agent___process_refund",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-west-2:442829247723:gateway/agentcoreproject-workshop-gateway-dbnfulnhn1"
) when {
  context.system.now.toTime() < duration("9h") ||
  context.system.now.toTime() > duration("17h")
};
