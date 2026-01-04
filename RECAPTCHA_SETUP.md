# reCAPTCHA Setup Instructions

This application uses Google reCAPTCHA v2 to protect registration and login forms from automated abuse.

## Getting Your reCAPTCHA Keys

### Step 1: Register Your Site

1. Go to https://www.google.com/recaptcha/admin
2. Log in with your Google account
3. Click "+" to register a new site

### Step 2: Configure Your Site

- **Label**: Give your site a name (e.g., "Tejara Store Registration")
- **reCAPTCHA type**: Select "reCAPTCHA v2" → "I'm not a robot" Checkbox
- **Domains**: Add your domains:
  - For local development: `localhost`
  - For production: `yourdomain.com`
- Accept the reCAPTCHA Terms of Service
- Click "Submit"

### Step 3: Get Your Keys

After registration, you'll receive two keys:
- **Site Key** (public) - Used in your HTML
- **Secret Key** (private) - Used in your backend

### Step 4: Update Configuration

Open `config.py` and replace the test keys with your actual keys:

```python
# reCAPTCHA v2 Site Key (public - used in HTML)
RECAPTCHA_SITE_KEY = "your_actual_site_key_here"

# reCAPTCHA v2 Secret Key (private - used in backend)
RECAPTCHA_SECRET_KEY = "your_actual_secret_key_here"
```

## Testing with Test Keys

The application comes with Google's official test keys that **always pass validation**. These are useful for development but **MUST be replaced** for production use.

Test keys currently in `config.py`:
- Site Key: `6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI`
- Secret Key: `6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe`

## How It Works

### Registration Flow with CAPTCHA
1. User fills out registration form
2. User completes reCAPTCHA challenge
3. Form submits with CAPTCHA token
4. Backend verifies token with Google's API
5. If valid: proceed with registration
6. If invalid: show error message in Arabic

### Login Flow with CAPTCHA
1. User enters mobile number and store name
2. User completes reCAPTCHA challenge
3. Form submits with CAPTCHA token
4. Backend verifies token with Google's API
5. If valid: generate and send OTP
6. If invalid: show error message in Arabic

## Error Messages

The application shows these Arabic error messages:
- **CAPTCHA not completed**: "يرجى إكمال التحقق من أنك لست روبوت"
- **CAPTCHA verification failed**: Same message (user needs to try again)

## Arabic Language Support

The reCAPTCHA widget automatically displays in Arabic because we load it with the `hl=ar` parameter:

```html
<script src="https://www.google.com/recaptcha/api.js?hl=ar" async defer></script>
```

## Production Deployment

> [!WARNING]
> **Before deploying to production:**
> 1. Register your actual domain at https://www.google.com/recaptcha/admin
> 2. Replace test keys in `config.py` with your real keys
> 3. Consider using environment variables for keys (see `.env.example`)
> 4. Test thoroughly to ensure CAPTCHA is working correctly

## Troubleshooting

### CAPTCHA not showing
- Check browser console for JavaScript errors
- Ensure reCAPTCHA script is loaded in `base.html`
- Verify your domain is registered with Google

### CAPTCHA always fails
- Check that Secret Key is correct in `config.py`
- Ensure `requests` library is installed
- Check server logs for API errors

### CAPTCHA in wrong language
- Verify `?hl=ar` parameter in script URL
- Clear browser cache

## Additional Resources

- [reCAPTCHA Documentation](https://developers.google.com/recaptcha/docs/display)
- [reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin)
