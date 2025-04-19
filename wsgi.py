# Import the Flask app
from app import app

# Application for WSGI servers
application = app

# This is only used when running this file directly
if __name__ == "__main__":
    application.run()