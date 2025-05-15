import argparse
import os
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

def generate_pr_description(repo_path: str, num_commits: Optional[int] = None, jira_ticket: Optional[str] = None, short: bool = False) -> None:
    """Generate a PR description using the MPC server."""
    try:
        # Get the absolute path of the repository
        repo_path = os.path.abspath(repo_path)
        print(f"\nUsing git repository at: {repo_path}")

        # Prepare the request
        request_data = {
            "repo_path": repo_path,
            "jira_ticket": jira_ticket,
            "short": short
        }
        if num_commits:
            request_data["num_commits"] = num_commits

        # Send request to the server
        response = requests.post(
            "http://localhost:8000/generate-pr",
            json=request_data
        )
        response.raise_for_status()

        # Print the PR description
        data = response.json()
        print("\nPR Description:")
        print("=" * 50)
        print(f"Title: {data['title']}\n")
        print("Full Description:")
        print(data['description'])

    except requests.exceptions.RequestException as e:
        print(f"Error: Could not connect to the MPC server. Make sure it's running. ({str(e)})")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Generate PR descriptions using the MPC server.")
    parser.add_argument("repo_path", help="Path to the git repository")
    parser.add_argument("jira_ticket", nargs="?", help="Jira ticket number (optional)")
    parser.add_argument("num_commits", nargs="?", type=int, help="Number of commits to include (optional)")
    parser.add_argument("--short", action="store_true", help="Generate a shorter PR description")

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

    generate_pr_description(args.repo_path, args.num_commits, args.jira_ticket, args.short)

if __name__ == "__main__":
    main()