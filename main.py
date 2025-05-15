import logging
import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()
# Load environment variables from the MPC server directory
load_dotenv(SCRIPT_DIR / '.env')

# Configure Gemini
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key or api_key == 'your_api_key_here':
    raise ValueError("Please set your GOOGLE_API_KEY in the .env file")
genai.configure(api_key=api_key)

# List available models
try:
    models = genai.list_models()
    available_models = [model.name for model in models if 'generateContent' in model.supported_generation_methods]
    logger.info(f"Available models: {available_models}")
    if not available_models:
        raise ValueError("No models available for content generation")
except Exception as e:
    logger.error(f"Error listing models: {str(e)}")
    raise ValueError(f"Failed to list available models: {str(e)}")

app = FastAPI(title="MPC Server for PR Descriptions")

class PRRequest(BaseModel):
    repo_path: str
    num_commits: Optional[int] = None
    jira_ticket: Optional[str] = None
    short: Optional[bool] = False

class PRResponse(BaseModel):
    title: str
    description: str
    changes: List[str]
    testing: List[str]

def get_commits(repo_path: str, num_commits: Optional[int] = None) -> List[str]:
    try:
        logger.info(f"Getting commits from {repo_path}")

        # Get the current branch name using git branch --show-current
        branch_result = subprocess.run(
            ['git', '-C', repo_path, 'branch', '--show-current'],
            capture_output=True,
            text=True
        )
        if branch_result.returncode != 0:
            error_msg = f"Failed to get current branch: {branch_result.stderr}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        current_branch = branch_result.stdout.strip()
        logger.info(f"Current branch: {current_branch}")

        # Get the upstream branch using git remote show upstream
        upstream_result = subprocess.run(
            ['git', '-C', repo_path, 'remote', 'show', 'upstream'],
            capture_output=True,
            text=True
        )
        if upstream_result.returncode != 0:
            error_msg = f"Failed to get upstream remote: {upstream_result.stderr}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # Parse the HEAD branch from the output
        upstream_branch = None
        for line in upstream_result.stdout.split('\n'):
            if 'HEAD branch' in line:
                upstream_branch = line.split(':')[1].strip()
                break

        if not upstream_branch:
            error_msg = "Could not determine upstream branch"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        logger.info(f"Upstream branch: {upstream_branch}")

        # Get commits that are not yet merged to upstream
        cmd = ['git', '-C', repo_path, 'log']
        if num_commits:
            cmd.extend(['-n', str(num_commits)])
        cmd.extend([f'upstream/{upstream_branch}..{current_branch}', '--pretty=format:%s'])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = f"Git command failed: {result.stderr}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        commits = [line for line in result.stdout.split('\n') if line.strip()]
        if not commits:
            error_msg = "No commits found"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # Reverse the commits to show most recent first
        commits.reverse()
        logger.info(f"Found {len(commits)} commits")
        return commits
    except Exception as e:
        error_msg = f"Error getting commits: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

def generate_pr_description(commits: List[str], jira_ticket: Optional[str] = None, short: bool = False) -> PRResponse:
    try:
        logger.info("Initializing Gemini model")
        # Initialize Gemini model - using gemini-1.5-flash which has higher rate limits
        model = genai.GenerativeModel('models/gemini-1.5-flash')

        # Remove common prefix from commit messages only if it appears multiple times
        cleaned_commits = []
        prefix_count = {}
        for commit in commits:
            if ":" in commit:
                prefix = commit.split(":")[0].strip()
                prefix_count[prefix] = prefix_count.get(prefix, 0) + 1

        # Only remove prefix if it appears more than once
        common_prefix = None
        for prefix, count in prefix_count.items():
            if count > 1:
                common_prefix = prefix
                break

        # Process commits with the common prefix
        for commit in commits:
            if common_prefix and commit.startswith(f"{common_prefix}:"):
                # Remove the prefix and colon from the message
                cleaned_commits.append(commit.split(":", 1)[1].strip())
            else:
                cleaned_commits.append(commit)

        # Format commits for the prompt - explicitly reverse the order
        formatted_commits = []
        for i, commit in enumerate(reversed(cleaned_commits), 1):
            formatted_commits.append(f"{i}. {commit}")
        commits_text = "\n".join(formatted_commits)

        # Prepare the prompt
        if short:
            prompt = f"""Based on these git commits, listed from most recent to oldest:
{commits_text}

{f'And Jira ticket: {jira_ticket}' if jira_ticket else ''}

Generate a brief PR description with:
1. A specific and descriptive title that reflects the actual changes in the commits{" - MUST include \"" + common_prefix + "\" in the title" if common_prefix else ""} - DO NOT start with # or any other markdown characters
2. List ALL commits as bullet points under Changes, keeping the same order (most recent first)
3. Basic testing steps (1-2 points)

Keep it very brief and to the point. Format in markdown.
IMPORTANT:
- Use the exact commit messages
- Keep the same order as the commits (most recent first)
- List ALL commits as separate bullet points under Changes
- The first commit in the list should be the most recent one
- Do not change the order of the commits
- If a common prefix was removed from commit messages, it MUST be included in the title
- Do NOT start the title with # or any other markdown characters
- Make the title specific to the actual changes in the commits, not generic"""
        else:
            prompt = f"""Based on these git commits, listed from most recent to oldest:
{commits_text}

{f'And Jira ticket: {jira_ticket}' if jira_ticket else ''}

Generate a PR description with:
1. A specific and descriptive title that reflects the actual changes in the commits{" - MUST include \"" + common_prefix + "\" in the title" if common_prefix else ""} - DO NOT start with # or any other markdown characters
2. A list of changes
3. Testing steps
4. Any additional notes

Format it in markdown.
IMPORTANT:
- Use the exact commit messages to describe changes, do not paraphrase
- List each commit as a separate bullet point
- Keep the same order as the commits (most recent first)
- The first commit in the list should be the most recent one
- Do not change the order of the commits
- If a common prefix was removed from commit messages, it MUST be included in the title
- Do NOT start the title with # or any other markdown characters
- Make the title specific to the actual changes in the commits, not generic"""

        logger.info("Generating response from Gemini")
        max_retries = 3
        retry_delay = 30  # seconds

        for attempt in range(max_retries):
            try:
                # Generate response
                response = model.generate_content(prompt)
                if not response or not response.text:
                    error_msg = "Empty response from Gemini"
                    logger.error(error_msg)
                    raise HTTPException(status_code=500, detail=error_msg)

                description = response.text
                logger.info("Successfully generated description")

                # Extract sections (this is a simple implementation)
                lines = description.split('\n')
                title = lines[0].replace('# ', '')
                changes = []
                testing = []
                current_section = None

                for line in lines[1:]:
                    if line.startswith('## Changes'):
                        current_section = 'changes'
                    elif line.startswith('## Testing'):
                        current_section = 'testing'
                    elif line.startswith('- ') and current_section:
                        if current_section == 'changes':
                            changes.append(line[2:])
                        elif current_section == 'testing':
                            testing.append(line[2:])

                return PRResponse(
                    title=title,
                    description=description,
                    changes=changes,
                    testing=testing
                )
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise

    except Exception as e:
        error_msg = f"Error generating PR description: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/generate-pr", response_model=PRResponse)
async def generate_pr(request: PRRequest):
    logger.info(f"Received request for repo: {request.repo_path}")
    commits = get_commits(request.repo_path, request.num_commits)
    return generate_pr_description(commits, request.jira_ticket, request.short)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)