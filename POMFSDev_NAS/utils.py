import smtplib
from email.mime.text import MIMEText
import os
import shutil

# SMTP Configuration
# SYSTEM ENV VARIABLES should be set for security in production
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your_email@gmail.com"  # Replace or use env var
SMTP_PASSWORD = "your_app_password" # Replace or use env var

def send_email_notification(count, recipient="kkwonjubu@gmail.com"):
    """
    Sends an email notification about registered events.
    """
    subject = f"P.O.MFS 공연 {count}건 등록 완료!"
    content = f"""
    [P.O.MFS 알림]
    
    관리자 페이지를 통해 새로운 공연 정보 {count}건이 성공적으로 데이터베이스에 등록되었습니다.
    
    관리자 페이지에서 확인하세요.
    """
    
    msg = MIMEText(content)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = recipient
    
    try:
        # Note: This will only work if valid credentials are provided or configured.
        # For local test without creds, we print to console.
        if SMTP_USER == "your_email@gmail.com":
            print(">>> [Mock Email] Skipping actual email send (No credentials).")
            print(f"To: {recipient}\nSubject: {subject}\nContent: ...")
            return
            
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f">>> Email sent to {recipient}")
            
    except Exception as e:
        print(f">>> Failed to send email: {e}")

def save_local_image(source_path, filename):
    """
    Copies image from source path to static/images directory.
    Returns the relative path for DB storage.
    """
    target_dir = os.path.join(os.getcwd(), 'static', 'images')
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    target_path = os.path.join(target_dir, filename)
    
    # DB stores path relative to static/ or just filename?
    # Usually easier to store 'static/images/filename.jpg' or just '/static/images/...'
    db_path = f"/static/images/{filename}"
    
    try:
        # Check if source exists
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            return db_path
        else:
            print(f"Warning: Source image not found at {source_path}")
            return None # Or default placeholder
    except Exception as e:
        print(f"Error copying image: {e}")
        return None
