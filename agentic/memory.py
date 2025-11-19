"""
Consolidated Memory Module - Episodic storage with learning capabilities
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class EpisodicStore:
    """Episodic memory with query methods for learning"""
    
    def __init__(self, store_path: str = "agentic/memory/episodic_store.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.store_path.exists():
            with open(self.store_path, 'r') as f:
                try:
                    self.runs = json.load(f)
                except json.JSONDecodeError:
                    self.runs = []
        else:
            self.runs = []
    
    def append(self, run_data: Dict[str, Any]) -> None:
        """Append a run to memory"""
        self.runs.append(run_data)
        self._persist()
    
    def _persist(self) -> None:
        """Save to disk"""
        with open(self.store_path, 'w') as f:
            json.dump(self.runs, f, indent=2, default=str)
    
    # Query Methods
    def get_all_runs(self) -> List[Dict[str, Any]]:
        """Get all runs"""
        return self.runs
    
    def get_runs_by_issue(self, issue_substring: str) -> List[Dict[str, Any]]:
        """Find runs matching an issue type"""
        matching = []
        for run in self.runs:
            detection = run.get("detection", {})
            issue_desc = (detection.get("issue") or detection.get("description") or "").lower()
            if issue_substring.lower() in issue_desc:
                matching.append(run)
        return matching
    
    def get_successful_runs(self, issue_substring: str) -> List[Dict[str, Any]]:
        """Get only successful runs for an issue"""
        all_runs = self.get_runs_by_issue(issue_substring)
        return [r for r in all_runs if r.get("pr", {}).get("status") in ["success", "ok"]]
    
    def get_latest_successful_fix(self, issue_substring: str) -> Optional[Dict[str, Any]]:
        """Get most recent successful fix"""
        successful = self.get_successful_runs(issue_substring)
        return successful[-1] if successful else None
    
    def get_successful_fixes_for_learning(self, issue_substring: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get examples for few-shot learning"""
        successful = self.get_successful_runs(issue_substring)
        return list(reversed(successful))[:limit]
    
    def get_issue_statistics(self, issue_substring: str) -> Dict[str, Any]:
        """Get statistics for an issue type"""
        all_runs = self.get_runs_by_issue(issue_substring)
        successful_runs = self.get_successful_runs(issue_substring)
        
        stats = {
            "total_occurrences": len(all_runs),
            "successful_fixes": len(successful_runs),
            "success_rate": len(successful_runs) / len(all_runs) if all_runs else 0,
            "most_recent_fix": None
        }
        
        if successful_runs:
            latest = successful_runs[-1]
            if latest.get("plan") and latest["plan"].get("files"):
                files = latest["plan"]["files"]
                if files and isinstance(files, list):
                    file_entry = files[0]
                    if isinstance(file_entry, list):
                        file_entry = file_entry[0] if file_entry else {}
                    if isinstance(file_entry, dict):
                        stats["most_recent_fix"] = {
                            "file_path": file_entry.get("path"),
                            "code_snippet": file_entry.get("patch", "")[:500]
                        }
        
        return stats
    
    def get_run_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get specific run by ID"""
        for run in self.runs:
            if run.get("run_id") == run_id:
                return run
        return None
    
    def get_recent_runs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get N most recent runs"""
        return list(reversed(self.runs))[:limit]
