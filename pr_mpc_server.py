import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize Gemini model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
DEFAULT_MODEL = 'gemini-2.0-flash-001'
model = genai.GenerativeModel(DEFAULT_MODEL)

class PRRequest(BaseModel):
    repo_path: str
    jira: Optional[str] = None
    commits: Optional[int] = None
    template_path: Optional[str] = None
    remote: str = "origin"
    model: Optional[str] = DEFAULT_MODEL

def get_commits(repo_path: str, num_commits: Optional[int] = None, remote: str = "origin") -> List[Dict[str, Any]]:
    """Get commits from the repository that haven't been pushed to remote."""
    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        current_branch = result.stdout.strip()
        print(f"Current branch: {current_branch}")

        # First, fetch the latest changes from remote
        subprocess.run(['git', 'fetch', remote], cwd=repo_path, capture_output=True)

        # Get commits that haven't been merged into the remote branch
        cmd = ['git', 'log', '--pretty=format:%H|%s|%b', '--reverse', f'{remote}/{current_branch}..HEAD', '--no-merges']
        if num_commits:
            cmd.append(f'-n{num_commits}')
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        commits = []
        for line in result.stdout.splitlines():
            if line.strip():
                commit_hash, subject, body = line.split('|', 2)
                commits.append({
                    'hash': commit_hash,
                    'subject': subject,
                    'body': body
                })
        return commits
    except Exception as e:
        print(f"Error getting commits: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

def generate_pr_description(commits: List[Dict[str, Any]], jira_ticket: Optional[str] = None, template_path: Optional[str] = None, model: Optional[genai.GenerativeModel] = None) -> str:
    """Generate PR description using Gemini."""
    try:
        # Use provided model or default
        if model is None:
            model = genai.GenerativeModel(DEFAULT_MODEL)

        # Remove common prefix from commit messages only if it appears multiple times
        cleaned_commits = []
        prefix_count = {}
        for commit in commits:
            subject = commit['subject']
            if ":" in subject:
                prefix = subject.split(":")[0].strip()
                prefix_count[prefix] = prefix_count.get(prefix, 0) + 1

        # Only remove prefix if it appears more than once
        common_prefix = None
        for prefix, count in prefix_count.items():
            if count > 1:
                common_prefix = prefix
                break

        # Process commits with the common prefix
        for commit in commits:
            subject = commit['subject']
            if common_prefix and subject.startswith(f"{common_prefix}:"):
                # Remove the prefix and colon from the message
                cleaned_commits.append(subject.split(":", 1)[1].strip())
            else:
                cleaned_commits.append(subject)

        # Format commits for the prompt
        commit_text = "\n".join(cleaned_commits)

        # Load template if provided
        template = ""
        if template_path and os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template = f.read()

        # Construct prompt (should still encourage bullets and [JIRA_TICKET] format)
        prompt = f"Generate Pull Request description with a brief title, Jira item (if provided), a list of commit changes, and testing steps."
        prompt += f"\n1. IMPORTANT: After the PR title, add a description section with:\n"
        if jira_ticket: # Add Jira ticket to prompt for context, model should use [JIRA_TICKET]
            prompt += f"\n1. IMPORTANT: Jira {jira_ticket} in a new line.\n"
        prompt += f"\n2. IMPORTANT: Then a list of concise bulleted items for each commit changes:\n"
        prompt += commit_text
        if template:
            prompt += f"\n\nAdd more details according to the following template:\n{template}\n" + \
                "3. If the template includes Testing sections, generate them according to the commits information of (2)." + \
                "4. If the template includes 'Request review criteria' section with [ ] checkboxes, copy them as is."
        prompt += "\n\nIMPORTANT: Do NOT include any markdown code blocks or ```text in your output."
        if common_prefix:
            prompt += f"\nIMPORTANT: The title MUST include \"{common_prefix}\" since it was removed from individual commit messages."

        # Generate description
        response = model.generate_content(prompt)
        pr_description = response.text.strip()
        print('RAW MODEL OUTPUT:')
        print(pr_description)
        return pr_description
    except Exception as e:
        print(f"Error generating PR description: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-pr")
async def generate_pr(request: PRRequest):
    """Generate PR description endpoint."""
    try:
        # Initialize model with requested version
        current_model = genai.GenerativeModel(request.model)
        commits = get_commits(request.repo_path, request.commits, request.remote)
        description = generate_pr_description(commits, request.jira, request.template_path, current_model)
        # Only return the model's generated description (with Jira ticket at the top if needed)
        return {"title": commits[-1]['subject'], "description": description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import argparse
    import socket
    import subprocess

    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--force", action="store_true", help="Force server to start by killing any process using the port")
    args = parser.parse_args()

    if args.force:
        try:
            # Try to find process using the port
            result = subprocess.run(
                ['lsof', '-i', f':{args.port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                # Get the PID from the output
                lines = result.stdout.splitlines()
                if len(lines) > 1:  # Skip header line
                    pid = lines[1].split()[1]
                    print(f"Killing process {pid} using port {args.port}")
                    subprocess.run(['kill', '-9', pid])
                    print(f"Process killed. Starting server on port {args.port}")
        except Exception as e:
            print(f"Warning: Could not kill process on port {args.port}: {str(e)}")

    uvicorn.run(app, host="0.0.0.0", port=args.port)
