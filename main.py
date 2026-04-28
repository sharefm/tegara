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
    UPDATE_DOMAINS_API_KEY, NGINX_UPDATER_URL
)
from caddy_manager import setup_domain_files, remove_domain_files, reload_caddy

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
# UPDATE DOMAINS API ENDPOINT
# ============================================================================

@app.post("/update-domains")
async def update_domains(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    External API endpoint that triggers nginx configuration updates.
    Requires X-API-Key header for authentication.
    Calls the nginx updater service with current domain list.
    """
    # Get API key from header
    api_key = request.headers.get("X-API-Key")
    
    # Validate API key
    if not api_key or api_key != UPDATE_DOMAINS_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API key")
    
    try:
        # Get all active and trial domains
        domains = db.query(Domain).filter(
            Domain.subscription_status.in_(['active', 'trial'])
        ).all()
        
        # Build simple domain name list for nginx updater
        domain_names = [domain.domain_name for domain in domains]
        
        # Prepare payload for nginx updater service
        payload = {
            "domains": domain_names
        }
        
        # Call the nginx updater service
        response = requests.post(
            NGINX_UPDATER_URL,
            json=payload,
            timeout=30
        )
        
        # Return the response from nginx updater service
        if response.status_code == 200:
            return JSONResponse(
                status_code=200,
                content=response.json()
            )
        else:
            print(f"[ERROR] Nginx updater service returned status {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=502,
                detail=f"Nginx updater service error: {response.status_code}"
            )
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to connect to nginx updater service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Failed to connect to nginx updater service"
        )
    except Exception as e:
        print(f"[ERROR] Exception in /update-domains: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# ============================================================================
# REGISTRATION FLOW
# ============================================================================

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Redirect authenticated users to dashboard
    if request.session.get("authenticated"):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(
    request: Request,
    mobile_number: str = Form(...),
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
    password_hash = request.session.get("pending_password")
    
    if not mobile_number or not password_hash:
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
        password_hash=password_hash,
        verified=1
    )
    db.add(new_user)
    
    # Mark OTP as verified
    otp_session.verified = 1
    
    db.commit()
    
    # Clear pending session data
    request.session.pop("pending_mobile", None)
    request.session.pop("pending_password", None)
    
    # Redirect to login with success message
    return RedirectResponse(url="/login?registered=true", status_code=303)

# ============================================================================
# LOGIN FLOW
# ============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Redirect authenticated users to dashboard
    if request.session.get("authenticated"):
        return RedirectResponse(url="/dashboard")
    
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
    custom_store_name: str = Form(None),
    address: str = Form(None),
    email: str = Form(None),
    facebook_url: str = Form(None),
    instagram_url: str = Form(None),
    tiktok_url: str = Form(None),
    db: Session = Depends(get_db)
):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    user_id = request.session.get("user_id")
    
    # Normalize and validate social media URLs
    normalized_fb, normalized_ig, normalized_tt = None, None, None
    if facebook_url and facebook_url.strip():
        is_valid, normalized_fb = normalize_and_validate_url(facebook_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    if instagram_url and instagram_url.strip():
        is_valid, normalized_ig = normalize_and_validate_url(instagram_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    if tiktok_url and tiktok_url.strip():
        is_valid, normalized_tt = normalize_and_validate_url(tiktok_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    
    # Determine domain name based on type
    if domain_type == "custom":
        domain_name = custom_domain_input
        if not domain_name or not domain_name.strip():
            return RedirectResponse(url="/dashboard?error=empty_domain", status_code=303)
        domain_name = domain_name.strip().lower()
        if domain_name.startswith('www.'):
            domain_name = domain_name[4:]
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
        facebook_url=normalized_fb,
        instagram_url=normalized_ig,
        tiktok_url=normalized_tt,
        store_name=custom_store_name,
        email=email,
        address=address,
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
    
    # Setup Caddy hosting files
    user = db.query(User).filter(User.id == user_id).first()
    phone = user.mobile_number if user else ""
    final_store_name = custom_store_name
    
    setup_success = setup_domain_files(
        domain=domain_name,
        store_name=final_store_name,
        phone=phone,
        address=address or "",
        email=email or "",
        social_media=[normalized_fb, normalized_ig, normalized_tt]
    )
    
    if setup_success:
        reload_caddy()
    else:
        print(f"[ERROR] Failed to setup caddy files for {domain_name}")
    
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
        
        # Remove Caddy files and reload
        remove_success = remove_domain_files(domain.domain_name)
        if remove_success:
            reload_caddy()
        else:
            print(f"[ERROR] Failed to remove caddy files for {domain.domain_name}")
        
    
    return RedirectResponse(url="/dashboard?success=domain_deleted", status_code=303)

@app.post("/dashboard/edit-domain/{domain_id}")
async def edit_domain(
    domain_id: int,
    request: Request,
    domain_type: str = Form(...),
    custom_domain_input: str = Form(None),
    store_name: str = Form(None),
    custom_store_name: str = Form(None),
    address: str = Form(None),
    email: str = Form(None),
    facebook_url: str = Form(None),
    instagram_url: str = Form(None),
    tiktok_url: str = Form(None),
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
    
    # Normalize and validate social media URLs
    normalized_fb, normalized_ig, normalized_tt = None, None, None
    if facebook_url and facebook_url.strip():
        is_valid, normalized_fb = normalize_and_validate_url(facebook_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    if instagram_url and instagram_url.strip():
        is_valid, normalized_ig = normalize_and_validate_url(instagram_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    if tiktok_url and tiktok_url.strip():
        is_valid, normalized_tt = normalize_and_validate_url(tiktok_url)
        if not is_valid: return RedirectResponse(url="/dashboard?error=invalid_url", status_code=303)
    
    # Determine new domain name based on type
    if domain_type == "custom":
        new_domain_name = custom_domain_input
        if not new_domain_name or not new_domain_name.strip():
            return RedirectResponse(url="/dashboard?error=empty_domain", status_code=303)
        new_domain_name = new_domain_name.strip().lower()
        if new_domain_name.startswith('www.'):
            new_domain_name = new_domain_name[4:]
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
    domain.facebook_url = normalized_fb
    domain.instagram_url = normalized_ig
    domain.tiktok_url = normalized_tt
    domain.store_name = custom_store_name
    domain.email = email
    domain.address = address
    db.commit()
    
    # Handle Caddy files
    user = db.query(User).filter(User.id == user_id).first()
    phone = user.mobile_number if user else ""
    final_store_name = custom_store_name
    
    if new_domain_name != old_domain_name:
        remove_domain_files(old_domain_name)
    
    setup_success = setup_domain_files(
        domain=new_domain_name,
        store_name=final_store_name,
        phone=phone,
        address=address or "",
        email=email or "",
        social_media=[normalized_fb, normalized_ig, normalized_tt]
    )
    
    if setup_success:
        reload_caddy()
    else:
        print(f"[ERROR] Failed to update caddy files for {new_domain_name}")
    
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
    return RedirectResponse(url="/")

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "service": "tegara"}


# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

from config import ADMIN_PASSWORD
import math

def require_admin(request: Request):
    """Raise 302 redirect if not admin-authenticated."""
    if not request.session.get("admin_authenticated"):
        raise HTTPException(status_code=302, headers={"Location": "/edara/login"})

@app.get("/edara/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if request.session.get("admin_authenticated"):
        return RedirectResponse(url="/edara")
    return templates.TemplateResponse("admin/login.html", {"request": request})

@app.post("/edara/login")
async def admin_login(request: Request, password: str = Form(...)):
    if not ADMIN_PASSWORD:
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Admin access is disabled. Set ADMIN_PASSWORD environment variable."
        })
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Incorrect password."
        })
    request.session["admin_authenticated"] = True
    return RedirectResponse(url="/edara", status_code=303)

@app.get("/edara/logout")
async def admin_logout(request: Request):
    request.session.pop("admin_authenticated", None)
    return RedirectResponse(url="/edara/login")

@app.get("/edara", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    total_users    = db.query(User).count()
    verified_users = db.query(User).filter(User.verified == 1).count()
    total_domains  = db.query(Domain).count()
    active_domains  = db.query(Domain).filter(Domain.subscription_status == "active").count()
    trial_domains   = db.query(Domain).filter(Domain.subscription_status == "trial").count()
    expired_domains = db.query(Domain).filter(Domain.subscription_status == "expired").count()
    total_otp      = db.query(OTPSession).count()
    recent_users   = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    recent_domains = db.query(Domain).order_by(Domain.created_at.desc()).limit(5).all()
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "active_page": "dashboard",
        "total_users": total_users, "verified_users": verified_users,
        "total_domains": total_domains, "active_domains": active_domains,
        "trial_domains": trial_domains, "expired_domains": expired_domains,
        "total_otp": total_otp, "recent_users": recent_users, "recent_domains": recent_domains,
    })

# ---- USERS ----

PAGE_SIZE = 25

@app.get("/edara/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: Session = Depends(get_db),
                      page: int = 1, q: str = "", verified: str = ""):
    require_admin(request)
    query = db.query(User)
    if q:
        query = query.filter(User.mobile_number.ilike(f"%{q}%"))
    if verified in ("0", "1"):
        query = query.filter(User.verified == int(verified))
    total = query.count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    users = query.order_by(User.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "active_page": "users",
        "users": users, "total": total, "page": page, "total_pages": total_pages,
        "q": q, "verified_filter": verified,
    })

@app.get("/edara/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request, "active_page": "users", "user": user,
    })

@app.post("/edara/users/{user_id}")
async def admin_user_update(
    user_id: int, request: Request, db: Session = Depends(get_db),
    mobile_number: str = Form(...), verified: int = Form(...),
    password_reset_count: int = Form(...), new_password: str = Form("")
):
    require_admin(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Check uniqueness if mobile changed
    if mobile_number != user.mobile_number:
        existing = db.query(User).filter(User.mobile_number == mobile_number).first()
        if existing:
            return templates.TemplateResponse("admin/user_detail.html", {
                "request": request, "active_page": "users", "user": user,
                "flash_error": "Mobile number already in use by another user.",
            })
    user.mobile_number = mobile_number
    user.verified = verified
    user.password_reset_count = password_reset_count
    if new_password.strip():
        user.password_hash = hash_password(new_password.strip())
    db.commit()
    db.refresh(user)
    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request, "active_page": "users", "user": user,
        "flash_success": "User updated successfully.",
    })

@app.post("/edara/users/{user_id}/delete")
async def admin_user_delete(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return RedirectResponse(url="/edara/users?flash_success=User+deleted", status_code=303)

# ---- DOMAINS ----

@app.get("/edara/domains", response_class=HTMLResponse)
async def admin_domains(request: Request, db: Session = Depends(get_db),
                        page: int = 1, q: str = "", status: str = "", dtype: str = ""):
    require_admin(request)
    query = db.query(Domain)
    if q:
        query = query.filter(Domain.domain_name.ilike(f"%{q}%"))
    if status:
        query = query.filter(Domain.subscription_status == status)
    if dtype:
        query = query.filter(Domain.domain_type == dtype)
    total = query.count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    domains = query.order_by(Domain.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return templates.TemplateResponse("admin/domains.html", {
        "request": request, "active_page": "domains",
        "domains": domains, "total": total, "page": page, "total_pages": total_pages,
        "q": q, "status_filter": status, "dtype_filter": dtype,
    })

@app.get("/edara/domains/{domain_id}", response_class=HTMLResponse)
async def admin_domain_detail(domain_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return templates.TemplateResponse("admin/domain_detail.html", {
        "request": request, "active_page": "domains", "domain": domain,
    })

@app.post("/edara/domains/{domain_id}")
async def admin_domain_update(
    domain_id: int, request: Request, db: Session = Depends(get_db),
    domain_name: str = Form(...), domain_type: str = Form(...),
    subscription_status: str = Form(...), is_active: int = Form(...),
    facebook_url: str = Form(None), instagram_url: str = Form(None), tiktok_url: str = Form(None), 
    store_name: str = Form(""),
    expiry_date: str = Form("")
):
    require_admin(request)
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    domain.domain_name = domain_name
    domain.domain_type = domain_type
    domain.subscription_status = subscription_status
    domain.is_active = is_active
    domain.facebook_url = facebook_url
    domain.instagram_url = instagram_url
    domain.tiktok_url = tiktok_url
    domain.store_name = store_name or None
    domain.expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d") if expiry_date else None
    db.commit()
    db.refresh(domain)
    return templates.TemplateResponse("admin/domain_detail.html", {
        "request": request, "active_page": "domains", "domain": domain,
        "flash_success": "Domain updated successfully.",
    })

@app.post("/edara/domains/{domain_id}/delete")
async def admin_domain_delete(domain_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    db.delete(domain)
    db.commit()
    return RedirectResponse(url="/edara/domains?flash_success=Domain+deleted", status_code=303)

# ---- OTP SESSIONS ----

@app.get("/edara/otp-sessions", response_class=HTMLResponse)
async def admin_otp_sessions(request: Request, db: Session = Depends(get_db),
                             page: int = 1, q: str = ""):
    require_admin(request)
    query = db.query(OTPSession)
    if q:
        query = query.filter(OTPSession.mobile_number.ilike(f"%{q}%"))
    total = query.count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    sessions = query.order_by(OTPSession.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return templates.TemplateResponse("admin/otp_sessions.html", {
        "request": request, "active_page": "otp",
        "sessions": sessions, "total": total, "page": page, "total_pages": total_pages,
        "q": q,
    })

@app.post("/edara/otp-sessions/{session_id}/delete")
async def admin_otp_delete(session_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    session = db.query(OTPSession).filter(OTPSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="OTP session not found")
    db.delete(session)
    db.commit()
    return RedirectResponse(url="/edara/otp-sessions", status_code=303)


# ============================================================================
# CRON JOB ENDPOINT
# ============================================================================

from config import CRON_SECRET

@app.get("/cron")
async def cron_job(request: Request, db: Session = Depends(get_db)):
    """
    Periodic maintenance endpoint. Call via cron with the X-Cron-Secret header.
    Tasks:
      1. Mark domains as 'expired' when their expiry_date has passed
      2. Delete OTP sessions older than 24 hours
    """
    # Authenticate via header
    secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    now = datetime.utcnow()
    cutoff_otp = now - timedelta(hours=24)

    # 1. Expire domains past their expiry_date
    expired = (
        db.query(Domain)
        .filter(
            Domain.expiry_date != None,
            Domain.expiry_date < now,
            Domain.subscription_status != "expired"
        )
        .all()
    )
    expired_count = len(expired)
    for domain in expired:
        domain.subscription_status = "expired"
        domain.is_active = 0

    # 2. Delete OTP sessions older than 24 hours
    deleted_otp = (
        db.query(OTPSession)
        .filter(OTPSession.created_at < cutoff_otp)
        .delete(synchronize_session=False)
    )

    db.commit()

    print(f"[CRON] Expired {expired_count} domain(s). Deleted {deleted_otp} OTP session(s).")

    return {
        "status": "ok",
        "ran_at": now.isoformat(),
        "domains_expired": expired_count,
        "otp_sessions_deleted": deleted_otp,
    }
