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
model = genai.GenerativeModel('gemini-2.0-flash-001')

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

        # Construct prompt (should still encourage bullets and [JIRA_TICKET] format)
        prompt = """
Generate a pull request (PR) description for the following changes. The PR description MUST include the Jira ticket (if provided) under the Description section. DO NOT include any commit diffs, commit logs, commit lists, or code snippets. Use the provided template if available. Be concise if the 'short' option is set.

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

3. Summarize the main changes as a bulleted list under the Description section, appearing after the Jira ticket. Start the bulleted list with a phrase like "Key changes include:" or "This PR includes the following updates:".
4. DO NOT output any commit list, commit log, or code diff.
5. DO NOT output any markdown code blocks or diff blocks.
6. DO NOT output any commit information or diff information.
7. DO NOT output any technical details about the changes.
8. DO NOT output any file changes or code snippets.
9. DO NOT output any commit or diff information.
10. DO NOT output any commit or diff blocks.
"""
        if jira_ticket: # Add Jira ticket to prompt for context, model should use [JIRA_TICKET]
            prompt += f"\nJira ticket for context: {jira_ticket}\n"
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

        # Server-side post-processing: ONLY remove template comments and basic unwanted patterns.
        # NO server-side Jira manipulation.

        lines = pr_description.split('\n')
        cleaned_lines = []
        template_comment_pattern = re.compile(r'^<!---.*-->$')
        for line in lines:
            if not template_comment_pattern.search(line.strip()):
                cleaned_lines.append(line)
        pr_description = '\n'.join(cleaned_lines)

        # Main content filtering (commits, diffs, etc.) - keep this less aggressive
        lines = pr_description.split('\n')
        filtered_lines_final = []
        pattern = re.compile(r'(commit[s]?|diff|```)', re.IGNORECASE) # No "changes:"
        for line in lines:
            if pattern.search(line):
                break
            filtered_lines_final.append(line)
        filtered = '\n'.join(filtered_lines_final)

        # Final cleanup for excessive newlines
        filtered = re.sub(r'\n{3,}', '\n\n', filtered).strip()

        print('FILTERED OUTPUT (Server):')
        print(filtered) # This output will go to the client
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
