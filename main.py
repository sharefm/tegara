from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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
from config import RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET_KEY, RECAPTCHA_VERIFY_URL, SESSION_SECRET_KEY, ENVIRONMENT

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

# Helper function to send SMS (placeholder for production)
def send_sms(mobile_number: str, message: str) -> bool:
    """Send SMS to mobile number"""
    if ENVIRONMENT == "production":
        print(f"[PRODUCTION] SMS would be sent to {mobile_number}: {message}")
        return True
    else:
        print(f"[DEVELOPMENT] SMS simulation to {mobile_number}: {message}")
        return True

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
    sms_message = f"رمز التحقق الخاص بك في تجارة: {otp_code}"
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
    success_message = "تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول" if registered else None
    
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
        db.delete(domain)
        db.commit()
    
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
    
    # Update domain
    domain.domain_name = new_domain_name
    domain.domain_type = domain_type
    domain.social_media_url = normalized_url
    db.commit()
    
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
