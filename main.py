from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import random
import re
import requests
from datetime import datetime, timedelta

from database import init_db, get_db
from models import Store, OTPSession
from config import RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET_KEY, RECAPTCHA_VERIFY_URL, SESSION_SECRET_KEY

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

# Helper function to validate store name pattern
def validate_store_name(store_name: str) -> bool:
    # Only allow alphanumeric and hyphens, must start with letter or number
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$'
    return bool(re.match(pattern, store_name))

# Helper function to generate OTP
def generate_otp() -> str:
    return str(random.randint(100000, 999999))

# Helper function to verify reCAPTCHA v3
def verify_recaptcha(recaptcha_response: str, min_score: float = 0.5) -> bool:
    """Verify reCAPTCHA v3 response with Google's API
    
    Args:
        recaptcha_response: The token from the client
        min_score: Minimum score threshold (0.0 to 1.0). Default 0.5
                  0.0 = very likely a bot, 1.0 = very likely a human
    
    Returns:
        True if verification succeeds and score >= min_score
    """
    if not recaptcha_response:
        return False
    
    payload = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': recaptcha_response
    }
    
    try:
        response = requests.post(RECAPTCHA_VERIFY_URL, data=payload, timeout=5)
        result = response.json()
        
        # reCAPTCHA v3 returns a score between 0.0 and 1.0
        success = result.get('success', False)
        score = result.get('score', 0.0)
        
        print(f"reCAPTCHA verification: success={success}, score={score}")
        
        # For v3, check both success and score threshold
        return success and score >= min_score
    except Exception as e:
        print(f"reCAPTCHA verification error: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(
    request: Request,
    store_name: str = Form(...),
    owner_name: str = Form(...),
    mobile_number: str = Form(...),
    facebook_page: str = Form(...),
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
    # Validate store name
    if not validate_store_name(store_name):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "اسم المتجر يجب أن يحتوي على أحرف وأرقام وشرطات فقط"
            }
        )
    
    # Check if store name already exists
    existing_store = db.query(Store).filter(Store.store_name == store_name).first()
    if existing_store:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "اسم المتجر مستخدم بالفعل"
            }
        )
    
    # Check if mobile number already exists
    existing_mobile = db.query(Store).filter(Store.mobile_number == mobile_number).first()
    if existing_mobile:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "رقم الهاتف مستخدم بالفعل"
            }
        )
    
    # Create new store
    new_store = Store(
        store_name=store_name,
        owner_name=owner_name,
        mobile_number=mobile_number,
        facebook_page=facebook_page
    )
    db.add(new_store)
    db.commit()
    
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "success": "تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول"
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    mobile_number: str = Form(...),
    store_name: str = Form(...),
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
    # Check if store exists with this mobile number and store name
    store = db.query(Store).filter(
        Store.mobile_number == mobile_number,
        Store.store_name == store_name
    ).first()
    
    if not store:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "رقم الهاتف أو اسم المتجر غير صحيح"
            }
        )
    
    # Generate OTP
    otp_code = generate_otp()
    
    # Delete any existing OTP sessions for this mobile/store
    db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number,
        OTPSession.store_name == store_name
    ).delete()
    
    # Create new OTP session
    otp_session = OTPSession(
        mobile_number=mobile_number,
        store_name=store_name,
        otp_code=otp_code
    )
    db.add(otp_session)
    db.commit()
    
    # Store in session for verification page
    request.session["pending_mobile"] = mobile_number
    request.session["pending_store"] = store_name
    
    return RedirectResponse(url="/verify-otp", status_code=303)

@app.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_page(request: Request, db: Session = Depends(get_db)):
    mobile_number = request.session.get("pending_mobile")
    store_name = request.session.get("pending_store")
    
    if not mobile_number or not store_name:
        return RedirectResponse(url="/login")
    
    # Get the OTP for display (in production, this would be sent via SMS)
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number,
        OTPSession.store_name == store_name
    ).first()
    
    otp_code = otp_session.otp_code if otp_session else None
    
    return templates.TemplateResponse(
        "verify_otp.html",
        {
            "request": request,
            "otp_code": otp_code,  # For demo purposes only
            "mobile_number": mobile_number
        }
    )

@app.post("/verify-otp")
async def verify_otp(
    request: Request,
    otp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    mobile_number = request.session.get("pending_mobile")
    store_name = request.session.get("pending_store")
    
    if not mobile_number or not store_name:
        return RedirectResponse(url="/login")
    
    # Check OTP
    otp_session = db.query(OTPSession).filter(
        OTPSession.mobile_number == mobile_number,
        OTPSession.store_name == store_name,
        OTPSession.otp_code == otp_code
    ).first()
    
    if not otp_session:
        # Clear session and redirect to login
        request.session.clear()
        return RedirectResponse(url="/login?error=invalid_otp", status_code=303)
    
    # Mark as verified
    otp_session.verified = 1
    db.commit()
    
    # Set authenticated session
    request.session["authenticated"] = True
    request.session["mobile_number"] = mobile_number
    request.session["store_name"] = store_name
    
    # Clear pending session data
    request.session.pop("pending_mobile", None)
    request.session.pop("pending_store", None)
    
    return RedirectResponse(url="/profile", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    mobile_number = request.session.get("mobile_number")
    store_name = request.session.get("store_name")
    
    store = db.query(Store).filter(
        Store.mobile_number == mobile_number,
        Store.store_name == store_name
    ).first()
    
    if not store:
        request.session.clear()
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "store": store
        }
    )

@app.post("/profile")
async def update_profile(
    request: Request,
    facebook_page: str = Form(...),
    db: Session = Depends(get_db)
):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    
    mobile_number = request.session.get("mobile_number")
    store_name = request.session.get("store_name")
    
    store = db.query(Store).filter(
        Store.mobile_number == mobile_number,
        Store.store_name == store_name
    ).first()
    
    if not store:
        request.session.clear()
        return RedirectResponse(url="/login")
    
    # Update Facebook page
    store.facebook_page = facebook_page
    db.commit()
    
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "store": store,
            "success": "تم تحديث صفحة الفيسبوك بنجاح"
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

