# Mass Email Sender

An application for sending bulk emails with follow-up scheduling capabilities.

## Features

- Send mass emails to multiple recipients at once
- Use multiple sender accounts to distribute the email sending workload
- Schedule follow-up emails with specific dates and times
- Track all sent emails and their follow-up status
- Upload attachments to include with your emails

## Deployment on Render

### Option 1: Quick Deployment (Recommended)

1. Fork this repository on GitHub
2. Sign up for Render (https://render.com)
3. In Render dashboard, click "New" and select "Blueprint"
4. Select your forked repository
5. Render will automatically configure everything from the render.yaml file:
   - Creates a web service with Python environment
   - Sets up a 1GB persistent disk for data storage
   - Generates a random SECRET_KEY
   - Runs the setup.py script to prepare directories

### Option 2: Manual Setup

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - Environment: Python
   - Python Version: 3.10 (specified in the "Environment Variables" section)
   - Build Command: `pip install -r requirements.txt && python setup.py`
   - Start Command: `gunicorn wsgi:app`
4. Set up environment variables:
   - `SECRET_KEY`: A random string for app security (use Render's "Generate" feature)
   - `PYTHON_VERSION`: 3.10.13
5. Add a disk in the Render "Disks" section:
   - Name: data
   - Mount Path: `/opt/render/project/src/data`
   - Size: 1GB minimum

## Email Credentials

This application uses email credentials exclusively from your uploaded Excel file for both initial and follow-up emails:

1. When you upload a login credentials Excel file, all credentials are securely stored in the application database
2. When sending follow-up emails, the system uses the same sender email address and password that was used for the initial email

## Local Development

1. Create a virtual environment: `python -m venv env`
2. Activate the virtual environment:
   - Windows: `env\Scripts\activate`
   - macOS/Linux: `source env/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the application: `python app.py`
5. Access the application at http://localhost:5000

## File Formats

### Recipients Excel File
Must contain columns: 
- `name` - Recipient's name
- `email` - Recipient's email address

### Login Credentials Excel File
Must contain columns:
- `email` - Sender's email address
- `password` - Sender's app password (for Gmail)

## Troubleshooting Deployment

If you encounter any issues during deployment:

1. Check the Render logs for detailed error messages
2. Ensure the disk is properly mounted by checking the logs
3. Verify that your Python version is set to 3.10.x
4. If you're still having trouble, try redeploying the service 