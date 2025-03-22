from flask import Flask, render_template, request, redirect, flash, jsonify
import os
import pandas as pd
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import random
import string
import math
import threading
import time
from datetime import datetime
import sqlite3
import pytz
from threading import Event

# Check if running on Render
if 'RENDER' in os.environ:
    # Use Render disk path if disk is mounted
    base_path = "/opt/render/project/src/data" if os.path.exists("/opt/render/project/src/data") else "/opt/render/project/src"
else:
    # Use local paths for development
    base_path = "."

# Configure paths based on environment
UPLOAD_FOLDER = os.path.join(base_path, "uploads")
DB_FOLDER = os.path.join(base_path, "database")

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this

# Configure file upload folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'default_email@example.com'
app.config['MAIL_PASSWORD'] = 'default_password'
app.config['MAIL_DEFAULT_SENDER'] = 'default_email@example.com'

mail = Mail(app)

# Set path for database file
DB_PATH = os.path.join(DB_FOLDER, "emails.db")

# Create SQLite database for tracking emails
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create emails table
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_email TEXT NOT NULL,
            sender_password TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_date TEXT NOT NULL,
            followup_date TEXT,
            followup_sent INTEGER DEFAULT 0,
            followup_body TEXT
        )
    ''')
    
    # Create a table to store email credentials
    c.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

# Initialize database
init_db()

ALLOWED_EXTENSIONS = {'xlsx', 'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        subject = request.form.get("subject")
        body = request.form.get("body")
        followup_days = request.form.get("followup_days")
        followup_datetime = request.form.get("followup_datetime")
        use_days = request.form.get("use-days") == "on"
        followup_body = request.form.get("followup_body")
        
        # Check if followup is enabled
        has_followup = False
        if followup_body:
            has_followup = True
            
            # Validate days or datetime based on which option is selected
            if use_days and followup_days:
                try:
                    followup_days = int(followup_days)
                except ValueError:
                    flash("Follow-up days must be a number", "error")
                    return redirect("/dashboard")
            elif not use_days and followup_datetime:
                try:
                    # Parse the datetime-local value
                    from datetime import datetime
                    datetime.strptime(followup_datetime, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash("Invalid follow-up date/time format", "error")
                    return redirect("/dashboard")
            else:
                flash("Please provide valid follow-up timing", "error")
                return redirect("/dashboard")

        # Get the Excel file with recipient data
        recipients_file = request.files["xlsx_file"]
        if not (recipients_file and allowed_file(recipients_file.filename)):
            flash("Please upload a valid XLSX file with recipients", "error")
            return redirect("/dashboard")

        filename = secure_filename(recipients_file.filename)
        recipients_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        recipients_file.save(recipients_path)

        try:
            recipients_df = pd.read_excel(recipients_path)
            if "name" not in recipients_df.columns or "email" not in recipients_df.columns:
                flash("Recipients XLSX must contain 'name' and 'email' columns!", "error")
                return redirect("/dashboard")
        except Exception as e:
            flash(f"Error reading recipients XLSX: {e}", "error")
            return redirect("/dashboard")

        # Get the Excel file with sender login credentials
        login_file = request.files["login_file"]
        if not (login_file and allowed_file(login_file.filename)):
            flash("Please upload a valid XLSX file with login credentials", "error")
            return redirect("/dashboard")

        login_filename = secure_filename(login_file.filename)
        login_path = os.path.join(app.config["UPLOAD_FOLDER"], login_filename)
        login_file.save(login_path)

        try:
            login_df = pd.read_excel(login_path)
            if "email" not in login_df.columns or "password" not in login_df.columns:
                flash("Login XLSX must contain 'email' and 'password' columns!", "error")
                return redirect("/dashboard")
            
            # Validate that we have at least one valid login
            if len(login_df) == 0:
                flash("Login file must contain at least one email account!", "error")
                return redirect("/dashboard")
        except Exception as e:
            flash(f"Error reading login XLSX: {e}", "error")
            return redirect("/dashboard")

        # Process attachment files
        attachments = []
        if "attachments" in request.files:
            files = request.files.getlist("attachments")
            if not files:
                flash("No attachment files were found.", "warning")
            for file in files:
                if file.filename == '':
                    continue  # Skip files with empty filename
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                    attachments.append(file_path)
                    flash(f"Uploaded attachment: {filename}", "success")
                else:
                    flash(f"Skipped file: {file.filename} (invalid type)", "warning")
        
        # Calculate how to distribute emails
        total_recipients = len(recipients_df)
        total_senders = len(login_df)
        
        recipients_per_sender = math.ceil(total_recipients / total_senders)
        
        sender_index = 0
        emails_sent = 0
        errors = 0
        
        # Connect to database for storing email records
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Current date and time
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate followup date if needed
        followup_date = None
        if has_followup:
            from datetime import timedelta
            
            if use_days and followup_days:
                # Calculate based on days offset
                followup_date = (now + timedelta(days=followup_days)).strftime("%Y-%m-%d %H:%M:%S")
            elif not use_days and followup_datetime:
                # Use specific datetime
                try:
                    # Convert the datetime-local value to a datetime object
                    specific_datetime = datetime.strptime(followup_datetime, '%Y-%m-%dT%H:%M')
                    followup_date = specific_datetime.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    flash("Invalid follow-up date/time format", "error")
                    return redirect("/dashboard")
        
        # Store all credentials in credentials table for future use
        for _, row in login_df.iterrows():
            email = row["email"]
            password = row["password"]
            
            # Store or update credential
            c.execute('INSERT OR REPLACE INTO credentials (email, password) VALUES (?, ?)', 
                     (email, password))
        
        conn.commit()
        
        # Iterate through recipients and send emails using the sender accounts
        for i, recipient_row in recipients_df.iterrows():
            # Determine which sender to use
            sender_row = login_df.iloc[sender_index]
            sender_email = sender_row["email"]
            sender_password = sender_row["password"]
            
            # Configure mail for this sender
            app.config['MAIL_USERNAME'] = sender_email
            app.config['MAIL_PASSWORD'] = sender_password
            app.config['MAIL_DEFAULT_SENDER'] = sender_email
            
            # Reinitialize mail with new settings
            mail = Mail(app)
            
            try:
                # Create message
                msg = Message(subject, recipients=[recipient_row["email"]])
                msg.body = f"Hello {recipient_row['name']},\n\n{body}"

                # Add attachments
                for attach in attachments:
                    with open(attach, "rb") as f:
                        msg.attach(os.path.basename(attach), "application/octet-stream", f.read())

                # Send email
                mail.send(msg)
                emails_sent += 1
                
                # Store in database
                c.execute('''
                    INSERT INTO emails (sender_email, sender_password, recipient_email, recipient_name, subject, body, sent_date, followup_date, followup_body) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sender_email,
                    sender_password,
                    recipient_row["email"],
                    recipient_row["name"],
                    subject,
                    body,
                    current_date,
                    followup_date,
                    followup_body if has_followup else None
                ))
                conn.commit()
                
                # Move to next sender after sending the calculated number of emails
                if (i + 1) % recipients_per_sender == 0 and sender_index < total_senders - 1:
                    sender_index += 1
                    flash(f"Switched to sender: {login_df.iloc[sender_index]['email']}", "info")
            
            except Exception as e:
                errors += 1
                flash(f"Error sending email to {recipient_row['email']}: {e}", "error")
                
                # If we encounter an error with this sender, try the next one
                if sender_index < total_senders - 1:
                    sender_index += 1
                    flash(f"Error with sender, switched to: {login_df.iloc[sender_index]['email']}", "warning")

        conn.close()
        
        # Start the followup scheduler if needed
        if has_followup:
            scheduler_thread = threading.Thread(target=followup_scheduler)
            scheduler_thread.daemon = True
            scheduler_thread.start()
            
        flash(f"Email sending complete: {emails_sent} sent, {errors} failed", "success")
        if has_followup:
            if use_days:
                flash(f"Follow-up emails scheduled for {followup_days} days later", "info")
            else:
                from datetime import datetime
                followup_dt = datetime.strptime(followup_date, "%Y-%m-%d %H:%M:%S")
                formatted_date = followup_dt.strftime("%B %d, %Y at %I:%M %p")
                flash(f"Follow-up emails scheduled for {formatted_date}", "info")

    return render_template("dashboard.html")

