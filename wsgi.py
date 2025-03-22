"""WSGI entry point"""
# Import the Flask app and scheduler
from app import app, start_scheduler
import threading

# Start the scheduler in a separate thread when wsgi is imported
# This ensures follow-up emails are checked and sent
scheduler_thread = threading.Thread(target=start_scheduler)
scheduler_thread.daemon = True
scheduler_thread.start()

# This is only used when running this file directly
if __name__ == "__main__":
    app.run() 