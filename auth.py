import os, secrets, hashlib, smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import Blueprint, request, jsonify, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from db import connection
from flask import current_app

auth = Blueprint('auth', __name__)

def current_user():
    uid = session.get('user_id')
    if not uid: return None
    with connection() as db:
        with db.cursor() as cur:
            cur.execute('SELECT user_id AS id,full_name,email,role,email_verified,is_active FROM users WHERE user_id=%s', (uid,))
            u=cur.fetchone()
    return u if u and u['is_active'] and u['email_verified'] else None

def otp_hash(email, code):
    return hashlib.sha256((email.lower()+':'+code+':'+os.environ['SECRET_KEY']).encode()).hexdigest()

def send_email(address, code):
    msg=EmailMessage()
    msg['Subject']='ParkVision email verification code'
    msg['From']=os.environ['SMTP_FROM']
    msg['To']=address
    msg.set_content(f'Your ParkVision verification code is {code}. It expires in 10 minutes. Do not share this code.')
    with smtplib.SMTP(os.environ.get('SMTP_HOST','smtp.gmail.com'), int(os.environ.get('SMTP_PORT','587')), timeout=20) as server:
        server.starttls()
        server.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
        server.send_message(msg)

@auth.get('/login')
def login_page(): return render_template('login.html')
@auth.get('/signup')
def signup_page(): return render_template('signup.html')
@auth.get('/verify')
def verify_page(): return render_template('verify.html')
@auth.get('/api/auth/me')
def me(): return jsonify(user=current_user())

@auth.post('/api/auth/signup')
def signup():
    p=request.get_json(silent=True) or {}
    name=str(p.get('name','')).strip(); email=str(p.get('email','')).strip().lower(); password=str(p.get('password',''))
    if not (1<=len(name)<=100 and 3<=len(email)<=255 and '@' in email and '.' in email.rsplit('@',1)[-1] and 10<=len(password)<=128):
        return jsonify(error='Enter a valid name, email and password of at least 10 characters.'),400
    code=f'{secrets.randbelow(1000000):06d}'
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                'SELECT user_id AS id, email_verified FROM users WHERE email=%s',
                (email,)
            )
            found = cur.fetchone()
            if found and found['email_verified']: return jsonify(error='Account exists. Please log in.'),409
            cur.execute(
                """
                SELECT created_at
                FROM email_otps
                WHERE email = %s
                  AND purpose = 'signup'
                ORDER BY otp_id DESC LIMIT 1
                """,
                (email,)
            )
            prev = cur.fetchone()
            if prev and (datetime.now()-prev['created_at']).total_seconds()<60:
                return jsonify(error='Please wait one minute before requesting another code.'),429
            if found:
                cur.execute('UPDATE users SET full_name=%s,password_hash=%s WHERE user_id=%s',(name,generate_password_hash(password),found['id']))
            else:
                cur.execute("INSERT INTO users(full_name,email,password_hash,role,email_verified) VALUES(%s,%s,%s,'customer',0)",(name,email,generate_password_hash(password)))
            cur.execute(
                "DELETE FROM email_otps WHERE email=%s AND purpose='signup'",
                (email,)
            )
            cur.execute(
                """
                INSERT INTO email_otps
                    (email, otp_hash, purpose, expires_at, verified, attempts, created_at)
                VALUES (%s, %s, 'signup', %s, 0, 0, %s)
                """,
                (
                    email,
                    otp_hash(email, code),
                    datetime.now() + timedelta(minutes=10),
                    datetime.now()
                )
            )
        db.commit()

    try:
        send_email(email, code)
    except Exception:
        auth.logger.exception("Failed to send verification email")
        return jsonify(
            error="Unable to send verification email. Check Gmail SMTP settings, then retry after one minute."
        ), 503

    return jsonify(message='Verification code sent. Check your email.'),200

@auth.post('/api/auth/verify')
def verify():
    p=request.get_json(silent=True) or {}; email=str(p.get('email','')).strip().lower(); code=str(p.get('code','')).strip()
    if len(code)!=6 or not code.isdigit(): return jsonify(error='Enter the six-digit code.'),400
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM email_otps
                WHERE email = %s AND purpose = 'signup'
                ORDER BY otp_id DESC LIMIT 1
                FOR
                UPDATE
                """,
                (email,)
            );
            otp=cur.fetchone()
            if not otp or otp['expires_at']<datetime.now() or otp['attempts']>=5: return jsonify(error='Code expired or attempts exhausted. Request a new code.'),400
            cur.execute('UPDATE email_otps SET attempts=attempts+1 WHERE otp_id=%s',(otp['otp_id'],))
            if not secrets.compare_digest(otp['otp_hash'],otp_hash(email,code)):
                db.commit(); return jsonify(error='Incorrect code.'),400
            cur.execute('UPDATE users SET email_verified=1 WHERE email=%s AND role=%s',(email,'customer'))
            cur.execute(
                "DELETE FROM email_otps WHERE email=%s AND purpose='signup'",
                (email,)
            )
            cur.execute('SELECT user_id AS id FROM users WHERE email=%s',(email,)); user=cur.fetchone()
        db.commit()
    session.clear()
    session.permanent = False
    session['user_id'] = user['id']
    return jsonify(message='Email verified. Welcome to ParkVision!')

@auth.post('/api/auth/login')
def login():
    p=request.get_json(silent=True) or {}; email=str(p.get('email','')).strip().lower(); password=str(p.get('password',''))
    with connection() as db:
        with db.cursor() as cur:
            cur.execute('SELECT user_id AS id,password_hash,email_verified,is_active,role FROM users WHERE email=%s',(email,)); u=cur.fetchone()
    if not u or not check_password_hash(u['password_hash'],password): return jsonify(error='Incorrect email or password.'),401
    if not u['is_active']: return jsonify(error='Account disabled.'),403
    if not u['email_verified']: return jsonify(error='Verify your email before logging in.'),403
    if u['role'] not in ('customer', 'admin'):
        return jsonify(
            error='Invalid account role.'
        ), 403
    session.clear()
    session.permanent = False
    session['user_id'] = u['id']
    return jsonify(
        message='Login successful',
        redirect='/admin' if u['role'] == 'admin' else '/'
    )

@auth.post('/api/auth/logout')
def logout(): session.clear();return jsonify(message='Logged out.')