def followup_scheduler():
    """Background thread to check and send follow-up emails"""
    print("Follow-up scheduler started")
    while True:
        try:
            # Connect to database
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Current time
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S")
            
            # Find emails that need follow-up
            c.execute('''
                SELECT id, sender_email, sender_password, recipient_email, recipient_name, subject, followup_body 
                FROM emails 
                WHERE followup_date <= ? 
                AND followup_sent = 0
                AND followup_body IS NOT NULL
            ''', (current_time,))
            
            emails_to_followup = c.fetchall()
            print(f"Found {len(emails_to_followup)} emails due for follow-up")
            
            for email in emails_to_followup:
                email_id = email['id']
                sender_email = email['sender_email']
                sender_password = email['sender_password']
                recipient_email = email['recipient_email']
                recipient_name = email['recipient_name']
                subject = email['subject']
                followup_body = email['followup_body']
                
                print(f"Sending follow-up to {recipient_email} from {sender_email}")
                
                try:
                    # Create a new Flask app context for mail
                    with app.app_context():
                        # Configure mail for this sender
                        mail_config = {
                            'MAIL_SERVER': 'smtp.gmail.com',
                            'MAIL_PORT': 587,
                            'MAIL_USE_TLS': True,
                            'MAIL_USE_SSL': False,
                            'MAIL_USERNAME': sender_email,
                            'MAIL_PASSWORD': sender_password,  # Use stored password from database
                            'MAIL_DEFAULT_SENDER': sender_email
                        }
                        
                        # Create a new mail instance with this config
                        mail_app = Flask(f"mail_app_{email_id}")
                        for key, value in mail_config.items():
                            mail_app.config[key] = value
                        
                        with mail_app.app_context():
                            mail_instance = Mail(mail_app)
                            
                            # Create follow-up message
                            followup_subject = f"Follow-up: {subject}"
                            msg = Message(followup_subject, recipients=[recipient_email])
                            msg.body = f"Hello {recipient_name},\n\n{followup_body}"
                            
                            # Send follow-up email
                            mail_instance.send(msg)
                            
                            # Update database
                            c.execute('''
                                UPDATE emails 
                                SET followup_sent = 1 
                                WHERE id = ?
                            ''', (email_id,))
                            conn.commit()
                            print(f"Successfully sent follow-up to {recipient_email}")
                except Exception as e:
                    print(f"Error sending follow-up to {recipient_email}: {str(e)}")
            
            conn.close()
            
            # Sleep for 1 minute before checking again
            time.sleep(60)
            
        except Exception as e:
            print(f"Error in follow-up scheduler: {str(e)}")
            # Sleep for 30 seconds before retrying
            time.sleep(30)

