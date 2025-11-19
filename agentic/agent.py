"""
Agent Main Module - Orchestrator, Scheduler, and CLI combined
Unified entry point for all agent functionality
"""

import os
import sys
import uuid
import time
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agentic.brain import Planner, Reasoner
from agentic.memory import EpisodicStore
from agentic._tools_module import read_file, create_pr, log_event
from agentic.policy.policy import PolicyEvaluator
from agentic.hitl import ApprovalsService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger("agentic.agent")

# Load environment
load_dotenv()


class Agent:
    """Main autonomous agent - unified orchestration + scheduler"""
    
    def __init__(self, groq_api_key=None):
        """Initialize agent with all components"""
        api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            LOG.warning("GROQ_API_KEY not provided")
            self.groq_client = None
        else:
            self.groq_client = Groq(api_key=api_key)
        
        # Initialize components
        self.episodic = EpisodicStore()
        self.planner = Planner(llm_client=self.groq_client, episodic_store=self.episodic)
        self.reasoner = Reasoner(llm_client=self.groq_client)
        self.policy = PolicyEvaluator()
        self.hitl = ApprovalsService()
        
        # Scheduler state
        self.scheduler = None
        self.run_count = 0
    
    def sense_sources(self):
        """Sense the environment"""
        try:
            content = read_file("./sample_repo/services/order/serializer.py")
        except:
            content = {"status": "error"}
        
        return {
            "git_head": "demo-commit",
            "files_snapshot": content,
            "ci_summary": {"status": "unknown"}
        }
    
    def run_once(self):
        """Execute single agent iteration"""
        run_id = str(uuid.uuid4())
        LOG.info(f"Starting run {run_id}")
        
        state = self.sense_sources()
        
        # Detect issues
        detection = self.reasoner.detect_issues(state)
        LOG.info(f"Detected: {detection.get('description')}")

        # Apply policy
        decision = self.policy.apply([detection], {})[0] if detection else None
        LOG.info(f"Policy decision: {decision}")

        # Generate plan
        plan = self.planner.generate(decision, state)
        LOG.info(f"Plan generated. Files: {len(plan.get('files', []))}")

        # Log plan explanation and steps for visibility
        plan_explanation = plan.get('explanation') or plan.get('goal') or 'No explanation provided.'
        LOG.info(f"Plan explanation: {plan_explanation}")
        steps = plan.get('steps', []) or []
        for idx, step in enumerate(steps, start=1):
            LOG.info(f"  Step {idx}: {step.get('description', '')}")
        
        # HITL check (optional)
        if plan.get("estimated_risk_score", 0) > 70:
            approved = self.hitl.request_approval(plan)
            if not approved:
                return {"run_id": run_id, "status": "rejected_by_hitl"}
        
        # Create PR
        # Use a single branch for agent commits (configurable via AGENT_BRANCH)
        head_branch = os.getenv("AGENT_BRANCH", "Agent")
        LOG.info(f"Using head branch: {head_branch}")

        pr_info = create_pr(
            repo=os.getenv("GITHUB_REPO", "shreyas7ss/testrepo"),
            base_branch=os.getenv("GITHUB_BASE_BRANCH", "main"),
            head_branch=head_branch,
            title=f"Auto-fix: {plan.get('goal', 'improvement')}",
            body=self._build_pr_body(run_id, plan),
            files=plan.get("files", [])
        )
        
        # Validation
        validation = {"passed": pr_info.get("status") == "ok"}

        # Build insights / results for this run (for easier visibility and UI use)
        insights = {
            "detection_summary": detection,
            "plan_explanation": plan_explanation,
            "steps": steps,
            "risk_score": plan.get('estimated_risk_score'),
            "pr": pr_info,
            "validation": validation
        }

        # Store in memory
        self.episodic.append({
            "run_id": run_id,
            "state": state,
            "detection": detection,
            "plan": plan,
            "pr": pr_info,
            "validation": validation,
            "insights": insights,
            "timestamp": datetime.now().isoformat()
        })

        # Log concise run summary / insights for users
        LOG.info(f"Run {run_id} completed. PR: {pr_info.get('url')} (#{pr_info.get('pr_number')})")
        LOG.info(f"Validation passed: {validation.get('passed')}")
        LOG.info(f"Risk score: {insights.get('risk_score')}")

        return {"run_id": run_id, "insights": insights}
    
    def _build_pr_body(self, run_id, plan):
        """Build detailed PR description"""
        body = f"""**Automated Code Improvement**

Run ID: `{run_id}`
Goal: {plan.get('goal', 'N/A')}

## Summary
{plan.get('explanation', 'N/A')}

## Steps
"""
        for step in plan.get("steps", []):
            body += f"- {step.get('description', '')}\n"
        
        body += f"\n## Risk Score: {plan.get('estimated_risk_score', 'N/A')}\n"
        body += f"\n## Full Plan\n```json\n{str(plan)}\n```"
        return body
    
    # ===== SCHEDULER =====
    def start_loop(self, interval_minutes=5, max_runs=None):
        """Start continuous looping"""
        if self.scheduler and self.scheduler.running:
            LOG.warning("Scheduler already running")
            return
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._scheduled_run,
            IntervalTrigger(minutes=interval_minutes),
            id='agent_run',
            replace_existing=True
        )
        
        self.scheduler.start()
        LOG.info(f"Scheduler started. Interval: {interval_minutes}m, Max: {max_runs or 'unlimited'}")
        
        # Run immediately
        LOG.info("Running agent immediately (first run)...")
        self._scheduled_run(max_runs=max_runs)
        
        # Keep running
        try:
            while self.scheduler.running and (max_runs is None or self.run_count < max_runs):
                time.sleep(1)
        except KeyboardInterrupt:
            LOG.info("Scheduler interrupted by user")
            self.stop_loop()
    
    def _scheduled_run(self, max_runs=None):
        """Execute run as scheduled task"""
        self.run_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        LOG.info(f"\n{'='*80}")
        LOG.info(f"[SCHEDULED RUN #{self.run_count}] {timestamp}")
        LOG.info(f"{'='*80}")
        
        try:
            result = self.run_once()
            pr = result.get("pr", {})
            LOG.info(f"[RUN #{self.run_count} SUCCESS]")
            LOG.info(f"  PR: {pr.get('pr_number')} - {pr.get('url')}")
        except Exception as e:
            LOG.error(f"[RUN #{self.run_count} FAILED] {e}", exc_info=True)
        
        # Stop if max reached
        if max_runs and self.run_count >= max_runs:
            LOG.info(f"Max runs ({max_runs}) reached. Stopping.")
            self.stop_loop()
    
    def stop_loop(self):
        """Stop scheduler gracefully"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            LOG.info(f"Scheduler stopped. Total runs: {self.run_count}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Autonomous AI Agent for Code Improvement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agentic.agent              # Single run
  python -m agentic.agent --loop       # Every 5 min
  python -m agentic.agent --loop --interval 10 --max-runs 20
        """
    )
    
    parser.add_argument('--loop', action='store_true', help='Enable continuous looping')
    parser.add_argument('--interval', type=int, default=5, help='Loop interval in minutes')
    parser.add_argument('--max-runs', type=int, default=None, help='Max runs (unlimited if not set)')
    
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment")
        sys.exit(1)
    
    agent = Agent()
    
    if args.loop:
        print(f"\n{'='*80}")
        print("CONTINUOUS LOOPING MODE ENABLED")
        print(f"{'='*80}")
        print(f"Interval: {args.interval} minute(s)")
        if args.max_runs:
            print(f"Max runs: {args.max_runs}")
        else:
            print("Max runs: Unlimited (press Ctrl+C to stop)")
        print(f"{'='*80}\n")
        
        agent.start_loop(interval_minutes=args.interval, max_runs=args.max_runs)
    else:
        print(f"\n{'='*80}")
        print("SINGLE RUN MODE")
        print(f"{'='*80}\n")

        result = agent.run_once()

        # Pretty-print results/insights for readability
        insights = result.get('insights', {})

        def _print_insights(run_id, data):
            print(f"Run ID: {run_id}\n")

            detection = data.get('detection_summary') or {}
            print("Detection:")
            print(f"  - Issue ID: {detection.get('issue_id', 'N/A')}")
            print(f"  - Description: {detection.get('description', 'N/A')}")
            print(f"  - Classification: {detection.get('classification', 'N/A')}")
            print(f"  - Score: {detection.get('score', 'N/A')}\n")

            print("Plan Explanation:")
            print(f"  {data.get('plan_explanation', 'N/A')}\n")

            steps = data.get('steps', [])
            if steps:
                print("Steps:")
                for i, s in enumerate(steps, start=1):
                    desc = s.get('description', '')
                    print(f"  {i}. {desc}")
                    code = s.get('refactored_code') or s.get('patch')
                    if code:
                        # show a short preview of the code block (first 10 lines)
                        preview = '\n'.join(code.splitlines()[:10])
                        print("    Code preview:")
                        for line in preview.splitlines():
                            print(f"      {line}")
                        if len(code.splitlines()) > 10:
                            print("      ... (truncated) ...")
                print("")
            else:
                print("No steps generated.\n")

            print(f"Risk score: {data.get('risk_score', 'N/A')}")

            pr = data.get('pr') or {}
            print("\nPull Request:")
            print(f"  - URL: {pr.get('url', 'N/A')}")
            print(f"  - PR Number: {pr.get('pr_number', 'N/A')}")
            print(f"\nValidation passed: {data.get('validation', {}).get('passed', False)}")

        _print_insights(result.get('run_id'), insights)


if __name__ == "__main__":
    main()
