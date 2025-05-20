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
model = genai.GenerativeModel('gemini-pro')

class PRRequest(BaseModel):
    repo_path: str
    jira_ticket: Optional[str] = None
    short: bool = False
    num_commits: Optional[int] = None
    template_path: Optional[str] = None
    remote: str = "origin"

def get_commits(repo_path: str, num_commits: Optional[int] = None, remote: str = "origin") -> List[Dict[str, Any]]:
    """Get commits from the repository."""
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

        # Get commits
        cmd = ['git', 'log', '--pretty=format:%H|%s|%b', '--reverse']
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

def generate_pr_description(commits: List[Dict[str, Any]], jira_ticket: Optional[str] = None, short: bool = False, template_path: Optional[str] = None) -> str:
    """Generate PR description using Gemini."""
    try:
        # Prepare commit messages
        commit_messages = [f"{commit['subject']}" for commit in commits]
        commit_text = "\n".join(commit_messages)

        # Load template if provided
        template = ""
        if template_path and os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template = f.read()

        # Construct prompt
        prompt = """
Generate a pull request (PR) description for the following changes. The PR description MUST include the Jira ticket (if provided) under the Description section. DO NOT include any commit diffs, commit logs, commit lists, or code snippets. Only summarize the changes in natural language. Use the provided template if available. Be concise if the 'short' option is set.

IMPORTANT:
1. If a Jira ticket is provided, include it in the Description section using this exact format:
[JIRA_TICKET]

2. DO NOT include any of the following in your output:
   - Commit diffs
   - Commit logs
   - Code snippets
   - File changes
   - Diff information
   - Any technical details about the changes
   - A "Commits" section
   - Any commit information
   - Any code blocks
   - Any diff blocks
   - Any markdown code blocks

3. Only provide a natural language summary of the changes.
4. DO NOT output any commit list, commit log, or code diff.
5. DO NOT output any markdown code blocks or diff blocks.
6. DO NOT output any commit information or diff information.
7. DO NOT output any technical details about the changes.
8. DO NOT output any file changes or code snippets.
9. DO NOT output any commit or diff information.
10. DO NOT output any commit or diff blocks.
"""
        if jira_ticket:
            prompt += f"\nJira ticket: {jira_ticket}\n"
        if template:
            prompt += f"\nUse the following template:\n{template}\n"
        prompt += "\nSummarize the following commits:\n"
        prompt += commit_text
        if short:
            prompt += "\n\nGenerate a very concise PR description with a brief title, a concise list of changes, and minimal testing steps."
        else:
            prompt += "\n\nGenerate a detailed PR description."
        prompt += "\n\nIMPORTANT: Do NOT include any commit diffs, commit logs, commit lists, or code snippets. The Jira ticket must be included under the Description section. Only summarize the changes in natural language. Do not output any commit list, commit log, or code diff. Only output the PR description in natural language."

        # Generate description
        response = model.generate_content(prompt)
        pr_description = response.text.strip()
        print('RAW MODEL OUTPUT:')
        print(pr_description)

        # Replace the Jira ticket placeholder with the actual ticket
        if jira_ticket:
            pr_description = pr_description.replace(f'[{jira_ticket}]', f'Jira ticket: {jira_ticket}')

        # Remove any diff information, Commits section, and markdown code blocks
        lines = pr_description.split('\n')
        filtered_lines = []
        # Aggressive regex to match keywords and code block starts
        pattern = re.compile(r'(commit[s]?|diff|changes:|```)', re.IGNORECASE)
        for line in lines:
            if pattern.search(line):
                break  # Stop processing further lines entirely
            filtered_lines.append(line)
        # Remove any trailing Jira ticket lines
        while filtered_lines and filtered_lines[-1].strip().lower().startswith('jira ticket:'):
            filtered_lines.pop()
        filtered = '\n'.join(filtered_lines)

        # Failsafe: scan again for any remaining unwanted lines and cut everything after
        lines2 = filtered.split('\n')
        for i, line in enumerate(lines2):
            if pattern.search(line):
                filtered = '\n'.join(lines2[:i])
                break
        print('FILTERED OUTPUT:')
        print(filtered)
        return filtered
    except Exception as e:
        print(f"Error generating PR description: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-pr")
async def generate_pr(request: PRRequest):
    """Generate PR description endpoint."""
    try:
        commits = get_commits(request.repo_path, request.num_commits, request.remote)
        description = generate_pr_description(commits, request.jira_ticket, request.short, request.template_path)
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
