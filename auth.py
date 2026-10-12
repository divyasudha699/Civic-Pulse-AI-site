
import os, re, secrets, base64, hashlib, smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

def valid_email(e):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (e or "").strip()))

def make_hash(password, salt=None):
    raw_salt = base64.b64decode(salt.encode()) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), raw_salt, 150000)
    return base64.b64encode(raw_salt).decode(), base64.b64encode(digest).decode()

def check_hash(password, salt, expected_hash):
    return secrets.compare_digest(make_hash(password, salt)[1], expected_hash)

def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"

def otp_expiry():
    return datetime.now() + timedelta(minutes=10)

def otp_valid(expected, expiry, entered):
    return bool(expected and expiry and datetime.now() <= expiry and secrets.compare_digest(str(expected), str(entered).strip()))

def send_otp_email(email, code):
    user = os.getenv("SMTP_USER","").strip()
    password = os.getenv("SMTP_PASSWORD","").strip()
    host = os.getenv("SMTP_HOST","smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT","587"))
    if not user or not password:
        return False, "SMTP not configured"
    msg = EmailMessage()
    msg["Subject"] = "Civic Pulse AI Login OTP"
    msg["From"] = os.getenv("SMTP_FROM", user)
    msg["To"] = email
    msg.set_content(f"Your Civic Pulse AI OTP is {code}. It is valid for 10 minutes.")
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return True, "OTP sent to your email."
    except Exception as e:
        return False, str(e)
