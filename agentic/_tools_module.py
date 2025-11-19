"""
Consolidated Tools Module - All agent tools in one place
Includes: file reading, PR creation, repo analysis, code execution, logging
"""

import os
import json
import base64
import logging
import requests
from pathlib import Path

LOG = logging.getLogger("agentic.tools")


# ============ FILE READER ============
def read_file(filepath):
    """Read file content"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return {"status": "ok", "content": f.read()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ PR TOOL ============
def create_pr(repo, base_branch, head_branch, title, body, files=None, labels=None):
    """Create GitHub PR with file commits"""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GIT_TOKEN")
    
    if not token:
        LOG.warning("GITHUB_TOKEN not set; demo PR")
        return {"status": "ok", "pr_number": 1, "url": f"https://example.com/{repo}/pull/1", "head_branch": head_branch}

    repo_full = repo if "/" in repo else os.getenv("GITHUB_REPO", repo)
    if not repo_full or "/" not in repo_full:
        return {"status": "error", "reason": "invalid_repo"}

    owner, name = repo_full.split("/", 1)
    api_base = f"https://api.github.com/repos/{owner}/{name}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    # Get base branch SHA
    ref_url = f"{api_base}/git/ref/heads/{base_branch}"
    resp = requests.get(ref_url, headers=headers)
    if resp.status_code != 200:
        repo_meta = requests.get(api_base, headers=headers).json()
        base_branch = repo_meta.get("default_branch", "master")
        ref_url = f"{api_base}/git/ref/heads/{base_branch}"
        resp = requests.get(ref_url, headers=headers)
    
    if resp.status_code != 200:
        return {"status": "error", "reason": "base_branch_not_found"}
    
    base_sha = resp.json()["object"]["sha"]
    LOG.info(f"Using base branch: {base_branch}, SHA: {base_sha}")

    # Create branch
    branch_url = f"{api_base}/git/refs"
    branch_data = {"ref": f"refs/heads/{head_branch}", "sha": base_sha}
    resp = requests.post(branch_url, headers=headers, json=branch_data)
    
    if resp.status_code not in [201, 422]:  # 422 = branch exists
        LOG.error(f"Failed to create branch: {resp.text}")
        return {"status": "error", "reason": "branch_creation_failed"}
    
    LOG.info(f"Branch created or exists: {head_branch}")

    # Commit files
    if files:
        files_flat = []
        if isinstance(files[0], list):
            files_flat = files[0]
        else:
            files_flat = files
        
        LOG.info(f"Files to commit: {len(files_flat)} files")
        for file_entry in files_flat:
            path = file_entry.get("path", "")
            content = file_entry.get("patch", "")
            
            LOG.info(f"  - {path}: {len(content)} bytes")
            
            # Get file SHA if exists
            contents_url = f"{api_base}/contents/{path}"
            get_resp = requests.get(contents_url, headers=headers, params={"ref": head_branch})
            file_sha = None
            if get_resp.status_code == 200:
                file_sha = get_resp.json()["sha"]
            
            # Commit file
            commit_data = {
                "message": f"Update {path}",
                "content": base64.b64encode(content.encode()).decode(),
                "branch": head_branch
            }
            if file_sha:
                commit_data["sha"] = file_sha
            
            resp = requests.put(contents_url, headers=headers, json=commit_data)
            if resp.status_code not in [200, 201]:
                LOG.error(f"Failed to commit {path}: {resp.text}")
            else:
                LOG.info(f"Successfully committed: {path}")

    # Create PR
    pr_url = f"{api_base}/pulls"
    pr_data = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }
    
    resp = requests.post(pr_url, headers=headers, json=pr_data)
    if resp.status_code != 201:
        LOG.error(f"PR creation failed: {resp.text}")
        return {"status": "error", "reason": "pr_creation_failed"}
    
    pr_info = resp.json()
    return {
        "status": "ok",
        "pr_number": pr_info["number"],
        "url": pr_info["html_url"],
        "head_branch": head_branch
    }


# ============ REPO ANALYZER ============
def get_repo_info(repo_path="."):
    """Get basic repo info"""
    try:
        git_path = Path(repo_path) / ".git" / "HEAD"
        if git_path.exists():
            with open(git_path) as f:
                head = f.read().strip()
            return {"status": "ok", "git_head": head}
    except:
        pass
    return {"status": "ok", "git_head": "unknown"}


# ============ LOGGER ============
def log_event(event_type, message, level="INFO"):
    """Log an event"""
    log_func = getattr(LOG, level.lower(), LOG.info)
    log_func(f"[{event_type}] {message}")
    return {"status": "ok"}


# ============ CODE VALIDATOR ============
def validate_code(code):
    """Basic code validation"""
    try:
        compile(code, '<string>', 'exec')
        return {"status": "valid"}
    except SyntaxError as e:
        return {"status": "invalid", "error": str(e)}
