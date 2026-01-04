# تجارة (Tejara) - Web Store Registration System

A modern web application for registering and managing web stores with Arabic interface, built with FastAPI and Jinja2.

## Features

- 🏪 **Store Registration** - Create web store accounts with custom subdomains
- 🔐 **OTP Authentication** - Secure login with 6-digit verification codes
- 👤 **Profile Management** - Update store information
- 🌐 **Arabic Interface** - Full RTL support with modern Arabic typography
- 🎨 **Premium Design** - Glassmorphism UI with smooth animations

## Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Run the Application

```bash
# Start the server
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Access the App

Open your browser and navigate to: **http://localhost:8000**

## Application Flow

1. **Register** - Create a new store account
   - Store name (e.g., `my-store` → `my-store.tejara.ps`)
   - Owner full name
   - Mobile number (10 digits)
   - Facebook page URL

2. **Login** - Enter mobile number and store name to receive OTP

3. **Verify OTP** - Enter the 6-digit code (displayed on screen for demo)

4. **Profile** - View store details and update Facebook page

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: Jinja2, HTML5, CSS3, JavaScript
- **Design**: Glassmorphism, RTL support, Google Fonts (Cairo)

## Project Structure

```
.
├── main.py              # FastAPI application
├── models.py            # Database models
├── database.py          # Database configuration
├── requirements.txt     # Python dependencies
├── templates/           # Jinja2 templates
│   ├── base.html
│   ├── register.html
│   ├── login.html
│   ├── verify_otp.html
│   └── profile.html
└── static/
    └── style.css        # Styling
```

## Notes

- OTP codes are displayed on screen for demo purposes
- In production, integrate with an SMS gateway (Twilio, Nexmo, etc.)
- All form fields are mandatory
- Store names must be alphanumeric with hyphens only

## License

This is a demo application for educational purposes.
