# Configuration for reCAPTCHA v3 and Application Settings
# Get your keys from: https://www.google.com/recaptcha/admin

import os
from pathlib import Path

# IMPORTANT: All sensitive values should be set via environment variables

# reCAPTCHA v3 Site Key (public - used in HTML)
RECAPTCHA_SITE_KEY = os.getenv(
    "RECAPTCHA_SITE_KEY",
    "6Let6z4sAAAAAPsuti-q9JOTLaYOdsVchMGoHvz7"  # Default for development
)

# reCAPTCHA v3 Secret Key (private - used in backend)
RECAPTCHA_SECRET_KEY = os.getenv(
    "RECAPTCHA_SECRET_KEY",
    "6Let6z4sAAAAANMtNTaaMgscktEdkZ5d4Kvd99gh"  # Default for development
)

# reCAPTCHA v3 uses score-based verification (0.0 to 1.0)
# Score threshold is set to 0.5 by default in main.py
# Higher score = more likely to be human

# reCAPTCHA Verification URL
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

# Session Secret Key
SESSION_SECRET_KEY = os.getenv(
    "SESSION_SECRET_KEY",
    "dev-secret-key-change-in-production"  # Default for development
)

# PostgreSQL Database URL - constructed from individual components
# This avoids shell-substitution issues in docker-compose environment blocks
_pg_user = os.getenv("POSTGRES_USER", "tejara_user")
_pg_password = os.getenv("POSTGRES_PASSWORD", "tejara_password")
_pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
_pg_port = os.getenv("POSTGRES_PORT", "5432")
_pg_db = os.getenv("POSTGRES_DB", "tejara_db")

DATABASE_URL = f"postgresql://{_pg_user}:{_pg_password}@{_pg_host}:{_pg_port}/{_pg_db}"


# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# SMS Configuration (Hadara SMS Service)
SMS_API_KEY = os.getenv(
    "SMS_API_KEY",
    "452E815F906B6BD877B6C5F294F244F4"  # Default API key
)

SMS_API_URL = os.getenv(
    "SMS_API_URL",
    "http://smsservice.hadara.ps:4545/SMS.ashx/bulkservice/sessionvalue/sendmessage/"
)

# Cloudflare DNS Configuration
CLOUDFLARE_API_TOKEN = os.getenv(
    "CLOUDFLARE_API_TOKEN",
    ""  # Must be set in production
)

CLOUDFLARE_ZONE_ID = os.getenv(
    "CLOUDFLARE_ZONE_ID",
    ""  # Zone ID for tejara.ps domain
)

CLOUDFLARE_TARGET_IP = os.getenv(
    "CLOUDFLARE_TARGET_IP",
    "37.27.245.226"  # IP address to point subdomains to
)

# Update Domains API Key
# Used to authenticate external requests to /update-domains endpoint
UPDATE_DOMAINS_API_KEY = os.getenv(
    "UPDATE_DOMAINS_API_KEY",
    "dev-update-domains-key-change-in-production"  # Default for development
)

# Nginx Updater Service URL
# External service that updates nginx configurations
NGINX_UPDATER_URL = os.getenv(
    "NGINX_UPDATER_URL",
    "http://localhost:8001/update-domains"  # Default for development
)

# Admin Dashboard
# Set ADMIN_PASSWORD env var to enable the admin interface. Empty = disabled.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Cron job secret — used to authenticate calls to /cron
CRON_SECRET = os.getenv("CRON_SECRET", "")
