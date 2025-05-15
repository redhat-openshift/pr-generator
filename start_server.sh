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

# Start the server
python main.py