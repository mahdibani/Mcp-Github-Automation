import os
import subprocess
import base64
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

mcp = FastMCP("terminal")

DEFAULT_WORKSPACE = r"C:\Users\bani_\OneDrive\Desktop\AI_ML\mcp\workspace"
os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)

# ============================================
# 🧠 Terminal Command Tool
# ============================================
@mcp.tool()
async def run_command(command: str) -> str:
    """
    Run a terminal command inside the workspace directory.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=DEFAULT_WORKSPACE,
            capture_output=True,
            text=True
        )
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)

# ============================================
# 🔐 GitHub Tool Setup
# ============================================
def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

# ============================================
# 🔧 GitHub Tool Functions (No token param)
# ============================================

@mcp.tool()
async def github_create_repository(name: str, private: bool = True) -> dict:
    """
    Create a new GitHub repository.
    """
    url = "https://api.github.com/user/repos"
    headers = get_headers()
    payload = {
        "name": name,
        "private": private,
#"description": description
    }
    res = requests.post(url, json=payload, headers=headers)
    return res.json()

@mcp.tool()
async def github_add_collaborator(owner: str, repo: str, username: str, permission: str = "push") -> dict:
    """
    Add a collaborator to a GitHub repository.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{username}"
    headers = get_headers()
    payload = {"permission": permission}
    res = requests.put(url, json=payload, headers=headers)
    if res.status_code == 204:
        return {"message": "Collaborator added successfully"}
    return res.json()

@mcp.tool()
async def github_push_file(owner: str, repo: str, project_path: str, commit_message: str, branch: str = "main") -> dict:
    """
    Push files/directories from your project to GitHub while preserving structure.
    Paths are relative to your main mcp folder (e.g. 'servers/terminal_server.py' or 'clients/mcp-client')
    """
    # Get absolute paths
    PROJECT_ROOT = os.path.dirname(DEFAULT_WORKSPACE)
    abs_local_path = os.path.join(PROJECT_ROOT, project_path)
    
    if not os.path.exists(abs_local_path):
        return {"error": f"Path not found: {abs_local_path}"}

    results = []
    
    if os.path.isfile(abs_local_path):
        # Handle single file
        result = await _push_single_file(
            owner, repo, abs_local_path, project_path, commit_message, branch
        )
        results.append(result)
    else:
        # Recursively handle directories
        for root, _, files in os.walk(abs_local_path):
            for file in files:
                file_abs_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_abs_path, PROJECT_ROOT)
                
                result = await _push_single_file(
                    owner, repo, file_abs_path, relative_path, commit_message, branch
                )
                results.append(result)

    return {
        "status": "complete",
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "error_count": sum(1 for r in results if r["status"] == "error"),
        "details": results
    }

async def _push_single_file(owner: str, repo: str, local_path: str, github_path: str, 
                           commit_message: str, branch: str) -> dict:
    """
    Internal helper to push individual files
    """
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        headers = get_headers()
        github_path = github_path.replace("\\", "/")  # GitHub uses Unix-style paths
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{github_path}"

        # Get existing file SHA if present
        get_res = requests.get(url, headers=headers)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        # Prepare payload
        payload = {
            "message": commit_message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch
        }
        if sha:
            payload["sha"] = sha

        # Push file
        put_res = requests.put(url, headers=headers, json=payload)
        put_res.raise_for_status()
        
        return {
            "status": "success",
            "path": github_path,
            "html_url": put_res.json()["content"]["html_url"]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "path": github_path,
            "error": str(e),
            "details": put_res.json() if 'put_res' in locals() else None
        }
@mcp.tool()
async def github_get_repository(owner: str, repo: str) -> dict:
    """
    Get details of a GitHub repository.
    """
    headers = get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}"
    return requests.get(url, headers=headers).json()

@mcp.tool()
async def github_get_pull_requests(owner: str, repo: str) -> list:
    """
    Get open pull requests for a repository.
    """
    headers = get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    return requests.get(url, headers=headers).json()

@mcp.tool()
async def github_delete_repository(owner: str, repo: str) -> dict:
    """
    Delete a GitHub repository. 
    Requires admin permissions on the repository.
    
    Args:
        owner: The owner of the repository (username or organization)
        repo: The name of the repository to delete
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = get_headers()
    
    try:
        # First verify repository exists
        check_res = requests.get(url, headers=headers)
        check_res.raise_for_status()
        
        # Delete repository
        delete_res = requests.delete(url, headers=headers)
        
        if delete_res.status_code == 204:
            return {
                "status": "success",
                "message": f"Repository {owner}/{repo} deleted successfully"
            }
            
        return {
            "error": f"Failed to delete repository (HTTP {delete_res.status_code})",
            "details": delete_res.json()
        }
        
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP Error {e.response.status_code}",
            "message": e.response.json().get("message"),
            "documentation_url": e.response.json().get("documentation_url")
        }
    except Exception as e:
        return {
            "error": "Unexpected error",
            "details": str(e)
        }

@mcp.tool()
async def github_merge_pull_request(owner: str, repo: str, pr_number: int) -> dict:
    """
    Merge a pull request.
    """
    headers = get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge"
    return requests.put(url, headers=headers).json()

# ============================================
# 🚀 Run MCP Server
# ============================================
if __name__ == "__main__":
    mcp.run(transport='stdio')
