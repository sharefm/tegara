# Configuration for reCAPTCHA v3
# Get your keys from: https://www.google.com/recaptcha/admin

# IMPORTANT: Replace with your actual keys for production use

# reCAPTCHA v3 Site Key (public - used in HTML)
RECAPTCHA_SITE_KEY = "6Let6z4sAAAAAPsuti-q9JOTLaYOdsVchMGoHvz7"  # site key from Google

# reCAPTCHA v3 Secret Key (private - used in backend)
RECAPTCHA_SECRET_KEY = "6Let6z4sAAAAANMtNTaaMgscktEdkZ5d4Kvd99gh"  # secret key from Google

# reCAPTCHA v3 uses score-based verification (0.0 to 1.0)
# Score threshold is set to 0.5 by default in main.py
# Higher score = more likely to be human

# reCAPTCHA Verification URL
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
