# PR Generator - PR Description Generator

A FastAPI server that generates PR descriptions using Google's Gemini AI model based on your git commits.

## Features

- Automatically generates PR descriptions from git commits
- Handles rate limiting with automatic retries
- Works with any git repository
- Supports Jira ticket integration with consistent formatting
- Automatically detects and removes common prefixes from commit messages
- Shows only commits that haven't been merged to upstream yet
- Formats changes as a bulleted list for better readability
- Supports custom PR templates with automatic integration
- Ensures Jira ticket appears exactly once in the correct format

## Prerequisites

- Python 3.8 or higher
- A Google API key for Gemini AI
- Git repository

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd pr-generator
```

2. Create a virtual environment and install dependencies:
```bash
./start_server.sh
```

3. Set up your Google API key:
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key
   - Edit the `.env` file and replace `your_api_key_here` with your actual API key:
```bash
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

## Usage

### Starting the Server

```bash
./start_server.sh
```

The server will start on `http://localhost:8000`.

You can also start the server with custom options:
```bash
# Start with custom port
python pr_mpc_server.py --port 8080

# Force start even if port is in use
python pr_mpc_server.py --port 8080 --force
```

### Server Options

- `--port`: Port number to run the server on (default: 8000)
- `--force`: Force server to start by killing any process using the specified port (requires lsof)

### Using the Client

The client script can be used to generate PR descriptions from any git repository:

```bash
# Basic usage - shows all unmerged commits
python gen_pr.py <repository_path>

# Specify number of commits to include
python gen_pr.py <repository_path> --commits 3

# Include a Jira ticket
python gen_pr.py <repository_path> --jira JIRA-123

# Use a different remote for comparison
python gen_pr.py <repository_path> --remote origin

# Write output to a file
python gen_pr.py <repository_path> --output pr_description.md

# Use custom server host and port
python gen_pr.py <repository_path> --host 192.168.1.100 --port 8080

# Use a custom PR template
python gen_pr.py <repository_path> --template templates/PR_TEMPLATE.md

# Combine options
python gen_pr.py <repository_path> --jira JIRA-123 --commits 3 --remote origin --output pr_description.md --model gemini-2.0-flash-001 --template templates/PR_TEMPLATE.md
```

### Options

- `<repository_path>`: Path to your git repository (required)
- `--jira`: Jira ticket number to include in the description
- `--commits`: Number of commits to include (optional, defaults to all unmerged commits)
- `--remote`: Git remote to use for comparison (default: origin)
- `--template`: Path to a custom PR template file (e.g., templates/PR_TEMPLATE.md)
- `--host`: MPC server host (default: localhost)
- `--port`: MPC server port (default: 8000)
- `--output`: Output file path to write the PR description (optional)
- `--model`: Gemini model to use (default: gemini-2.0-flash-001)

### PR Template

The tool comes with a default PR template that includes:
- Description section
- Testing details
- Test impact analysis
- Review criteria checklist
- Post-merge checklist

To use the template:
```bash
# Use the default template
python gen_pr.py <repository_path> --template templates/PR_TEMPLATE.md

# Use template with other options
python gen_pr.py <repository_path> --jira JIRA-123 --template templates/PR_TEMPLATE.md --output pr_description.md
```

The template will be automatically integrated into the generated PR description, ensuring consistent formatting and required sections.

### Example Output
```
PR Description:
==================================================
Title: Dashboard-E2E Improvements and ODH Operator Enhancements (JIRA-123)

Full Description:
# Dashboard-E2E Improvements and ODH Operator Enhancements (JIRA-123)

Jira ticket: JIRA-123

**Changes:**

* Add retry mechanism for ODH operator deployment
* Set env.PRODUCT to RHOAI if it is "RHODS"
* Pass ODS_BUILD_URL to addICSP() for the image registry
* Get ODH-Nightly for ODH, if no image was specified
* Reset Dashboard-E2E clusters to "dash-e2e-rhoai" and "dash-e2e-odh"

**Testing:**

1. Verify successful deployment of the ODH operator with the retry mechanism.
2. Run Dashboard-E2E tests to ensure functionality with the updated cluster names and image registry configuration.

Request review criteria:
- [ ] Code follows project style guidelines
- [ ] Tests have been added/updated
- [ ] Documentation has been updated

Self checklist:
- [ ] All tests pass
- [ ] Code has been linted
- [ ] No sensitive data in commits

If you have UI changes:
- [ ] Screenshots attached
- [ ] Mobile responsive design verified

After the PR is posted & before it merges:
- [ ] CI/CD pipeline passes
- [ ] Required approvals received
- [ ] Conflicts resolved
```

## Features in Detail

### Common Prefix Handling
- If multiple commits share a common prefix (e.g., "Dashboard-E2E:"), it will be:
  - Removed from individual commit messages
  - Added to the PR title
  - Only applied if the prefix appears in multiple commits

### Commit Selection
- By default, shows all commits that haven't been merged to upstream yet
- Can limit the number of commits with the optional number parameter
- Commits are always shown in reverse chronological order (most recent first)

### Rate Limiting

The server includes automatic retry logic with exponential backoff for rate limit errors. If you hit rate limits:
1. The server will automatically retry up to 3 times
2. Each retry will wait longer than the previous one
3. You can also wait a few minutes before trying again

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

### PR Template Integration

The tool supports custom PR templates that can be automatically integrated into the generated description. To use a custom template:

1. Create a template file with your desired sections
2. Use the `--template` option when running the client:
```bash
python gen_pr.py <repository_path> --template path/to/template.md
```