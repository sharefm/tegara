from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import random
import re
import requests
from datetime import datetime, timedelta

from database import init_db, get_db
from models import User, Domain, OTPSession
from config import (
    RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET_KEY, RECAPTCHA_VERIFY_URL, 
    SESSION_SECRET_KEY, ENVIRONMENT, SMS_API_KEY, SMS_API_URL,
    CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID, CLOUDFLARE_TARGET_IP,
    API_KEY, DOMAIN_SYNC_WEBHOOK_URL, DOMAIN_SYNC_WEBHOOK_SECRET
)

app = FastAPI()

# Add session middleware with secret from config
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add reCAPTCHA site key to template context
templates.env.globals['RECAPTCHA_SITE_KEY'] = RECAPTCHA_SITE_KEY

# Initialize database
init_db()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Convert password to bytes and hash
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

# Helper function to validate domain name pattern (DNS record)
def validate_domain_name(domain_name: str) -> bool:
    """Validate domain name as a valid DNS record (English alphanumeric and hyphens only)"""
    # Must be 1-63 characters
    if not domain_name or len(domain_name) > 63:
        return False
    # Must start and end with alphanumeric, can contain hyphens in between
    # Only English letters and numbers allowed (no Arabic or other characters)
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$'
    return bool(re.match(pattern, domain_name))

# Helper function to normalize and validate URL
def normalize_and_validate_url(url: str) -> tuple[bool, str]:
    """
    Normalize and validate URL. Automatically adds https:// if protocol is missing.
    Returns: (is_valid, normalized_url)
    """
    if not url or not url.strip():
        return False, ""
    
    url = url.strip()
    
    # If URL doesn't start with http:// or https://, add https://
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # URL pattern that checks for http/https protocol and valid domain structure
    url_pattern = r'^https?://[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*(/.*)?$'
    is_valid = bool(re.match(url_pattern, url))
    
    return is_valid, url if is_valid else ""

# Helper function to generate OTP
def generate_otp() -> str:
    return str(random.randint(100000, 999999))

# Helper function to send SMS
def send_sms(mobile_number: str, message: str) -> bool:
    """Send SMS to mobile number using Hadara SMS service"""
    if ENVIRONMENT == "production":
        try:
            # Prepare the API request
            params = {
                'apikey': SMS_API_KEY,
                'to': mobile_number,
                'msg': message
            }
            
            # Send the SMS via Hadara API
            response = requests.get(SMS_API_URL, params=params, timeout=10)
            
            # Check if request was successful
            if response.status_code == 200:
                print(f"[PRODUCTION] SMS sent successfully to {mobile_number}")
                return True
            else:
                print(f"[PRODUCTION] SMS failed to {mobile_number}. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"[PRODUCTION] SMS error to {mobile_number}: {e}")
            return False
    else:
        # Development mode - just log the message
        print(f"[DEVELOPMENT] SMS simulation to {mobile_number}: {message}")
        return True

# Helper function to create DNS record in Cloudflare
def create_dns_record(subdomain: str) -> bool:
    """
    Create an A record in Cloudflare for a tejara.ps subdomain
    subdomain should be like 'my-store' (without .tejara.ps)
    """
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ZONE_ID:
        print(f"[WARNING] Cloudflare credentials not configured. Skipping DNS record creation for {subdomain}.tejara.ps")
        return False
    
    try:
        # Cloudflare API endpoint for DNS records
        url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
        
        # Headers with API token
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # DNS record data
        data = {
            "type": "A",
            "name": subdomain,  # Just the subdomain part (e.g., 'my-store')
            "content": CLOUDFLARE_TARGET_IP,
            "ttl": 1,  # Auto TTL
            "proxied": False  # Set to True if you want Cloudflare proxy
        }
        
        # Create the DNS record
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"[SUCCESS] DNS A record created: {subdomain}.tejara.ps -> {CLOUDFLARE_TARGET_IP}")
                return True
            else:
                errors = result.get("errors", [])
                print(f"[ERROR] Cloudflare API error for {subdomain}.tejara.ps: {errors}")
                return False
        else:
            print(f"[ERROR] Cloudflare API request failed for {subdomain}.tejara.ps. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception creating DNS record for {subdomain}.tejara.ps: {e}")
        return False

