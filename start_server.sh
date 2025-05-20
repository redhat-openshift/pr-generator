#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    echo "GOOGLE_API_KEY=your_api_key_here" > .env
    echo "Please edit .env file and add your Google API key"
    exit 1
fi

# Install requirements if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Kill any existing process on the specified port if --force is passed
if [[ "$*" == *"--force"* ]]; then
    # Extract port number from arguments
    PORT=$(echo "$*" | grep -o -- "--port [0-9]*" | awk '{print $2}')
    if [ -z "$PORT" ]; then
        PORT=8000  # Default port
    fi
    echo "Attempting to kill any existing process on port $PORT..."
    # Kill all processes using the port
    if lsof -ti :"$PORT" > /dev/null 2>&1; then
        lsof -ti :"$PORT" | xargs kill -9
        echo "Killed existing process on port $PORT"
        # Add a small delay to ensure the port is released
        sleep 1
    else
        echo "No existing process found on port $PORT"
    fi
fi

# Start the server with all arguments
# shellcheck disable=SC2068
python pr_mpc_server.py "$@"