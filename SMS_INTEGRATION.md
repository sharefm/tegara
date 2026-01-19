# SMS Integration Guide

This document explains how to integrate SMS functionality for OTP verification in production.

## Overview

The application currently has a placeholder `send_sms()` function in `main.py` that needs to be replaced with actual SMS provider integration for production use.

## Environment Behavior

| Environment | OTP Display | SMS Sending |
|-------------|-------------|-------------|
| **Development** | ✅ Shown on screen | ❌ Logged to console only |
| **Production** | ❌ Hidden | ✅ Should send actual SMS |

## SMS Provider Options

### 1. Twilio (Recommended for International)

**Installation:**
```bash
pip install twilio
```

**Configuration (add to `.env` or environment variables):**
```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890
```

**Implementation:**
```python
from twilio.rest import Client
import os

def send_sms(mobile_number: str, message: str) -> bool:
    if ENVIRONMENT == "production":
        try:
            client = Client(
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN")
            )
            client.messages.create(
                to=mobile_number,
                from_=os.getenv("TWILIO_FROM_NUMBER"),
                body=message
            )
            print(f"SMS sent successfully to {mobile_number}")
            return True
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
    else:
        print(f"[DEVELOPMENT] SMS simulation to {mobile_number}: {message}")
        return True
```

---

### 2. AWS SNS (Amazon Web Services)

**Installation:**
```bash
pip install boto3
```

**Configuration:**
```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
```

**Implementation:**
```python
import boto3
import os

def send_sms(mobile_number: str, message: str) -> bool:
    if ENVIRONMENT == "production":
        try:
            sns_client = boto3.client(
                'sns',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
            sns_client.publish(
                PhoneNumber=mobile_number,
                Message=message
            )
            print(f"SMS sent successfully to {mobile_number}")
            return True
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
    else:
        print(f"[DEVELOPMENT] SMS simulation to {mobile_number}: {message}")
        return True
```

---

### 3. Local Palestinian SMS Gateway

For local Palestinian SMS providers, you'll need to:

1. Contact your SMS provider for API documentation
2. Get API credentials (API key, sender ID, etc.)
3. Implement according to their API specifications

**Generic HTTP API Example:**
```python
import requests
import os

def send_sms(mobile_number: str, message: str) -> bool:
    if ENVIRONMENT == "production":
        try:
            response = requests.post(
                os.getenv("SMS_GATEWAY_URL"),
                json={
                    "api_key": os.getenv("SMS_API_KEY"),
                    "sender": os.getenv("SMS_SENDER_ID"),
                    "recipient": mobile_number,
                    "message": message
                },
                timeout=10
            )
            if response.status_code == 200:
                print(f"SMS sent successfully to {mobile_number}")
                return True
            else:
                print(f"SMS sending failed: {response.text}")
                return False
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False
    else:
        print(f"[DEVELOPMENT] SMS simulation to {mobile_number}: {message}")
        return True
```

---

## Implementation Steps

1. **Choose your SMS provider** from the options above

2. **Install required package:**
   ```bash
   pip install <provider-package>
   pip freeze > requirements.txt
   ```

3. **Add credentials to environment variables:**
   - Update `.env.dev` for development testing
   - Set production environment variables in your deployment platform

4. **Replace the `send_sms()` function** in `main.py` (lines 42-67) with your provider's implementation

5. **Test in development:**
   ```bash
   # The function will log to console instead of sending actual SMS
   docker-compose -f docker-compose.dev.yml up
   ```

6. **Test in production mode locally:**
   ```bash
   # Set environment to production temporarily
   export ENVIRONMENT=production
   # Run and verify SMS is sent (not displayed)
   ```

7. **Deploy to production** with proper environment variables set

## Phone Number Format

Ensure mobile numbers are in international format:
- **Format:** `+970599123456` (for Palestinian numbers)
- **Validation:** Add validation in the registration/login forms if needed

## Error Handling

Consider adding retry logic and error notifications:

```python
def send_sms(mobile_number: str, message: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            # SMS sending code here
            return True
        except Exception as e:
            print(f"SMS attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Log to error tracking service
                return False
    return False
```

## Cost Considerations

- **Twilio:** ~$0.0075 per SMS for Palestinian numbers
- **AWS SNS:** ~$0.00645 per SMS
- **Local providers:** Varies, often cheaper for local numbers

## Security Best Practices

1. ✅ Never commit API credentials to git
2. ✅ Use environment variables for all secrets
3. ✅ Implement rate limiting to prevent SMS abuse
4. ✅ Add CAPTCHA (already implemented with reCAPTCHA v3)
5. ✅ Log all SMS attempts for monitoring

## Support

For issues with specific SMS providers:
- **Twilio:** https://www.twilio.com/docs/sms
- **AWS SNS:** https://docs.aws.amazon.com/sns/
- **Local providers:** Contact your provider's support team