# Helper function to delete DNS record from Cloudflare
def delete_dns_record(subdomain: str) -> bool:
    """
    Delete an A record from Cloudflare for a tejara.ps subdomain
    subdomain should be like 'my-store' (without .tejara.ps)
    """
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ZONE_ID:
        print(f"[WARNING] Cloudflare credentials not configured. Skipping DNS record deletion for {subdomain}.tejara.ps")
        return False
    
    try:
        # First, find the DNS record ID
        list_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Search for the record by name
        params = {
            "type": "A",
            "name": f"{subdomain}.tejara.ps"
        }
        
        response = requests.get(list_url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result"):
                # Get the first matching record
                record = result["result"][0]
                record_id = record["id"]
                
                # Delete the record
                delete_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}"
                delete_response = requests.delete(delete_url, headers=headers, timeout=10)
                
                if delete_response.status_code == 200:
                    delete_result = delete_response.json()
                    if delete_result.get("success"):
                        print(f"[SUCCESS] DNS A record deleted: {subdomain}.tejara.ps")
                        return True
                    else:
                        errors = delete_result.get("errors", [])
                        print(f"[ERROR] Cloudflare API error deleting {subdomain}.tejara.ps: {errors}")
                        return False
                else:
                    print(f"[ERROR] Failed to delete DNS record for {subdomain}.tejara.ps. Status: {delete_response.status_code}")
                    return False
            else:
                print(f"[WARNING] DNS record not found for {subdomain}.tejara.ps, nothing to delete")
                return True  # Not an error if record doesn't exist
        else:
            print(f"[ERROR] Failed to list DNS records for {subdomain}.tejara.ps. Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception deleting DNS record for {subdomain}.tejara.ps: {e}")
        return False

# Helper function to sync domains to external webhook
def sync_domains_to_webhook(db: Session) -> bool:
    """
    Send list of active and trial domains to configured webhook URL
    Only sends domains with subscription_status 'active' or 'trial'
    """
    if not DOMAIN_SYNC_WEBHOOK_URL:
        print("[INFO] Domain sync webhook URL not configured, skipping sync")
        return False
    
    try:
        # Get all active and trial domains
        domains = db.query(Domain).filter(
            Domain.subscription_status.in_(['active', 'trial'])
        ).all()
        
        # Build domain list
        domain_list = []
        for domain in domains:
            domain_list.append({
                "domain_name": domain.domain_name,
                "subscription_status": domain.subscription_status,
                "social_media_url": domain.social_media_url,
                "is_active": domain.is_active == 1
            })
        
        # Prepare payload
        payload = {
            "domains": domain_list
        }
        
        # Prepare headers with authentication
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add webhook secret if configured
        if DOMAIN_SYNC_WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = DOMAIN_SYNC_WEBHOOK_SECRET
        
        # Send to webhook
        response = requests.post(
            DOMAIN_SYNC_WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201, 204]:
            print(f"[SUCCESS] Synced {len(domain_list)} domains to webhook")
            return True
        else:
            print(f"[ERROR] Webhook sync failed. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception syncing domains to webhook: {e}")
        return False

# Helper function to verify reCAPTCHA v3
def verify_recaptcha(recaptcha_response: str, min_score: float = 0.5) -> bool:
    """Verify reCAPTCHA v3 response with Google's API"""
    # In development mode, bypass reCAPTCHA verification
    if ENVIRONMENT == "development":
        print(f"[DEVELOPMENT] reCAPTCHA verification bypassed")
        return True
    
    if not recaptcha_response:
        return False
    
    payload = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': recaptcha_response
    }
    
    try:
        response = requests.post(RECAPTCHA_VERIFY_URL, data=payload, timeout=5)
        result = response.json()
        
        success = result.get('success', False)
        score = result.get('score', 0.0)
        
        print(f"reCAPTCHA verification: success={success}, score={score}")
        
        return success and score >= min_score
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False

