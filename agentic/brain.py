"""
Consolidated Brain Module - Planner & Reasoner combined
Handles planning and reasoning for code improvements
"""

import uuid
import json
import logging

LOG = logging.getLogger("agentic.brain")


class Planner:
    """Generates repair plans using LLM with memory-based learning"""
    
    def __init__(self, llm_client=None, episodic_store=None):
        self.llm = llm_client
        self.memory = episodic_store
    
    def generate(self, decision, context):
        """Generate a repair plan with memory-based few-shot learning"""
        plan_id = str(uuid.uuid4())
        goal = decision.get("summary", decision.get("description", "Auto fix"))
        location = decision.get("location", "")
        
        # Query memory for learned patterns
        memory_context = ""
        if self.memory:
            try:
                issue_substring = goal.split(":")[0][:50]
                examples = self.memory.get_successful_fixes_for_learning(issue_substring, limit=2)
                if examples:
                    memory_context = "\n\nPAST SUCCESSFUL FIXES:\n"
                    for i, ex in enumerate(examples, 1):
                        memory_context += f"\nExample {i}:\n"
                        if ex.get("plan") and ex["plan"].get("files"):
                            files = ex["plan"]["files"]
                            for f in (files if files else []):
                                if isinstance(f, list):
                                    f = f[0] if f else {}
                                if isinstance(f, dict):
                                    code = f.get("patch", "")[:300]
                                    if code:
                                        memory_context += f"```python\n{code}\n```\n"
                        memory_context += f"(Success rate: {self._get_success_rate(issue_substring):.0%})\n"
            except Exception as e:
                LOG.warning(f"Memory query failed: {e}")
        
        # Generate plan with LLM or fallback
        if self.llm:
            try:
                prompt = f"""You are an expert code fixer. Generate a repair plan.

Issue: {goal}
Location: {location}
{memory_context}

Return JSON with this structure:
{{
  "steps": [
    {{"step_id": "s1", "type": "code_change", "description": "fix", "refactored_code": "actual Python code"}}
  ],
  "estimated_time_minutes": 15,
  "risks": [{{"id": "r1", "desc": "risk", "score": 20}}],
  "estimated_risk_score": 25
}}

CRITICAL: Include actual working Python code in 'refactored_code' with error handling and type hints.
Return ONLY valid JSON, no markdown."""
                
                response = self.llm.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                plan_text = response.choices[0].message.content
                plan_json = json.loads(plan_text)
                
                files = []
                for step in plan_json.get("steps", []):
                    if step.get("type") == "code_change" and step.get("refactored_code"):
                        file_path = location.split(":")[0] if location else "refactored_code.py"
                        files.append({"path": file_path, "patch": step.get("refactored_code", "")})
                
                plan = {
                    "plan_id": plan_id,
                    "goal": goal,
                    "estimated_time_minutes": plan_json.get("estimated_time_minutes", 20),
                    "steps": plan_json.get("steps", []),
                    "risks": plan_json.get("risks", []),
                    "estimated_risk_score": plan_json.get("estimated_risk_score", 30),
                    "policy_gate": "HITL_if_risk>70",
                    "files": [files] if files else [],
                    "memory_context": bool(memory_context)
                }
                
                step_descs = [s.get("description", "") for s in plan.get("steps", [])]
                explanation = f"Planned changes for: {goal}. Steps: " + "; ".join([d for d in step_descs if d])
                if memory_context:
                    explanation += " [Using learned patterns]"
                plan["explanation"] = explanation
                return plan
                
            except json.JSONDecodeError as je:
                LOG.error(f"JSON decode error: {je}")
            except Exception as e:
                LOG.error(f"LLM error: {e}")
        
        # Fallback: demo logic
        refactored_code = """'''Improved module with error handling.'''

class Serializer:
    def serialize(self, data):
        if data is None:
            return None
        try:
            return {"status": "ok", "data": data}
        except Exception as e:
            raise ValueError(f"Serialization failed: {e}")
"""
        
        files = [{"path": location.split(":")[0] if location else "improved.py", "patch": refactored_code}]
        return {
            "plan_id": plan_id,
            "goal": goal,
            "estimated_time_minutes": 20,
            "steps": [{"step_id": "s1", "type": "code_change", "description": "Apply improvements", "refactored_code": refactored_code}],
            "risks": [{"id": "r1", "desc": "compatibility risk", "score": 30}],
            "estimated_risk_score": 30,
            "policy_gate": "HITL_if_risk>70",
            "files": [files],
            "memory_context": bool(memory_context),
            "explanation": f"Improve: {goal}"
        }
    
    def _get_success_rate(self, issue_substring: str) -> float:
        if not self.memory:
            return 0
        try:
            stats = self.memory.get_issue_statistics(issue_substring)
            return stats.get("success_rate", 0)
        except:
            return 0


class Reasoner:
    """Analyzes code state and detects issues"""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    def detect_issues(self, state):
        """Detect issues in code using LLM or heuristics"""
        files_snapshot = state.get("files_snapshot", {})
        
        if self.llm:
            try:
                content = files_snapshot.get("content", "")
                prompt = f"""Analyze this code and detect ONE issue to fix:

{content[:500]}

Return JSON: {{"issue_id": "ISSUE-1", "score": 85, "classification": "bug", "location": "file.py", "description": "Brief issue description"}}

Only valid JSON, no markdown."""
                
                response = self.llm.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500
                )
                result = json.loads(response.choices[0].message.content)
                return result
            except Exception as e:
                LOG.warning(f"LLM reasoning failed: {e}")
        
        # Fallback: demo detection
        import random
        issues = [
            {"issue_id": f"ISSUE-DEMO-{random.randint(1,100)}", "score": 85, "classification": "bug",
             "location": "./sample_repo/services/order/serializer.py", 
             "description": "Demo detection: investigate serializer"},
            {"issue_id": "ISSUE-NULL-POINTER", "score": 75, "classification": "bug",
             "location": "./sample_repo/services/order/serializer.py",
             "description": "Detected possible null pointer"}
        ]
        return random.choice(issues)
