# PR Generator - PR Description Generator

A FastAPI server that generates PR descriptions using Google's Gemini AI model based on your git commits.

## Features

- Automatically generates PR descriptions from git commits
- Supports both detailed and concise descriptions
- Handles rate limiting with automatic retries
- Works with any git repository
- Supports Jira ticket integration
- Automatically detects and removes common prefixes from commit messages
- Shows only commits that haven't been merged to upstream yet

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

### Using the Client

The client script can be used to generate PR descriptions from any git repository:

```bash
# Basic usage - shows all unmerged commits
python client.py <repository_path>

# Generate a concise description
python client.py <repository_path> --short

# Specify number of commits to include
python client.py <repository_path> JIRA-123 3

# Include a Jira ticket
python client.py <repository_path> JIRA-123

# Combine options
python client.py <repository_path> JIRA-123 3 --short
```

### Options

- `<repository_path>`: Path to your git repository (required)
- `--short`: Generate a concise description
- `<jira_ticket>`: Jira ticket number to include in the description
- `<number>`: Number of commits to include (optional, defaults to all unmerged commits)

## Example Output

### Short Description
```
PR Description:
==================================================
Title: Dashboard-E2E Improvements and ODH Operator Enhancements (JIRA-123)

Full Description:
# Dashboard-E2E Improvements and ODH Operator Enhancements (JIRA-123)

**Changes:**

* Add retry mechanism for ODH operator deployment
* Set env.PRODUCT to RHOAI if it is "RHODS"
* Pass ODS_BUILD_URL to addICSP() for the image registry
* Get ODH-Nightly for ODH, if no image was specified
* Reset Dashboard-E2E clusters to "dash-e2e-rhoai" and "dash-e2e-odh"

**Testing:**

1. Verify successful deployment of the ODH operator with the retry mechanism.
2. Run Dashboard-E2E tests to ensure functionality with the updated cluster names and image registry configuration.
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

[Your chosen license]