# Helper function to verify API key
async def verify_api_key(request: Request):
    """Verify API key from request header"""
    api_key = request.headers.get("X-API-Key")
    
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )
    
    if not api_key or api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    return True

# ============================================================================
# ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Redirect authenticated users to dashboard
    if request.session.get("authenticated"):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("landing.html", {"request": request})

# ============================================================================
# REGISTRATION FLOW
# ============================================================================

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(
    request: Request,
    mobile_number: str = Form(...),
    business_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    g_recaptcha_response: str = Form(None, alias="g-recaptcha-response")
):
    # Verify reCAPTCHA
    if not verify_recaptcha(g_recaptcha_response):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "يرجى إكمال التحقق من أنك لست روبوت"
            }
        )
    
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "كلمات المرور غير متطابقة"
            }
        )
    
    # Validate password length
    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
            }
        )
    
    if len(password) > 60:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن لا تتجاوز 60 حرف"
            }
        )
    
    # Validate password contains only allowed characters
    password_pattern = r'^[A-Za-z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$'
    if not re.match(password_pattern, password):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن تحتوي على أحرف إنجليزية وأرقام ورموز فقط"
            }
        )
    
    # Check if mobile number already exists
    existing_user = db.query(User).filter(User.mobile_number == mobile_number).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "رقم الهاتف مستخدم بالفعل"
            }
        )
    
    # Generate OTP
    otp_code = generate_otp()
    
    # Delete any existing OTP sessions for this mobile
    db.query(OTPSession).filter(OTPSession.mobile_number == mobile_number).delete()
    
    # Create new OTP session
    otp_session = OTPSession(
        mobile_number=mobile_number,
        otp_code=otp_code
    )
    db.add(otp_session)
    db.commit()
    
    # Send OTP via SMS
    sms_message = f"رمز التحقق الخاص بك في في بوابة التجارة الالكترونية tejara.ps: {otp_code}"
    send_sms(mobile_number, sms_message)
    
    # Store registration data in session
    request.session["pending_mobile"] = mobile_number
    request.session["pending_business_name"] = business_name
    request.session["pending_password"] = hash_password(password)
    
    return RedirectResponse(url="/verify-sms", status_code=303)

@app.get("/verify-sms", response_class=HTMLResponse)
async def verify_sms_page(request: Request, db: Session = Depends(get_db)):
    mobile_number = request.session.get("pending_mobile")
    
    if not mobile_number:
        return RedirectResponse(url="/register")
    
    # Get the OTP session
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number
    ).first()
    
    # Only show OTP on screen in development mode
    otp_code = None
    if ENVIRONMENT == "development" and otp_session:
        otp_code = otp_session.otp_code
    
    return templates.TemplateResponse(
        "verify_sms.html",
        {
            "request": request,
            "otp_code": otp_code,
            "mobile_number": mobile_number,
            "is_production": ENVIRONMENT == "production"
        }
    )

@app.post("/verify-sms")
async def verify_sms(
    request: Request,
    otp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    mobile_number = request.session.get("pending_mobile")
    business_name = request.session.get("pending_business_name")
    password_hash = request.session.get("pending_password")
    
    if not mobile_number or not business_name or not password_hash:
        return RedirectResponse(url="/register")
    
    # Check OTP
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number,
        OTPSession.otp_code == otp_code
    ).first()
    
    if not otp_session:
        return templates.TemplateResponse(
            "verify_sms.html",
            {
                "request": request,
                "error": "رمز التحقق غير صحيح",
                "mobile_number": mobile_number,
                "is_production": ENVIRONMENT == "production"
            }
        )
    
    # Create user account
    new_user = User(
        mobile_number=mobile_number,
        business_name=business_name,
        password_hash=password_hash,
        verified=1
    )
    db.add(new_user)
    
    # Mark OTP as verified
    otp_session.verified = 1
    
    db.commit()
    
    # Clear pending session data
    request.session.pop("pending_mobile", None)
    request.session.pop("pending_business_name", None)
    request.session.pop("pending_password", None)
    
    # Redirect to login with success message
    return RedirectResponse(url="/login?registered=true", status_code=303)

