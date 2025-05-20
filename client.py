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

def generate_pr_description(repo_path: str, num_commits: Optional[int] = None, jira_ticket: Optional[str] = None, short: bool = False, template_path: Optional[str] = None, remote: str = "origin", server_host: str = "localhost", server_port: int = 8000) -> str:
    """Generate a PR description using the MPC server."""
    try:
        # Get the absolute path of the repository
        repo_path = os.path.abspath(repo_path)
        print(f"\nUsing git repository at: {repo_path}")

        # Prepare the request
        request_data = {
            "repo_path": repo_path,
            "jira_ticket": jira_ticket,
            "short": short,
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
    """Write PR description to file. Client ensures final Jira ticket format and presence."""

    processed_description = description # Start with what the server sent

    if jira_ticket:
        jira_placeholder_from_model = f'[{jira_ticket}]' # e.g. [TEST-123]
        final_jira_line = f'Jira ticket: {jira_ticket}' # e.g. Jira ticket: TEST-123

        lines = processed_description.splitlines()
        new_lines = []
        jira_handled = False
        desc_idx = -1

        # Find first ## Description index
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('## description'):
                desc_idx = i
                break

        # Process lines: replace placeholder or remove other forms, ensure only one final Jira line
        for i, line in enumerate(lines):
            if jira_placeholder_from_model in line:
                if not jira_handled:
                    new_lines.append(line.replace(jira_placeholder_from_model, final_jira_line))
                    jira_handled = True
                # else skip if it's a duplicate placeholder
            elif final_jira_line in line: # If model somehow already produced the final format
                if not jira_handled:
                    new_lines.append(line) # Keep it
                    jira_handled = True
                # else skip if it's a duplicate final format
            else:
                new_lines.append(line)

        if not jira_handled:
            # Jira ticket was not found in any format, add it.
            if desc_idx != -1:
                # Insert after the ## Description line
                new_lines.insert(desc_idx + 1, final_jira_line)
            else:
                # No ## Description, add to the top
                new_lines.insert(0, final_jira_line)

        processed_description = '\n'.join(new_lines)

    with open(output_file, 'w') as f:
        f.write(processed_description)

    # Keep the existing clean_pr_description_file for template and other cleanup,
    # but it no longer needs to handle Jira ticket presence.
    clean_pr_description_file(output_file, template_path)

def clean_pr_description_file(output_file, template_path=None):
    # This function no longer needs to worry about jira_ticket
    pattern = re.compile(r'(commit[s]?|diff|changes:|```)', re.IGNORECASE)
    with open(output_file, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if pattern.search(line):
            lines = lines[:i]
            break
    # Remove trailing blank lines
    while lines and lines[-1].strip() == '':
        lines.pop()
    # Ensure template data is present
    if template_path and os.path.exists(template_path):
        with open(template_path, 'r') as f:
            template_content = f.read()
        # Check if template sections are present
        template_sections = ['Request review criteria:', 'Self checklist', 'If you have UI changes:', 'After the PR is posted & before it merges:']
        if not any(section in ''.join(lines) for section in template_sections):
            lines.append('\n' + template_content)
    with open(output_file, 'w') as f:
        f.writelines(lines)

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Generate PR descriptions using the MPC server.")
    parser.add_argument("repo_path", help="Path to the git repository")
    parser.add_argument("jira_ticket", nargs="?", help="Jira ticket number (optional)")
    parser.add_argument("num_commits", nargs="?", type=int, help="Number of commits to include (optional)")
    parser.add_argument("--short", action="store_true", help="Generate a shorter PR description")
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

    # Always overwrite the output file if specified

    pr_description = generate_pr_description(args.repo_path, args.num_commits, args.jira_ticket, args.short, args.template, args.remote, args.server_host, args.server_port)

    if args.output_file:
        write_pr_description(args.output_file, pr_description, args.jira_ticket, args.template)
        print(f"PR description written to {args.output_file}")
    else:
        print(pr_description)

if __name__ == "__main__":
    main()