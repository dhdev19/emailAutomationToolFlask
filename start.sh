#!/bin/bash

# Activate virtual environment (if using one)
# source venv/bin/activate

# Set environment variables from .env
export $(grep -v '^#' .env | xargs)

# Start Gunicorn with your app
gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 wsgi:application 