# ============================================================================
# LOGIN FLOW
# ============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    registered = request.query_params.get("registered")
    password_reset = request.query_params.get("password_reset")
    
    success_message = None
    if registered:
        success_message = "تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول"
    elif password_reset:
        success_message = "تم تغيير كلمة المرور بنجاح! يمكنك الآن تسجيل الدخول"
    
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "success": success_message
        }
    )

@app.post("/login")
async def login(
    request: Request,
    mobile_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    g_recaptcha_response: str = Form(None, alias="g-recaptcha-response")
):
    # Verify reCAPTCHA
    if not verify_recaptcha(g_recaptcha_response):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "يرجى إكمال التحقق من أنك لست روبوت"
            }
        )
    
    # Check if user exists
    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "رقم الهاتف أو كلمة المرور غير صحيحة"
            }
        )
    
    # Set authenticated session
    request.session["authenticated"] = True
    request.session["user_id"] = user.id
    request.session["mobile_number"] = user.mobile_number
    
    return RedirectResponse(url="/dashboard", status_code=303)

# ============================================================================
# PASSWORD RESET FLOW
# ============================================================================

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.post("/forgot-password")
async def forgot_password(
    request: Request,
    mobile_number: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if user exists
    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    
    if not user:
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error": "رقم الهاتف غير مسجل"
            }
        )
    
    # Check if user has exceeded reset limit (5 attempts)
    if user.password_reset_count >= 5:
        return RedirectResponse(url="/reset-password-blocked", status_code=303)
    
    # Generate OTP
    otp_code = generate_otp()
    
    # Delete any existing OTP sessions for this mobile
    db.query(OTPSession).filter(OTPSession.mobile_number == mobile_number).delete()
    
    # Create new OTP session
    otp_session = OTPSession(
        mobile_number=mobile_number,
        otp_code=otp_code
    )
    db.add(otp_session)
    db.commit()
    
    # Send OTP via SMS
    sms_message = f"رمز إعادة تعيين كلمة المرور في بوابة التجارة الالكترونية tejara.ps: {otp_code}"
    send_sms(mobile_number, sms_message)
    
    # Store mobile in session for verification
    request.session["reset_mobile"] = mobile_number
    
    return RedirectResponse(url="/reset-password-verify", status_code=303)

@app.get("/reset-password-verify", response_class=HTMLResponse)
async def reset_password_verify_page(request: Request, db: Session = Depends(get_db)):
    mobile_number = request.session.get("reset_mobile")
    
    if not mobile_number:
        return RedirectResponse(url="/forgot-password")
    
    # Get the OTP session
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number
    ).first()
    
    # Only show OTP on screen in development mode
    otp_code = None
    if ENVIRONMENT == "development" and otp_session:
        otp_code = otp_session.otp_code
    
    return templates.TemplateResponse(
        "reset_password_verify.html",
        {
            "request": request,
            "otp_code": otp_code,
            "mobile_number": mobile_number
        }
    )

@app.post("/reset-password-verify")
async def reset_password_verify(
    request: Request,
    otp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    mobile_number = request.session.get("reset_mobile")
    
    if not mobile_number:
        return RedirectResponse(url="/forgot-password")
    
    # Check OTP
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number,
        OTPSession.otp_code == otp_code
    ).first()
    
    if not otp_session:
        return templates.TemplateResponse(
            "reset_password_verify.html",
            {
                "request": request,
                "error": "رمز التحقق غير صحيح",
                "mobile_number": mobile_number
            }
        )
    
    # Mark OTP as verified
    otp_session.verified = 1
    db.commit()
    
    # Set session flag that OTP is verified
    request.session["reset_verified"] = True
    
    return RedirectResponse(url="/reset-password-new", status_code=303)

@app.get("/reset-password-new", response_class=HTMLResponse)
async def reset_password_new_page(request: Request):
    # Check if user has verified OTP
    if not request.session.get("reset_verified"):
        return RedirectResponse(url="/forgot-password")
    
    return templates.TemplateResponse("reset_password_new.html", {"request": request})

