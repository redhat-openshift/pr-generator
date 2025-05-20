import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests


def get_git_root(path):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None

def generate_pr_description(repo_path: str, num_commits: Optional[int] = None, jira_ticket: Optional[str] = None, template_path: Optional[str] = None, remote: str = "origin", server_host: str = "localhost", server_port: int = 8000) -> str:
    """Generate a PR description using the MPC server."""
    try:
        # Get the absolute path of the repository
        repo_path = os.path.abspath(repo_path)
        print(f"\nUsing git repository at: {repo_path}")

        # Prepare the request
        request_data = {
            "repo_path": repo_path,
            "jira_ticket": jira_ticket,
            "remote": remote
        }
        if num_commits:
            request_data["num_commits"] = num_commits
        if template_path:
            request_data["template_path"] = template_path

        url = f"http://{server_host}:{server_port}/generate-pr"
        response = requests.post(url, json=request_data)
        response.raise_for_status()

        # Only use the PR description from the server response
        data = response.json()
        return data['description']

    except requests.exceptions.RequestException as e:
        print(f"Error: Could not connect to the MPC server. Make sure it's running. ({str(e)})")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def write_pr_description(output_file: str, description: str, jira_ticket: Optional[str] = None, template_path: Optional[str] = None) -> None:
    """Write PR description to file."""
    # Write the raw description directly to file
    with open(output_file, 'w') as f:
        f.write(description)

def clean_pr_description_file(output_file, template_path=None):
    # This function is no longer needed as we want to preserve the exact server output
    pass

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Generate PR descriptions using the MPC server.")
    parser.add_argument("repo_path", help="Path to the git repository")
    parser.add_argument("jira_ticket", nargs="?", help="Jira ticket number (optional)")
    parser.add_argument("num_commits", nargs="?", type=int, help="Number of commits to include (optional)")
    parser.add_argument("--template", help="Path to PR template file (optional)")
    parser.add_argument("--remote", default="origin", help="Git remote to use for comparison (default: origin)")
    parser.add_argument("--server-port", type=int, default=8000, help="MPC server port (default: 8000)")
    parser.add_argument("--server-host", default="localhost", help="MPC server host (default: localhost)")
    parser.add_argument('--output-file', help='Output file path to write the PR description (optional)')

    args = parser.parse_args()

    # Validate repository path
    if not os.path.isdir(args.repo_path):
        print(f"Error: Repository path '{args.repo_path}' is not a valid directory")
        sys.exit(1)

    # Validate git repository
    try:
        subprocess.run(
            ["git", "-C", args.repo_path, "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        print(f"Error: '{args.repo_path}' is not a git repository")
        sys.exit(1)

    # Get the raw description from the server
    pr_description = generate_pr_description(args.repo_path, args.num_commits, args.jira_ticket, args.template, args.remote, args.server_host, args.server_port)

    if args.output_file:
        # Write raw server output to file without any processing
        write_pr_description(args.output_file, pr_description)
        print(f"PR description written to {args.output_file}")
    else:
        # Print raw server output without any processing
        print(pr_description)

if __name__ == "__main__":
    main()