class PolicyEvaluator:
    def __init__(self, hitl_threshold=70):
        self.hitl_threshold = hitl_threshold

    def apply(self, detections, state):
        # For demo, convert detections to decisions directly
        decisions = []
        for d in detections:
            decisions.append({
                "summary": d.get("description", "Auto action"),
                "location": d.get("location"),
                "score": d.get("score", 50),
                "detection": d
            })
        return decisions

    def requires_hitl(self, plan):
        # require HITL if estimated_risk_score exceeds threshold
        try:
            return plan.get("estimated_risk_score", 0) > self.hitl_threshold
        except Exception:
            return True