@app.post("/reset-password-new")
async def reset_password_new(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if user has verified OTP
    if not request.session.get("reset_verified"):
        return RedirectResponse(url="/forgot-password")
    
    mobile_number = request.session.get("reset_mobile")
    
    if not mobile_number:
        return RedirectResponse(url="/forgot-password")
    
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "reset_password_new.html",
            {
                "request": request,
                "error": "كلمات المرور غير متطابقة"
            }
        )
    
    # Validate password length
    if len(password) < 8:
        return templates.TemplateResponse(
            "reset_password_new.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
            }
        )
    
    if len(password) > 60:
        return templates.TemplateResponse(
            "reset_password_new.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن لا تتجاوز 60 حرف"
            }
        )
    
    # Validate password contains only allowed characters
    password_pattern = r'^[A-Za-z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]+$'
    if not re.match(password_pattern, password):
        return templates.TemplateResponse(
            "reset_password_new.html",
            {
                "request": request,
                "error": "كلمة المرور يجب أن تحتوي على أحرف إنجليزية وأرقام ورموز فقط"
            }
        )
    
    # Get user and update password
    user = db.query(User).filter(User.mobile_number == mobile_number).first()
    
    if not user:
        return RedirectResponse(url="/forgot-password")
    
    # Update password and increment reset count
    user.password_hash = hash_password(password)
    user.password_reset_count += 1
    db.commit()
    
    # Clear session
    request.session.pop("reset_mobile", None)
    request.session.pop("reset_verified", None)
    
    # Redirect to login with success message
    return RedirectResponse(url="/login?password_reset=true", status_code=303)

@app.get("/reset-password-blocked", response_class=HTMLResponse)
async def reset_password_blocked_page(request: Request):
    return templates.TemplateResponse("reset_password_blocked.html", {"request": request})

# ============================================================================
# DASHBOARD
# ============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login")
    
    # Get user's domains
    domains = db.query(Domain).filter(Domain.user_id == user_id).all()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "domains": domains,
            "datetime": datetime,
            "timedelta": timedelta
        }
    )

@app.post("/dashboard/add-domain")
async def add_domain(
    request: Request,
    domain_type: str = Form(...),
    custom_domain_input: str = Form(None),
    store_name: str = Form(None),
    social_media_url: str = Form(...),
    db: Session = Depends(get_db)
):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    
    # Normalize and validate social media URL
    is_valid_url, normalized_url = normalize_and_validate_url(social_media_url)
    if not is_valid_url:
        return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    
    # Determine domain name based on type
    if domain_type == "custom":
        domain_name = custom_domain_input
        if not domain_name or not domain_name.strip():
            return RedirectResponse(url="/dashboard?error=empty_domain", status_code=303)
    else:  # temporary
        if not store_name or not validate_domain_name(store_name):
            return RedirectResponse(url="/dashboard?error=invalid_store_name", status_code=303)
        domain_name = f"{store_name}.tejara.ps"
    
    # Check if domain already exists
    existing_domain = db.query(Domain).filter(Domain.domain_name == domain_name).first()
    if existing_domain:
        return RedirectResponse(url="/dashboard?error=domain_exists", status_code=303)
    
    # Create new domain with expiry date (7 days from now) and trial status
    expiry_date = datetime.utcnow() + timedelta(days=7)
    new_domain = Domain(
        user_id=user_id,
        domain_name=domain_name,
        domain_type=domain_type,
        social_media_url=normalized_url,
        subscription_status='trial',
        expiry_date=expiry_date
    )
    db.add(new_domain)
    db.commit()
    
    # If it's a temporary domain (tejara.ps subdomain), create DNS record in Cloudflare
    if domain_type == "temporary":
        # Extract subdomain (e.g., 'my-store' from 'my-store.tejara.ps')
        subdomain = store_name
        create_dns_record(subdomain)
        # Note: We don't fail the domain creation if DNS fails
        # The domain is still created in our database
    
    # Sync domains to webhook
    sync_domains_to_webhook(db)
    
    return RedirectResponse(url="/dashboard?success=domain_added", status_code=303)

