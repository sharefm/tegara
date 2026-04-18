# SSL Certificate Setup for Nginx

This guide explains how to set up SSL certificates for the nginx reverse proxy.

## Overview

The nginx container is configured to:
- Redirect all HTTP (port 80) traffic to HTTPS (port 443)
- Act as a reverse proxy to the Tegara application
- Serve traffic over SSL/TLS

## SSL Certificate Location

SSL certificates should be placed in the `ssl/` folder:
```
ssl/
├── cert.pem    # SSL certificate
└── key.pem     # Private key
```

> [!IMPORTANT]
> The `ssl/` folder is in `.gitignore` and should **never** be committed to version control.

## Option 1: Self-Signed Certificate (Development/Testing)

For development or testing purposes, you can create a self-signed certificate:

```bash
# Create ssl directory
mkdir -p ssl

# Generate self-signed certificate (valid for 365 days)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

> [!WARNING]
> Self-signed certificates will show a browser warning. They are **not suitable for production**.

## Option 2: Let's Encrypt (Production)

For production, use Let's Encrypt to get free, trusted SSL certificates.

### Prerequisites
- A registered domain name pointing to your server
- Ports 80 and 443 accessible from the internet

### Using Certbot

1. **Install Certbot:**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install certbot
   ```

2. **Stop nginx temporarily:**
   ```bash
   docker-compose -f docker-compose.prod.yml stop nginx
   ```

3. **Generate certificate:**
   ```bash
   sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
   ```

4. **Copy certificates to ssl folder:**
   ```bash
   mkdir -p ssl
   sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
   sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
   sudo chown $USER:$USER ssl/*.pem
   ```

5. **Start nginx:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Automatic Renewal

Let's Encrypt certificates expire after 90 days. Set up automatic renewal:

1. **Create renewal script** (`renew-ssl.sh`):
   ```bash
   #!/bin/bash
   docker-compose -f docker-compose.prod.yml stop nginx
   certbot renew
   cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
   cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Make it executable:**
   ```bash
   chmod +x renew-ssl.sh
   ```

3. **Add to crontab** (runs monthly):
   ```bash
   crontab -e
   # Add this line:
   0 0 1 * * /path/to/renew-ssl.sh
   ```

## Option 3: Commercial SSL Certificate

If you have a commercial SSL certificate:

1. **Create ssl directory:**
   ```bash
   mkdir -p ssl
   ```

2. **Copy your certificate files:**
   ```bash
   cp /path/to/your/certificate.crt ssl/cert.pem
   cp /path/to/your/private.key ssl/key.pem
   ```

3. **Set proper permissions:**
   ```bash
   chmod 600 ssl/key.pem
   chmod 644 ssl/cert.pem
   ```

## Updating nginx.conf

The default `nginx.conf` is configured to use:
- Certificate: `/etc/nginx/ssl/cert.pem`
- Private key: `/etc/nginx/ssl/key.pem`

If your certificate files have different names, update `nginx.conf`:

```nginx
ssl_certificate /etc/nginx/ssl/your-cert-name.pem;
ssl_certificate_key /etc/nginx/ssl/your-key-name.pem;
```

## Verifying SSL Setup

After starting the containers:

1. **Check nginx is running:**
   ```bash
   docker-compose ps
   ```

2. **Test HTTP redirect:**
   ```bash
   curl -I http://localhost
   # Should return: HTTP/1.1 301 Moved Permanently
   ```

3. **Test HTTPS:**
   ```bash
   curl -k https://localhost
   # Should return the application
   ```

4. **Check SSL certificate:**
   ```bash
   openssl s_client -connect localhost:443 -servername localhost
   ```

## Troubleshooting

### nginx container won't start

**Error**: "cannot load certificate"

**Solution**: Ensure `ssl/cert.pem` and `ssl/key.pem` exist:
```bash
ls -la ssl/
```

### Browser shows "Not Secure"

**Cause**: Using self-signed certificate

**Solution**: 
- For development: Accept the browser warning
- For production: Use Let's Encrypt or commercial certificate

### Permission denied errors

**Solution**: Fix file permissions:
```bash
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem
```

### Certificate expired

**Solution**: Renew the certificate:
- Let's Encrypt: Run `certbot renew`
- Self-signed: Generate new certificate
- Commercial: Contact your certificate provider

## Security Best Practices

1. **Never commit SSL certificates** to git (already in `.gitignore`)
2. **Use strong private keys** (minimum 2048-bit RSA)
3. **Keep certificates updated** (set up auto-renewal)
4. **Restrict key file permissions** (`chmod 600 ssl/key.pem`)
5. **Use HTTPS only** in production (HTTP redirect is configured)
6. **Enable HSTS** (already configured in `nginx.conf`)

## Port Configuration

With nginx reverse proxy:

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | HTTP | Redirects to HTTPS |
| 443 | HTTPS | Main application access |
| 8080 | HTTP | Direct app access (internal only) |
| 9000 | HTTP | Portainer |
| 9443 | HTTPS | Portainer (secure) |

## Accessing the Application

**With nginx (recommended):**
- HTTP: http://yourdomain.com → redirects to HTTPS
- HTTPS: https://yourdomain.com

**Direct access (without nginx):**
- HTTP: http://yourdomain.com:8080

## Summary

✅ **nginx configured** as reverse proxy  
✅ **HTTP to HTTPS redirect** enabled  
✅ **SSL/TLS support** configured  
✅ **Persistent volumes** for nginx.conf and SSL  
✅ **Security headers** enabled  

Choose the SSL option that fits your needs:
- **Development**: Self-signed certificate
- **Production**: Let's Encrypt (free) or commercial certificate
