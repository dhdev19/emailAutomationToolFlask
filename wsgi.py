"""WSGI entry point"""
# Import the Flask app and scheduler
import os
import sys
import logging

# Add your application directory to path
sys.path.insert(0, '/home/username/yourappfolder')

# Set production environment variable
os.environ['FLASK_ENV'] = 'production'
os.environ['HOSTINGER'] = 'true'

# Import the app after setting environment variables
from app import app, configure_logging, start_scheduler

# Set up logging
configure_logging()

# Start the scheduler in a background thread
start_scheduler()

# Application for WSGI servers
application = app

# This is only used when running this file directly
if __name__ == "__main__":
    application.run() 