# Create a separate function to manage the single global instance of the scheduler
def start_scheduler():
    # Start the followup scheduler in a background thread
    scheduler_thread = threading.Thread(target=followup_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    print("Scheduler thread started")

@app.route('/emails')
def view_emails():
    """View all emails and their status"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT * FROM emails ORDER BY sent_date DESC
    ''')
    
    emails = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return render_template('emails.html', emails=emails)

@app.route('/send-followup/<int:email_id>', methods=['GET'])
def send_followup(email_id):
    """Manually trigger follow-up for a specific email"""
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find the email
        c.execute('SELECT * FROM emails WHERE id = ?', (email_id,))
        email = c.fetchone()
        
        if not email:
            flash(f"Email ID {email_id} not found", "error")
            return redirect('/emails')
        
        # Create a local function to send the follow-up
        def send_single_followup():
            if email['followup_sent'] == 1:
                flash(f"Follow-up for email ID {email_id} was already sent", "warning")
                return False
                
            if not email['followup_body']:
                flash(f"Email ID {email_id} has no follow-up message", "error")
                return False
                
            try:
                # Get the sender password 
                sender_password = email['sender_password']
                
                # Configure mail for this sender
                mail_config = {
                    'MAIL_SERVER': 'smtp.gmail.com',
                    'MAIL_PORT': 587,
                    'MAIL_USE_TLS': True,
                    'MAIL_USE_SSL': False,
                    'MAIL_USERNAME': email['sender_email'],
                    'MAIL_PASSWORD': sender_password,  # Use stored password
                    'MAIL_DEFAULT_SENDER': email['sender_email']
                }
                
                # Create a new mail instance with this config
                mail_app = Flask(f"mail_app_{email_id}")
                for key, value in mail_config.items():
                    mail_app.config[key] = value
                
                with mail_app.app_context():
                    mail_instance = Mail(mail_app)
                    
                    # Create follow-up message
                    followup_subject = f"Follow-up: {email['subject']}"
                    msg = Message(followup_subject, recipients=[email['recipient_email']])
                    msg.body = f"Hello {email['recipient_name']},\n\n{email['followup_body']}"
                    
                    # Send follow-up email
                    mail_instance.send(msg)
                    
                    # Update database
                    c.execute('UPDATE emails SET followup_sent = 1 WHERE id = ?', (email_id,))
                    conn.commit()
                    
                    flash(f"Follow-up email sent to {email['recipient_email']}", "success")
                    return True
            except Exception as e:
                flash(f"Error sending follow-up: {str(e)}", "error")
                return False
        
        # Send the follow-up
        success = send_single_followup()
        
        conn.close()
        
        return redirect('/emails')
    
    except Exception as e:
        flash(f"Error processing follow-up: {str(e)}", "error")
        return redirect('/emails')

if __name__ == '__main__':
    # Start the background scheduler
    start_scheduler()
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 5000))
    
    # Run the app on 0.0.0.0 to make it accessible externally
    app.run(host='0.0.0.0', port=port, debug=False)