@app.post("/dashboard/delete-domain/{domain_id}")
async def delete_domain(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    
    # Find domain and verify ownership
    domain = db.query(Domain).filter(
        Domain.id == domain_id,
        Domain.user_id == user_id
    ).first()
    
    if domain:
        # Delete DNS record if it's a temporary domain
        if domain.domain_type == "temporary" and domain.domain_name.endswith(".tejara.ps"):
            subdomain = domain.domain_name.replace(".tejara.ps", "")
            delete_dns_record(subdomain)
        
        # Delete domain from database
        db.delete(domain)
        db.commit()
        
        # Sync domains to webhook
        sync_domains_to_webhook(db)
    
    return RedirectResponse(url="/dashboard?success=domain_deleted", status_code=303)

@app.post("/dashboard/edit-domain/{domain_id}")
async def edit_domain(
    domain_id: int,
    request: Request,
    domain_type: str = Form(...),
    custom_domain_input: str = Form(None),
    store_name: str = Form(None),
    social_media_url: str = Form(...),
    db: Session = Depends(get_db)
):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    
    # Find domain and verify ownership
    domain = db.query(Domain).filter(
        Domain.id == domain_id,
        Domain.user_id == user_id
    ).first()
    
    if not domain:
        return RedirectResponse(url="/dashboard?error=domain_not_found", status_code=303)
    
    # Normalize and validate social media URL
    is_valid_url, normalized_url = normalize_and_validate_url(social_media_url)
    if not is_valid_url:
        return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    
    # Determine new domain name based on type
    if domain_type == "custom":
        new_domain_name = custom_domain_input
        if not new_domain_name or not new_domain_name.strip():
            return RedirectResponse(url="/dashboard?error=empty_domain", status_code=303)
    else:  # temporary
        if not store_name or not validate_domain_name(store_name):
            return RedirectResponse(url="/dashboard?error=invalid_store_name", status_code=303)
        new_domain_name = f"{store_name}.tejara.ps"
    
    # Check if new domain name conflicts with existing domains (excluding current domain)
    if new_domain_name != domain.domain_name:
        existing_domain = db.query(Domain).filter(
            Domain.domain_name == new_domain_name,
            Domain.id != domain_id
        ).first()
        if existing_domain:
            return RedirectResponse(url="/dashboard?error=domain_exists", status_code=303)
    
    # Handle DNS record changes for temporary domains
    old_domain_name = domain.domain_name
    old_domain_type = domain.domain_type
    
    # If domain name or type is changing, handle DNS updates
    if new_domain_name != old_domain_name or domain_type != old_domain_type:
        # Delete old DNS record if it was a temporary domain
        if old_domain_type == "temporary" and old_domain_name.endswith(".tejara.ps"):
            old_subdomain = old_domain_name.replace(".tejara.ps", "")
            delete_dns_record(old_subdomain)
        
        # Create new DNS record if it's a temporary domain
        if domain_type == "temporary":
            new_subdomain = store_name
            create_dns_record(new_subdomain)
    
    # Update domain in database
    domain.domain_name = new_domain_name
    domain.domain_type = domain_type
    domain.social_media_url = normalized_url
    db.commit()
    
    # Sync domains to webhook
    sync_domains_to_webhook(db)
    
    return RedirectResponse(url="/dashboard?success=domain_updated", status_code=303)

@app.get("/subscribe/{domain_id}", response_class=HTMLResponse)
async def subscribe_page(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # Verify authentication
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    
    # Get domain and verify ownership
    domain = db.query(Domain).filter(
        Domain.id == domain_id,
        Domain.user_id == user_id
    ).first()
    
    if not domain:
        return RedirectResponse(url="/dashboard?error=domain_not_found", status_code=303)
    
    return templates.TemplateResponse(
        "subscribe.html",
        {
            "request": request,
            "domain": domain
        }
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "service": "tegara"}
