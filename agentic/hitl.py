class ApprovalsService:
    def __init__(self):
        pass

    def request(self, plan):
        # Demo: auto-approve low-risk plans and simulate manual approval for high risk
        if plan.get("estimated_risk_score", 0) > 70:
            return {"granted": False, "reason": "requires_manual_review"}
        return {"granted": True}

    # Backwards-compatible method name used by agentic.agent
    def request_approval(self, plan):
        return self.request(plan)
